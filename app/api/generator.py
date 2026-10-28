from typing import Optional
from fastapi import APIRouter, Depends, File, Form, UploadFile, HTTPException, status
from app.api.deps import verify_admin_token
from app.schema.app_schema import (
    AgentAppGenerateRequest,
    N8nAppGenerateRequest,
    FormGeneratePromptRequest,
    GeneratedAppResult,
    AppCreateRequest,
    AppResponse,
)
from app.service import generator_service, app_service
from app.core.logger import logger

router = APIRouter(prefix="/api/generator", tags=["智能体与自动化生成器"])

@router.post("/agent", response_model=GeneratedAppResult, summary="生成 AI 智能体对话单页应用 (需管理员权限)")
async def generate_agent_app(
    req: AgentAppGenerateRequest,
    auto_publish: bool = False,
    _: bool = Depends(verify_admin_token),
) -> GeneratedAppResult:
    """
    根据配置角色设定与快速提问生成独立 AI 智能体单页微应用
    """
    result = generator_service.generate_agent_app_html(req)
    if auto_publish:
        create_req = AppCreateRequest(
            slug=result.slug,
            title=result.title,
            description=result.description,
            category=result.category,
            icon=result.icon,
            html_content=result.html_content,
        )
        app_service.create_app_with_html(create_req)
        logger.info(f"已自动发布生成的智能体微应用: slug={result.slug}")
    return result

@router.post("/n8n", response_model=GeneratedAppResult, summary="生成 n8n 自动化微应用 (需管理员权限)")
async def generate_n8n_app(
    req: N8nAppGenerateRequest,
    auto_publish: bool = False,
    _: bool = Depends(verify_admin_token),
) -> GeneratedAppResult:
    """
    生成 n8n Chat 嵌入或 Webhook 触发与执行结果看板微应用
    """
    result = generator_service.generate_n8n_app_html(req)
    if auto_publish:
        create_req = AppCreateRequest(
            slug=result.slug,
            title=result.title,
            description=result.description,
            category=result.category,
            icon=result.icon,
            html_content=result.html_content,
        )
        app_service.create_app_with_html(create_req)
        logger.info(f"已自动发布生成的 n8n 自动化微应用: slug={result.slug}")
    return result

@router.post("/form-prompt", response_model=GeneratedAppResult, summary="根据功能需求描述生成数据采集表单 (需管理员权限)")
async def generate_form_from_prompt(
    req: FormGeneratePromptRequest,
    auto_publish: bool = False,
    _: bool = Depends(verify_admin_token),
) -> GeneratedAppResult:
    """
    智能分析需求描述中的字段信息，生成带本地保存与 Webhook 转发的表单应用
    """
    fields = generator_service.parse_prompt_to_form_fields(req.prompt)
    result = generator_service.generate_form_app_html(
        title=req.title,
        description=req.description,
        icon=req.icon or "📝",
        category=req.category or "数据收集",
        fields=fields,
        webhook_url=req.webhook_url,
        slug=req.slug,
    )
    if auto_publish:
        create_req = AppCreateRequest(
            slug=result.slug,
            title=result.title,
            description=result.description,
            category=result.category,
            icon=result.icon,
            html_content=result.html_content,
        )
        app_service.create_app_with_html(create_req)
        logger.info(f"已自动发布生成的表单微应用: slug={result.slug}")
    return result

@router.post("/form-file", response_model=GeneratedAppResult, summary="上传 CSV/Excel 自动推断字段生成采集表单 (需管理员权限)")
async def generate_form_from_file(
    file: UploadFile = File(..., description="上传的 .csv 或 .xlsx 模板表格"),
    title: str = Form(..., description="表单名称"),
    description: str = Form("", description="表单简介"),
    icon: str = Form("📊", description="图标 Emoji"),
    category: str = Form("数据收集", description="分类"),
    webhook_url: Optional[str] = Form(None, description="可选的提交目标 Webhook"),
    slug: Optional[str] = Form(None, description="指定的 slug"),
    auto_publish: bool = Form(False, description="是否直接发布"),
    _: bool = Depends(verify_admin_token),
) -> GeneratedAppResult:
    """
    读取表格首行表头和样本值，推断数据类型并生成数据录入表单单页应用
    """
    filename = file.filename or "table.csv"
    file_bytes = await file.read()
    fields = generator_service.parse_table_file_to_fields(file_bytes, filename)

    result = generator_service.generate_form_app_html(
        title=title,
        description=description,
        icon=icon,
        category=category,
        fields=fields,
        webhook_url=webhook_url,
        slug=slug,
    )
    if auto_publish:
        create_req = AppCreateRequest(
            slug=result.slug,
            title=result.title,
            description=result.description,
            category=result.category,
            icon=result.icon,
            html_content=result.html_content,
        )
        app_service.create_app_with_html(create_req)
        logger.info(f"已自动从文件发布表单微应用: slug={result.slug}")
    return result
