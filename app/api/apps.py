from typing import Optional, List
from fastapi import APIRouter, Depends, File, Form, UploadFile, HTTPException, status
from fastapi.responses import HTMLResponse
from app.api.deps import verify_admin_token
from app.schema.app_schema import (
    AppCreateRequest,
    AppUpdateRequest,
    AppResponse,
    AppListResponse,
    AppSourceResponse,
    AppVersionResponse,
    AppMetadataInspectRequest,
    AppMetadataInspectResponse,
)
from app.service import app_service
from app.service.zip_service import read_index_html_from_zip
from app.service.llm_service import extract_html_basic_metadata, analyze_app_metadata_with_ai
from app.core.logger import logger

router = APIRouter(prefix="/api/apps", tags=["微应用管理"])

@router.get("", response_model=AppListResponse, summary="获取微应用广场列表 (公开)")
async def get_apps(
    category: Optional[str] = None,
    search: Optional[str] = None,
) -> AppListResponse:
    """
    分页或带分类/搜索过滤的微应用列表展示
    """
    return app_service.list_all_apps(category=category, search=search)

@router.get("/{slug}", response_model=AppResponse, summary="获取单个微应用详情 (公开)")
async def get_app(slug: str) -> AppResponse:
    """
    获取指定 slug 的微应用元数据
    """
    return app_service.get_single_app(slug)

@router.get("/{slug}/source", response_model=AppSourceResponse, summary="获取微应用源码与元数据 (用于二次编辑)")
async def get_app_source(slug: str) -> AppSourceResponse:
    """
    读取应用的入口 HTML 源码及元数据，用于加载进 AI 创客工坊继续迭代
    """
    return app_service.get_app_source(slug)

@router.get("/{slug}/versions", response_model=List[AppVersionResponse], summary="获取微应用历史快照列表")
async def get_app_versions(slug: str) -> List[AppVersionResponse]:
    """
    获取该应用每次覆盖/更新保存的历史版本快照
    """
    return app_service.list_versions_of_app(slug)

@router.get("/{slug}/versions/{version_id}/preview", response_class=HTMLResponse, summary="预览微应用历史快照版本")
async def preview_app_version(slug: str, version_id: int):
    """
    直接输出该历史版本的 index.html 内容以供沙箱预览
    """
    html_content = app_service.get_version_preview_content(slug, version_id)
    return HTMLResponse(content=html_content, status_code=200)

@router.post("/{slug}/versions/{version_id}/rollback", response_model=AppResponse, summary="一键回滚微应用到指定快照 (需管理员权限)")
async def rollback_app_version(
    slug: str,
    version_id: int,
    _: bool = Depends(verify_admin_token),
) -> AppResponse:
    """
    一键回滚恢复该历史快照版本，自动对当前状态做安全备份
    """
    return app_service.rollback_app_version(slug, version_id)

@router.post("", response_model=AppResponse, summary="新建微应用 (需管理员权限)")
async def create_app(
    req: AppCreateRequest,
    _: bool = Depends(verify_admin_token),
) -> AppResponse:
    """
    通过 JSON 载荷创建微应用（支持直接传入内联 HTML）
    """
    return app_service.create_app_with_html(req)

@router.post("/upload", response_model=AppResponse, summary="通过文件上传发布新应用 (需管理员权限)")
async def upload_and_create_app(
    slug: str = Form(..., description="应用唯一标识"),
    title: str = Form(..., description="应用名称"),
    description: str = Form("", description="应用简介"),
    category: str = Form("通用", description="分类标签"),
    icon: str = Form("🚀", description="图标"),
    file: UploadFile = File(..., description="上传的 HTML 或 ZIP 文件"),
    _: bool = Depends(verify_admin_token),
) -> AppResponse:
    """
    支持一次性上传 .html 或 .zip 部署新微应用
    """
    filename = file.filename or ""
    file_bytes = await file.read()

    # 1. 先创建基本应用记录
    create_req = AppCreateRequest(
        slug=slug,
        title=title,
        description=description,
        category=category,
        icon=icon,
        html_content=""
    )
    app = app_service.create_app_with_html(create_req)

    # 2. 根据文件格式写入或解压
    if filename.lower().endswith(".zip"):
        app = app_service.overwrite_app_zip(slug, file_bytes, description="首次上传 ZIP 静态包")
    elif filename.lower().endswith((".html", ".htm")):
        try:
            html_text = file_bytes.decode("utf-8")
        except UnicodeDecodeError:
            html_text = file_bytes.decode("gbk", errors="ignore")
        app = app_service.overwrite_app_html(slug, html_text, description="首次上传单文件 HTML")
    else:
        try:
            html_text = file_bytes.decode("utf-8")
            app = app_service.overwrite_app_html(slug, html_text, description="首次上传文件")
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="不支持的文件格式，仅支持 .html 文件或 .zip 静态网站压缩包"
            )

    return app

