import shutil
import time
from pathlib import Path
from typing import Optional, List
from fastapi import HTTPException, status
from app.core.config import settings
from app.core.logger import logger
from app.model.models import AppModel, AppVersionModel
from app.schema.app_schema import (
    AppCreateRequest,
    AppUpdateRequest,
    AppResponse,
    AppListResponse,
    AppSourceResponse,
    AppVersionResponse,
)
from app.repository import app_repo
from app.service.zip_service import extract_zip_safely

def get_app_storage_dir(slug: str) -> Path:
    """
    根据 Slug 获取静态微应用物理存放目录
    """
    return settings.sites_path / slug

def get_app_backups_dir(slug: str) -> Path:
    """
    根据 Slug 获取历史版本快照归档目录
    """
    d = settings.backups_path / slug
    d.mkdir(parents=True, exist_ok=True)
    return d

def model_to_response(model: AppModel) -> AppResponse:
    """
    转换 AppModel 为带绝对/相对 URL 的 API 响应模型
    """
    return AppResponse(
        id=model.id or 0,
        slug=model.slug,
        title=model.title,
        description=model.description,
        category=model.category,
        icon=model.icon,
        entry_type=model.entry_type,
        view_count=model.view_count,
        created_at=model.created_at,
        updated_at=model.updated_at,
        url_path=f"/s/{model.slug}/",
    )

def version_to_response(v: AppVersionModel) -> AppVersionResponse:
    """
    转换 AppVersionModel 为响应模型
    """
    return AppVersionResponse(
        id=v.id or 0,
        app_slug=v.app_slug,
        version_num=v.version_num,
        entry_type=v.entry_type,
        description=v.description,
        created_at=v.created_at,
    )

def create_version_snapshot(slug: str, entry_type: str, description: str) -> Optional[AppVersionModel]:
    """
    对指定微应用当前目录创建一份物理文件归档与数据库快照记录
    """
    app_dir = get_app_storage_dir(slug)
    if not app_dir.exists() or not any(app_dir.iterdir()):
        return None

    try:
        backups_dir = get_app_backups_dir(slug)
        # 获取当前下一个版本号
        existing_versions = app_repo.list_app_versions(slug)
        next_ver = len(existing_versions) + 1

        target_dir = backups_dir / f"v{next_ver}"
        if target_dir.exists():
            shutil.rmtree(target_dir, ignore_errors=True)

        shutil.copytree(app_dir, target_dir)
        version_record = app_repo.create_app_version(
            app_slug=slug,
            entry_type=entry_type,
            description=description,
            storage_path=str(target_dir),
        )
        logger.info(f"成功为应用 '{slug}' 创建版本快照 v{next_ver} -> {target_dir}")
        return version_record
    except Exception as e:
        logger.error(f"创建应用版本快照失败: slug={slug}, err={e}")
        return None

def list_all_apps(category: Optional[str] = None, search: Optional[str] = None) -> AppListResponse:
    """
    获取微应用广场列表
    """
    models = app_repo.list_apps(category=category, search=search)
    categories = app_repo.get_all_categories()
    items = [model_to_response(m) for m in models]
    return AppListResponse(
        total=len(items),
        items=items,
        categories=categories,
    )

def get_single_app(slug: str) -> AppResponse:
    """
    根据 Slug 获取单条应用详情
    """
    app = app_repo.get_app_by_slug(slug)
    if not app:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"未找到标识为 '{slug}' 的微应用"
        )
    return model_to_response(app)

def get_app_source(slug: str) -> AppSourceResponse:
    """
    读取指定应用的入口 HTML 源码及元数据（用于在 AI 工坊中再次加载编辑）
    """
    app = app_repo.get_app_by_slug(slug)
    if not app:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"未找到微应用: {slug}"
        )

    app_dir = get_app_storage_dir(slug)
    index_file = app_dir / "index.html"
    html_content = ""
    if index_file.exists():
        try:
            html_content = index_file.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            html_content = index_file.read_text(encoding="gbk", errors="ignore")
    else:
        # 如果是目录，尝试寻找任何 html 文件
        html_files = list(app_dir.glob("*.html"))
        if html_files:
            try:
                html_content = html_files[0].read_text(encoding="utf-8")
            except Exception:
                pass

    return AppSourceResponse(
        slug=app.slug,
        title=app.title,
        description=app.description,
        category=app.category,
        icon=app.icon,
        entry_type=app.entry_type,
        html_content=html_content,
    )

