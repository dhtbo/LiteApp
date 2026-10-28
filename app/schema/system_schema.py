from pydantic import BaseModel, Field
from typing import Optional

class SystemConfigResponse(BaseModel):
    """系统全局集成配置响应模型"""
    n8n_base_url: str = Field(..., description="n8n 基础服务地址")
    n8n_api_key: str = Field(..., description="n8n 访问鉴权 API Key")

class SystemConfigUpdateRequest(BaseModel):
    """系统全局集成配置更新请求模型"""
    n8n_base_url: Optional[str] = Field(None, description="n8n 基础服务地址")
    n8n_api_key: Optional[str] = Field(None, description="n8n 访问鉴权 API Key")
