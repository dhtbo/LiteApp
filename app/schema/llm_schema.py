from typing import Optional, List
from pydantic import BaseModel, Field

def mask_api_key(api_key: str) -> str:
    """
    对 API Key 进行脱敏处理，防止敏感信息泄漏
    
    :param api_key: 原始密钥
    :returns: 脱敏后的字符串（如 sk-abc...1234）
    """
    if not api_key:
        return ""
    length = len(api_key)
    if length <= 8:
        return "****"
    return f"{api_key[:3]}...{api_key[-4:]}"

class LLMProviderCreate(BaseModel):
    """
    新增大模型兼容配置请求
    """
    name: str = Field(..., min_length=1, max_length=100, description="模型配置友好展示名称")
    base_url: str = Field(..., min_length=1, max_length=300, description="API 基础地址，例如 https://api.openai.com/v1")
    api_key: str = Field(..., min_length=1, max_length=300, description="API 密钥")
    model_name: str = Field(..., min_length=1, max_length=100, description="具体调用的模型标识，例如 gpt-4o 或 deepseek-chat")
    is_active: bool = Field(False, description="是否立即设为激活模型")

class LLMProviderUpdate(BaseModel):
    """
    修改大模型配置请求
    """
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    base_url: Optional[str] = Field(None, min_length=1, max_length=300)
    api_key: Optional[str] = Field(None, max_length=300, description="留空或不传表示不修改原密钥")
    model_name: Optional[str] = Field(None, min_length=1, max_length=100)
    is_active: Optional[bool] = None

class LLMProviderResponse(BaseModel):
    """
    大模型配置脱敏响应模型
    """
    id: int
    name: str
    base_url: str
    masked_api_key: str
    model_name: str
    is_active: bool
    created_at: str
    updated_at: str

class AIChatMessage(BaseModel):
    """
    AI 对话历史单条消息
    """
    role: str = Field(..., description="角色：system / user / assistant")
    content: str = Field(..., description="文本内容")

class AIChatRequest(BaseModel):
    """
    AI 创客流式对话生成请求
    """
    messages: List[AIChatMessage] = Field(..., description="对话上下文消息数组")
    provider_id: Optional[int] = Field(None, description="指定调用的模型提供商 ID，默认使用当前激活项")
    temperature: Optional[float] = Field(0.7, ge=0.0, le=2.0, description="采样温度")
    system_instruction: Optional[str] = Field(None, description="自定义系统指令 (System Instructions)")
    max_tokens: Optional[int] = Field(None, ge=128, le=16384, description="最大生成 Token 数")
    top_p: Optional[float] = Field(1.0, ge=0.0, le=1.0, description="Top P 采样值")