@router.put("/{slug}", response_model=AppResponse, summary="修改微应用元信息 (需管理员权限)")
async def update_app(
    slug: str,
    req: AppUpdateRequest,
    _: bool = Depends(verify_admin_token),
) -> AppResponse:
    """
    更新标题、分类、图标等元信息
    """
    return app_service.update_app(slug, req)

@router.post("/{slug}/overwrite", response_model=AppResponse, summary="重新上传/覆盖微应用代码 (需管理员权限)")
async def overwrite_app(
    slug: str,
    file: Optional[UploadFile] = File(None, description="上传的替换文件 (.html 或 .zip)"),
    html_content: Optional[str] = Form(None, description="直接提交的 HTML 源码文本"),
    description: Optional[str] = Form("微应用代码覆盖更新", description="本次更新描述/版本说明"),
    _: bool = Depends(verify_admin_token),
) -> AppResponse:
    """
    覆盖已有微应用的文件内容（支持拖拽文件覆盖或提交代码文本覆盖）
    """
    if file:
        file_bytes = await file.read()
        filename = (file.filename or "").lower()
        if filename.endswith(".zip"):
            return app_service.overwrite_app_zip(slug, file_bytes, description=description)
        else:
            try:
                html_text = file_bytes.decode("utf-8")
            except UnicodeDecodeError:
                html_text = file_bytes.decode("gbk", errors="ignore")
            return app_service.overwrite_app_html(slug, html_text, description=description)
    elif html_content is not None and html_content.strip():
        return app_service.overwrite_app_html(slug, html_content, description=description)
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请提供要替换的文件或 HTML 源码内容"
        )

@router.delete("/{slug}", summary="删除微应用 (需管理员权限)")
async def delete_app(
    slug: str,
    _: bool = Depends(verify_admin_token),
) -> dict:
    """
    删除微应用数据库记录及磁盘托管目录与版本快照
    """
    app_service.delete_app(slug)
    return {"success": True, "message": f"微应用 '{slug}' 已彻底删除"}

@router.post("/inspect-metadata", response_model=AppMetadataInspectResponse, summary="从 HTML 源码提取或通过 AI 生成元信息")
async def inspect_metadata(
    req: AppMetadataInspectRequest,
) -> AppMetadataInspectResponse:
    """
    根据传入的 HTML 源码文本片段与文件名，自动提取 <title>/<meta> 或通过大模型智能生成标题与简介
    """
    html_text = req.html_content or ""
    if req.use_ai:
        data = await analyze_app_metadata_with_ai(html_text, filename=req.filename)
    else:
        data = extract_html_basic_metadata(html_text, filename=req.filename)

    return AppMetadataInspectResponse(**data)

@router.post("/inspect-file", response_model=AppMetadataInspectResponse, summary="从上传的 HTML/ZIP 文件提取或 AI 生成元信息")
async def inspect_uploaded_file_metadata(
    file: UploadFile = File(..., description="上传的 .html 或 .zip 文件"),
    use_ai: bool = Form(False, description="是否启用大模型深度提炼与生成"),
) -> AppMetadataInspectResponse:
    """
    自动读取上传的 .html 文件或 .zip 包内的 index.html，提取或由 AI 生成标题、简介、分类与 Slug
    """
    filename = file.filename or ""
    file_bytes = await file.read()
    html_text = ""

    if filename.lower().endswith(".zip"):
        html_text = read_index_html_from_zip(file_bytes)
    else:
        try:
            html_text = file_bytes.decode("utf-8")
        except UnicodeDecodeError:
            html_text = file_bytes.decode("gbk", errors="ignore")

    if use_ai:
        data = await analyze_app_metadata_with_ai(html_text, filename=filename)
    else:
        data = extract_html_basic_metadata(html_text, filename=filename)

    return AppMetadataInspectResponse(**data)
