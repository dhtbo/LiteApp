import httpx
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from app.api.deps import verify_admin_token
from app.schema.llm_schema import (
    LLMProviderCreate,
    LLMProviderUpdate,
    LLMProviderResponse,
    AIChatRequest,
    mask_api_key,
)
from app.schema.app_schema import (
    FieldAIGenerateRequest,
    FieldAIGenerateResponse,
    AgentSuiteGenerateResponse,
    AgentProxyCallRequest,
)
from app.model.models import LLMProviderModel
from app.repository import llm_repo
from app.service.llm_service import (
    stream_openai_chat,
    test_llm_connection,
    generate_field_with_ai,
    generate_agent_suite_with_ai,
)
from app.core.logger import logger

router = APIRouter(prefix="", tags=["大模型与AI工作台"])

def model_to_provider_response(m: LLMProviderModel) -> LLMProviderResponse:
    """
    转换为对外脱敏响应模型
    """
    return LLMProviderResponse(
        id=m.id or 0,
        name=m.name,
        base_url=m.base_url,
        masked_api_key=mask_api_key(m.api_key),
        model_name=m.model_name,
        is_active=bool(m.is_active),
        created_at=m.created_at,
        updated_at=m.updated_at,
    )

@router.get("/api/llm/configs", response_model=List[LLMProviderResponse], summary="获取所有大模型配置列表 (需鉴权)")
async def get_llm_configs(_: bool = Depends(verify_admin_token)) -> List[LLMProviderResponse]:
    """
    查询所有已配置的 OpenAI 兼容端点列表（Key 已脱敏）
    """
    providers = llm_repo.list_providers()
    return [model_to_provider_response(p) for p in providers]

@router.post("/api/llm/configs", response_model=LLMProviderResponse, summary="新增大模型配置 (需鉴权)")
async def create_llm_config(
    req: LLMProviderCreate,
    _: bool = Depends(verify_admin_token),
) -> LLMProviderResponse:
    """
    新增大模型提供商配置，并持久化到 SQLite
    """
    model = LLMProviderModel(
        id=None,
        name=req.name,
        base_url=req.base_url.strip(),
        api_key=req.api_key.strip(),
        model_name=req.model_name.strip(),
        is_active=1 if req.is_active else 0,
        created_at="",
        updated_at="",
    )
    saved = llm_repo.create_provider(model)
    return model_to_provider_response(saved)

@router.put("/api/llm/configs/{provider_id}", response_model=LLMProviderResponse, summary="修改大模型配置 (需鉴权)")
async def update_llm_config(
    provider_id: int,
    req: LLMProviderUpdate,
    _: bool = Depends(verify_admin_token),
) -> LLMProviderResponse:
    """
    修改指定提供商参数（未传 Key 时保留原 Key）
    """
    updated = llm_repo.update_provider(
        provider_id=provider_id,
        name=req.name,
        base_url=req.base_url,
        api_key=req.api_key,
        model_name=req.model_name,
        is_active=req.is_active,
    )
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="未找到对应的大模型配置"
        )
    return model_to_provider_response(updated)

@router.post("/api/llm/configs/{provider_id}/activate", summary="切换激活当前大模型配置 (需鉴权)")
async def activate_llm_config(
    provider_id: int,
    _: bool = Depends(verify_admin_token),
) -> dict:
    """
    将指定配置设为全局默认调用的模型
    """
    success = llm_repo.set_active_provider(provider_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="指定配置不存在")
    return {"success": True, "message": "已切换默认模型"}

@router.post("/api/llm/configs/{provider_id}/test", summary="测试大模型端点连通性 (需鉴权)")
async def test_config_connection(
    provider_id: int,
    _: bool = Depends(verify_admin_token),
) -> dict:
    """
    向目标 Base URL 发起轻量 Ping 连通测试
    """
    provider = llm_repo.get_provider_by_id(provider_id)
    if not provider:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="未找到配置")
    return await test_llm_connection(provider)

@router.delete("/api/llm/configs/{provider_id}", summary="删除大模型配置 (需鉴权)")
async def delete_llm_config(
    provider_id: int,
    _: bool = Depends(verify_admin_token),
) -> dict:
    """
    删除指定的提供商配置
    """
    success = llm_repo.delete_provider(provider_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="未找到指定配置")
    return {"success": True, "message": "删除成功"}