def create_app_with_html(req: AppCreateRequest) -> AppResponse:
    """
    创建新微应用，并写入初始单文件 HTML，同时生成 v1 初始快照
    """
    existing = app_repo.get_app_by_slug(req.slug)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"应用标识 Slug '{req.slug}' 已被占用，请更换"
        )

    app_dir = get_app_storage_dir(req.slug)
    app_dir.mkdir(parents=True, exist_ok=True)
    index_file = app_dir / "index.html"

    content = req.html_content
    if not content or not content.strip():
        content = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{req.title}</title>
  <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-slate-900 text-slate-100 min-h-screen flex items-center justify-center p-4">
  <div class="text-center max-w-md bg-slate-800 p-8 rounded-2xl border border-slate-700 shadow-xl">
    <div class="text-5xl mb-4">{req.icon or '🚀'}</div>
    <h1 class="text-2xl font-bold mb-2">{req.title}</h1>
    <p class="text-slate-400 text-sm mb-6">{req.description or '应用已就绪，等待上传或生成代码...'}</p>
    <span class="inline-block px-3 py-1 bg-indigo-600/30 text-indigo-400 border border-indigo-500/40 rounded-full text-xs font-semibold">
      {req.category or '通用'}
    </span>
  </div>
</body>
</html>"""

    index_file.write_text(content, encoding="utf-8")

    model = AppModel(
        id=None,
        slug=req.slug,
        title=req.title,
        description=req.description or "",
        category=req.category or "通用",
        icon=req.icon or "🚀",
        entry_type="html",
        view_count=0,
        created_at="",
        updated_at="",
    )
    saved = app_repo.create_app(model)

    # 创建初始版本 v1 快照
    create_version_snapshot(req.slug, entry_type="html", description="初次发布版本")
    return model_to_response(saved)

def overwrite_app_html(slug: str, html_content: str, description: Optional[str] = None) -> AppResponse:
    """
    覆盖已有微应用的 index.html 源码，并在更新前后妥善维护快照
    """
    app = app_repo.get_app_by_slug(slug)
    if not app:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"未找到微应用: {slug}"
        )

    # 1. 如果已有内容，先对更新前状态归档（如果尚未归档过）
    versions = app_repo.list_app_versions(slug)
    if not versions:
        create_version_snapshot(slug, entry_type=app.entry_type, description="初始版本自动归档")

    # 2. 写入新代码
    app_dir = get_app_storage_dir(slug)
    app_dir.mkdir(parents=True, exist_ok=True)
    index_file = app_dir / "index.html"
    index_file.write_text(html_content, encoding="utf-8")

    # 3. 更新数据库 entry_type 为 html
    app_repo.update_app_entry_type(slug, "html")

    # 4. 记录本次更新的版本快照
    desc = description or "HTML 源码更新"
    create_version_snapshot(slug, entry_type="html", description=desc)

    updated = app_repo.get_app_by_slug(slug)
    return model_to_response(updated or app)

def overwrite_app_zip(slug: str, zip_bytes: bytes, description: Optional[str] = None) -> AppResponse:
    """
    解压并覆盖已有微应用的全部静态资源，并打上版本快照
    """
    app = app_repo.get_app_by_slug(slug)
    if not app:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"未找到微应用: {slug}"
        )

    # 1. 归档当前状态
    versions = app_repo.list_app_versions(slug)
    if not versions:
        create_version_snapshot(slug, entry_type=app.entry_type, description="初始版本自动归档")

    # 2. 安全解压并覆盖
    app_dir = get_app_storage_dir(slug)
    extract_zip_safely(zip_bytes, app_dir)

    # 3. 更新数据库
    app_repo.update_app_entry_type(slug, "zip")

    # 4. 记录本次更新快照
    desc = description or "ZIP 静态资源包覆盖更新"
    create_version_snapshot(slug, entry_type="zip", description=desc)

    updated = app_repo.get_app_by_slug(slug)
    return model_to_response(updated or app)

def update_app(slug: str, req: AppUpdateRequest) -> AppResponse:
    """
    修改微应用元信息
    """
    updated = app_repo.update_app_metadata(
        slug=slug,
        title=req.title,
        description=req.description,
        category=req.category,
        icon=req.icon,
    )
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"未找到微应用: {slug}"
        )
    return model_to_response(updated)

def delete_app(slug: str) -> bool:
    """
    删除微应用记录及对应的物理磁盘静态文件夹与版本快照
    """
    app = app_repo.get_app_by_slug(slug)
    if not app:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"未找到微应用: {slug}"
        )

    # 1. 物理删除静态站点目录
    app_dir = get_app_storage_dir(slug)
    if app_dir.exists():
        try:
            shutil.rmtree(app_dir, ignore_errors=True)
            logger.info(f"已清理应用静态文件夹: {app_dir}")
        except Exception as e:
            logger.warning(f"删除物理文件夹失败: {e}")

    # 2. 物理删除历史版本备份目录
    backups_dir = settings.backups_path / slug
    if backups_dir.exists():
        try:
            shutil.rmtree(backups_dir, ignore_errors=True)
            logger.info(f"已清理应用历史版本文件夹: {backups_dir}")
        except Exception as e:
            logger.warning(f"删除历史版本文件夹失败: {e}")

    # 3. 数据库删除微应用记录
    success = app_repo.delete_app(slug)
    return success

# ==================== 版本快照与回滚服务 ====================

def list_versions_of_app(slug: str) -> List[AppVersionResponse]:
    """
    获取微应用的所有历史快照列表
    """
    app = app_repo.get_app_by_slug(slug)
    if not app:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"未找到微应用: {slug}"
        )
    versions = app_repo.list_app_versions(slug)
    return [version_to_response(v) for v in versions]

def get_version_preview_content(slug: str, version_id: int) -> str:
    """
    读取历史版本快照中的 index.html 源码以供沙盒预览
    """
    version = app_repo.get_app_version_by_id(version_id)
    if not version or version.app_slug != slug:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"未找到对应的历史快照版本记录 (id={version_id})"
        )

    target_dir = Path(version.storage_path)
    index_file = target_dir / "index.html"
    if not index_file.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="该快照目录中未检测到 index.html"
        )

    try:
        return index_file.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return index_file.read_text(encoding="gbk", errors="ignore")

def rollback_app_version(slug: str, version_id: int) -> AppResponse:
    """
    将微应用一键回滚恢复到指定快照版本
    """
    app = app_repo.get_app_by_slug(slug)
    if not app:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"未找到微应用: {slug}"
        )

    version = app_repo.get_app_version_by_id(version_id)
    if not version or version.app_slug != slug:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"未找到指定的历史快照版本记录 (id={version_id})"
        )

    snapshot_path = Path(version.storage_path)
    if not snapshot_path.exists():
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="该版本的磁盘快照物理文件已缺失，无法回滚"
        )

    # 1. 回滚前对当前状态打一个保护性快照
    create_version_snapshot(slug, entry_type=app.entry_type, description=f"回滚至 v{version.version_num} 前的状态自动快照")

    # 2. 覆盖恢复应用目录
    app_dir = get_app_storage_dir(slug)
    if app_dir.exists():
        shutil.rmtree(app_dir, ignore_errors=True)

    shutil.copytree(snapshot_path, app_dir)

    # 3. 更新应用类型与时间戳
    app_repo.update_app_entry_type(slug, version.entry_type)

    # 4. 再创建一条回滚生效的版本快照
    create_version_snapshot(slug, entry_type=version.entry_type, description=f"已成功回滚至 v{version.version_num}")

    logger.info(f"微应用 '{slug}' 已成功一键回滚至快照版本 v{version.version_num}")
    updated = app_repo.get_app_by_slug(slug)
    return model_to_response(updated or app)
