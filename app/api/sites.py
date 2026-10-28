import mimetypes
from pathlib import Path
from fastapi import APIRouter, HTTPException, status, Request
from fastapi.responses import RedirectResponse, FileResponse, Response
from app.core.config import settings
from app.core.logger import logger
from app.repository import app_repo

router = APIRouter(tags=["静态微应用托管"])

@router.get("/s/{app_slug}", summary="微应用根路径规范化重定向")
async def redirect_to_trailing_slash(app_slug: str) -> RedirectResponse:
    """
    当用户访问 /s/{app_slug} 时，强制 307 重定向至 /s/{app_slug}/
    NOTE: 这一步至关重要！缺少末尾斜杠将导致前端相对路径静态资源（如 ./assets/app.js 或 css/style.css）解析到上级根路径引起 404
    """
    return RedirectResponse(url=f"/s/{app_slug}/", status_code=status.HTTP_307_TEMPORARY_REDIRECT)

@router.get("/s/{app_slug}/", summary="访问微应用首页入口")
@router.get("/s/{app_slug}/{file_path:path}", summary="访问微应用内部静态资源")
async def serve_site_file(app_slug: str, file_path: str = "") -> Response:
    """
    安全分发各微应用托管的静态文件：
    - 若访问根入口或 index.html，原子累加应用访问计数
    - 严格校验路径，杜绝任何上级目录穿越
    """
    clean_slug = app_slug.strip().lower()
    site_root = (settings.sites_path / clean_slug).resolve()

    if not site_root.exists() or not site_root.is_dir():
        logger.warning(f"微应用未找到或目录不存在: {clean_slug}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"未找到微应用 '{clean_slug}' 或其静态资源尚未部署"
        )

    # 规范化子路径
    req_path = file_path.strip().lstrip("/")
    if not req_path:
        req_path = "index.html"

    # 路径安全沙箱校验
    target_file = (site_root / req_path).resolve()
    try:
        target_file.relative_to(site_root)
    except ValueError:
        logger.warning(f"检测到非法目录穿越访问: slug={clean_slug}, path={file_path}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="非法文件路径"
        )

    # 如果请求的是子目录，尝试在该目录下寻找 index.html
    if target_file.is_dir():
        target_file = target_file / "index.html"

    if not target_file.exists() or not target_file.is_file():
        # 如果是 SPA 单页且找不到静态资源，且请求不是资源文件后缀，可按需降级
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"文件不存在: {req_path}"
        )

    # 当请求的是入口主页面时，原子累加访问计数
    if req_path in ("index.html", "", "index.htm"):
        app_repo.increment_view_count(clean_slug)

    # 自动探测 MIME 类型
    content_type, _ = mimetypes.guess_type(str(target_file))
    if not content_type:
        if target_file.suffix.lower() == ".wasm":
            content_type = "application/wasm"
        elif target_file.suffix.lower() == ".map":
            content_type = "application/json"
        else:
            content_type = "application/octet-stream"

    # 为 HTML 文件增加 UTF-8 编码声明
    if "text/html" in content_type:
        content_type = "text/html; charset=utf-8"

    return FileResponse(
        path=str(target_file),
        media_type=content_type,
        headers={
            "Cache-Control": "public, max-age=60",
            # 允许在主站 iframe 中同源沙箱内嵌入运行
            "X-Frame-Options": "SAMEORIGIN",
        }
    )
