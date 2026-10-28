import io
import os
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Set
from fastapi import HTTPException, status
from app.core.config import settings
from app.core.logger import logger

IGNORED_SYSTEM_ENTRIES: Set[str] = {
    "__MACOSX",
    ".DS_Store",
    "Thumbs.db",
    "desktop.ini",
    ".git",
}

def is_ignored_entry(name: str) -> bool:
    """
    判断是否为操作系统生成的垃圾隐藏文件或目录
    """
    parts = Path(name).parts
    return any(p in IGNORED_SYSTEM_ENTRIES or p.startswith("._") for p in parts)

def extract_zip_safely(zip_bytes: bytes, destination_dir: Path) -> None:
    """
    安全解压 ZIP 压缩包至目标目录：
    1. 防范 Zip Slip 路径穿越攻击；
    2. 限制总解包体积，防止 Zip 炸弹；
    3. 智能扁平化 (Flatten Root Directory)：自动上移单根目录包裹的内容，保证根目录下存在 index.html。
    
    :param zip_bytes: 压缩包二进制数据
    :param destination_dir: 最终站点存放的绝对目录
    :raises HTTPException: 解包异常或不合法格式
    """
    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if len(zip_bytes) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"压缩包体积超过最大限制 ({settings.MAX_UPLOAD_SIZE_MB}MB)"
        )

    try:
        zip_file = zipfile.ZipFile(io.BytesIO(zip_bytes))
    except zipfile.BadZipFile as e:
        logger.warning(f"无效的 ZIP 文件: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="上传的文件不是合法的 ZIP 压缩包"
        )

    # 1. 严格检查解包后总体积及 Zip Slip 风险
    total_uncompressed_size = 0
    for info in zip_file.infolist():
        # 拒绝绝对路径或跨盘符路径
        fname = info.filename.replace("\\", "/")
        if fname.startswith("/") or ":" in fname:
            logger.warning(f"Zip Slip 拦截: 绝对路径条目 {fname}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"ZIP 包中包含非法绝对路径: {fname}"
            )
        
        # 拒绝向上遍历的相对路径
        path_parts = Path(fname).parts
        if ".." in path_parts:
            logger.warning(f"Zip Slip 拦截: 发现相对路径穿越 {fname}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"ZIP 包中包含非法路径穿越条目: {fname}"
            )

        total_uncompressed_size += info.file_size
        if total_uncompressed_size > max_bytes:
            logger.warning("解包拦截: 总体积超过 Zip 炸弹防护上限")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"ZIP 解包后总体积超过最大解压限制 ({settings.MAX_UPLOAD_SIZE_MB}MB)"
            )

    # 2. 先解压到隔离的临时目录以进行智能处理与校验
    with tempfile.TemporaryDirectory() as temp_dir_str:
        temp_dir = Path(temp_dir_str)

        for info in zip_file.infolist():
            if is_ignored_entry(info.filename):
                continue
            
            # 计算绝对提取路径，二次校验是否在 temp_dir 内部
            target_path = (temp_dir / info.filename).resolve()
            try:
                target_path.relative_to(temp_dir.resolve())
            except ValueError:
                logger.warning(f"Zip Slip 终极防御拦截: {info.filename}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="检测到恶意目录穿越风险"
                )

            zip_file.extract(info, path=temp_dir)

        # 3. 智能扁平化 (Flatten Root Directory) 处理
        # 寻找根目录下存在的有效项（排除系统隐藏文件）
        valid_root_entries = [
            p for p in temp_dir.iterdir()
            if not is_ignored_entry(p.name)
        ]

        effective_content_dir = temp_dir

        # 如果根目录下直接没有 index.html
        if not (temp_dir / "index.html").exists():
            # 若只存在唯一一个有效子目录
            if len(valid_root_entries) == 1 and valid_root_entries[0].is_dir():
                sub_dir = valid_root_entries[0]
                if (sub_dir / "index.html").exists():
                    logger.info(f"触发智能扁平化：发现唯一外层包裹文件夹 '{sub_dir.name}'，正在自动提升至根目录")
                    effective_content_dir = sub_dir
                else:
                    # 尝试再深挖一层寻找 index.html（例如 某项目-master/dist/index.html）
                    sub_entries = [p for p in sub_dir.iterdir() if not is_ignored_entry(p.name)]
                    if len(sub_entries) == 1 and sub_entries[0].is_dir() and (sub_entries[0] / "index.html").exists():
                        logger.info(f"触发二级智能扁平化：提升深层子目录 '{sub_entries[0].name}' 至根目录")
                        effective_content_dir = sub_entries[0]

        # 校验最终目标是否具备 index.html
        if not (effective_content_dir / "index.html").is_file():
            # 搜索是否存在任何子目录包含 index.html，如果存在给出友好指引
            html_candidates = list(temp_dir.glob("**/index.html"))
            if html_candidates:
                rel_path = html_candidates[0].relative_to(temp_dir)
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"ZIP 包根目录缺少 'index.html'。检测到在 '{rel_path}' 存在 index.html，请确认压缩包目录结构"
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="ZIP 压缩包中缺少入口文件 'index.html'，请确认后重新打包"
                )

        # 4. 将处理完成的内容安全覆盖复制至目标目录
        destination_dir.mkdir(parents=True, exist_ok=True)

        # 清空原目录现有文件（除目录本身）以实现完全覆盖更新
        for item in destination_dir.iterdir():
            if item.is_dir():
                shutil.rmtree(item, ignore_errors=True)
            else:
                try:
                    item.unlink(missing_ok=True)
                except Exception as e:
                    logger.warning(f"清理文件失败: {item}, {e}")

        # 将有效内容递归复制至 destination_dir
        for src_item in effective_content_dir.iterdir():
            if is_ignored_entry(src_item.name):
                continue
            dst_item = destination_dir / src_item.name
            if src_item.is_dir():
                shutil.copytree(src_item, dst_item, dirs_exist_ok=True)
            else:
                shutil.copy2(src_item, dst_item)

        logger.info(f"ZIP 包解压并智能扁平化成功，已安全部署至: {destination_dir}")

def read_index_html_from_zip(zip_bytes: bytes) -> str:
    """
    轻量扫描 ZIP 压缩包中的 index.html 文本内容，用于元数据自动解析与 AI 提炼
    
    :param zip_bytes: ZIP 二进制字节
    :returns: index.html 的文本内容，若未找到返回空字符串
    """
    try:
        zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
    except Exception:
        return ""

    # 优先查找根目录下的 index.html 或 index.htm
    candidate = None
    for name in zf.namelist():
        clean_name = name.replace("\\", "/").strip().lstrip("/")
        if is_ignored_entry(clean_name):
            continue
        parts = clean_name.split("/")
        if parts[-1].lower() in ("index.html", "index.htm"):
            if len(parts) == 1:
                candidate = name
                break
            elif candidate is None or len(parts) < len(candidate.split("/")):
                candidate = name

    if not candidate:
        return ""

    try:
        # 最多读取前 512KB 以免内存过大
        with zf.open(candidate) as f:
            raw_data = f.read(512 * 1024)
            try:
                return raw_data.decode("utf-8")
            except UnicodeDecodeError:
                return raw_data.decode("gbk", errors="ignore")
    except Exception as e:
        logger.warning(f"从 ZIP 预览读取 index.html 失败: {e}")
        return ""