@router.post("/api/ai/chat/stream", summary="AI 创客代码生成流式调用 (需鉴权)")
async def ai_stream_chat(
    req: AIChatRequest,
    _: bool = Depends(verify_admin_token),
) -> StreamingResponse:
    """
    通过 Server-Sent Events (SSE) 流式返回大模型生成的单文件 HTML 源码
    """
    # 确定调用的模型配置
    provider: Optional[LLMProviderModel] = None
    if req.provider_id:
        provider = llm_repo.get_provider_by_id(req.provider_id)
    if not provider:
        provider = llm_repo.get_active_provider()

    if not provider:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="尚未配置任何可用的大模型端点，请先在模型设置中添加 OpenAI 兼容接口"
        )

    if not provider.api_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="当前激活的大模型缺少 API Key，请先补全配置"
        )

    generator = stream_openai_chat(
        provider=provider,
        messages=req.messages,
        temperature=req.temperature or 0.7,
        system_instruction=req.system_instruction,
        max_tokens=req.max_tokens,
        top_p=req.top_p,
    )

    return StreamingResponse(
        generator,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )

@router.post("/api/ai/generate-field", response_model=FieldAIGenerateResponse, summary="输入框单字段 AI 智能扩写与生成")
async def ai_generate_field(
    req: FieldAIGenerateRequest,
    _: bool = Depends(verify_admin_token),
) -> FieldAIGenerateResponse:
    """
    针对提示词、简介、标题等字段提供智能生成与润色
    """
    provider = None
    if req.provider_id:
        provider = llm_repo.get_provider_by_id(req.provider_id)
    content = await generate_field_with_ai(
        field_type=req.field_type,
        context=req.context,
        provider=provider
    )
    return FieldAIGenerateResponse(field_type=req.field_type, content=content, generated_content=content)

@router.post("/api/ai/generate-agent-suite", response_model=AgentSuiteGenerateResponse, summary="根据简要概念一键 AI 生成整套智能体配置")
async def ai_generate_agent_suite(
    req: FieldAIGenerateRequest,
    _: bool = Depends(verify_admin_token),
) -> AgentSuiteGenerateResponse:
    """
    输入一句话（如 '生成n8n工作流并调用API发布的助手'），一键生成标题、图标、角色设定、欢迎语、推荐提问、Skills与Tools
    """
    provider = None
    if req.provider_id:
        provider = llm_repo.get_provider_by_id(req.provider_id)
    data = await generate_agent_suite_with_ai(
        context=req.context,
        provider=provider
    )
    return AgentSuiteGenerateResponse(**data)

@router.post("/api/agent/proxy-call", summary="智能体第三方 API 安全代理调用 (绕过浏览器跨域)")
async def agent_api_proxy_call(
    req: AgentProxyCallRequest,
) -> Any:
    """
    为智能体单页微应用提供安全可靠的外部 REST API 代理中继
    """
    target_url = req.url.strip()
    if not target_url.startswith(("http://", "https://")):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="非法的请求目标 URL 地址，只支持 HTTP/HTTPS 协议")

    method = (req.method or "POST").upper()
    headers = {k: v for k, v in (req.headers or {}).items() if k.lower() not in {"host", "content-length"}}
    
    timeout = httpx.Timeout(connect=10.0, read=30.0, write=10.0, pool=30.0)
    try:
        async with httpx.AsyncClient(timeout=timeout, verify=False) as client:
            if method == "GET":
                res = await client.get(target_url, headers=headers)
            elif method == "POST":
                res = await client.post(target_url, headers=headers, json=req.payload)
            elif method == "PUT":
                res = await client.put(target_url, headers=headers, json=req.payload)
            elif method == "DELETE":
                res = await client.delete(target_url, headers=headers)
            else:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"不支持的 HTTP 方法: {method}")

            # 尝试返回 JSON
            try:
                body_json = res.json()
                return {
                    "status_code": res.status_code,
                    "is_json": True,
                    "data": body_json,
                }
            except Exception:
                return {
                    "status_code": res.status_code,
                    "is_json": False,
                    "text": res.text[:2000],
                }
    except Exception as e:
        logger.error(f"代理请求外部 API 失败: url={target_url}, err={e}")
        return {
            "status_code": 500,
            "error": True,
            "message": f"代理请求失败: {str(e)}",
        }


@router.post("/api/ai/agent/stream", summary="已发布微应用 AI 智能体对话流式调用 (公开接口)")
async def ai_stream_agent_chat(
    req: AIChatRequest,
) -> StreamingResponse:
    """
    专为已发布的微应用 AI 智能体提供的免密流式对话接口，
    密钥在后端安全持有，向客户端安全流式输出模型回复
    """
    provider: Optional[LLMProviderModel] = None
    if req.provider_id:
        provider = llm_repo.get_provider_by_id(req.provider_id)
    if not provider:
        provider = llm_repo.get_active_provider()

    if not provider or not provider.api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="平台当前尚未配置可用的大模型提供商或 API Key"
        )

    generator = stream_openai_chat(
        provider=provider,
        messages=req.messages,
        temperature=req.temperature or 0.7,
        system_instruction=req.system_instruction,
        max_tokens=req.max_tokens,
        top_p=req.top_p,
    )

    return StreamingResponse(
        generator,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )

@router.post("/api/ai/generate-field", response_model=FieldAIGenerateResponse, summary="输入框单字段 AI 智能扩写与生成")
async def ai_generate_field(
    req: FieldAIGenerateRequest,
    _: bool = Depends(verify_admin_token),
) -> FieldAIGenerateResponse:
    """
    针对提示词、简介、标题等字段提供智能生成与润色
    """
    provider = None
    if req.provider_id:
        provider = llm_repo.get_provider_by_id(req.provider_id)
    content = await generate_field_with_ai(
        field_type=req.field_type,
        context=req.context,
        provider=provider
    )
    return FieldAIGenerateResponse(field_type=req.field_type, content=content, generated_content=content)

@router.post("/api/ai/generate-agent-suite", response_model=AgentSuiteGenerateResponse, summary="根据简要概念一键 AI 生成整套智能体配置")
async def ai_generate_agent_suite(
    req: FieldAIGenerateRequest,
    _: bool = Depends(verify_admin_token),
) -> AgentSuiteGenerateResponse:
    """
    输入一句话（如 '生成n8n工作流并调用API发布的助手'），一键生成标题、图标、角色设定、欢迎语、推荐提问、Skills与Tools
    """
    provider = None
    if req.provider_id:
        provider = llm_repo.get_provider_by_id(req.provider_id)
    data = await generate_agent_suite_with_ai(
        context=req.context,
        provider=provider
    )
    return AgentSuiteGenerateResponse(**data)

@router.post("/api/agent/proxy-call", summary="智能体第三方 API 安全代理调用 (绕过浏览器跨域)")
async def agent_api_proxy_call(
    req: AgentProxyCallRequest,
) -> Any:
    """
    为智能体单页微应用提供安全可靠的外部 REST API 代理中继
    """
    target_url = req.url.strip()
    if not target_url.startswith(("http://", "https://")):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="非法的请求目标 URL 地址，只支持 HTTP/HTTPS 协议")

    method = (req.method or "POST").upper()
    headers = {k: v for k, v in (req.headers or {}).items() if k.lower() not in {"host", "content-length"}}
    
    timeout = httpx.Timeout(connect=10.0, read=30.0, write=10.0, pool=30.0)
    try:
        async with httpx.AsyncClient(timeout=timeout, verify=False) as client:
            if method == "GET":
                res = await client.get(target_url, headers=headers)
            elif method == "POST":
                res = await client.post(target_url, headers=headers, json=req.payload)
            elif method == "PUT":
                res = await client.put(target_url, headers=headers, json=req.payload)
            elif method == "DELETE":
                res = await client.delete(target_url, headers=headers)
            else:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"不支持的 HTTP 方法: {method}")

            # 尝试返回 JSON
            try:
                body_json = res.json()
                return {
                    "status_code": res.status_code,
                    "is_json": True,
                    "data": body_json,
                }
            except Exception:
                return {
                    "status_code": res.status_code,
                    "is_json": False,
                    "text": res.text[:2000],
                }
    except Exception as e:
        logger.error(f"代理请求外部 API 失败: url={target_url}, err={e}")
        return {
            "status_code": 500,
            "error": True,
            "message": f"代理请求失败: {str(e)}",
        }

