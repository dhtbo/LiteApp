import re
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, field_validator, model_validator

SLUG_REGEX = re.compile(r"^[a-z0-9][a-z0-9-_]{1,49}$")

class AppCreateRequest(BaseModel):
    """
    新建微应用请求模型
    """
    slug: str = Field(..., description="应用唯一标识 Slug (英文字母小写、数字、下划线及短横线)")
    title: str = Field(..., min_length=1, max_length=100, description="应用名称")
    description: Optional[str] = Field("", max_length=500, description="应用简介")
    category: Optional[str] = Field("通用", max_length=50, description="分类标签")
    icon: Optional[str] = Field("🚀", max_length=30, description="图标或 Emoji")
    html_content: Optional[str] = Field(None, description="内联单文件 HTML 代码（纯代码创建模式）")

    @field_validator("slug")
    def validate_slug(cls, v: str) -> str:
        clean_slug = v.strip().lower()
        if not SLUG_REGEX.match(clean_slug):
            raise ValueError("Slug 必须由 2-50 位小写英文字母、数字、短横线(-)或下划线(_)组成，且必须以英文字母或数字开头")
        if clean_slug in {"api", "s", "static", "docs", "redoc", "openapi", "admin"}:
            raise ValueError(f"'{clean_slug}' 为系统保留关键字，不能作为应用 Slug")
        return clean_slug

class AppUpdateRequest(BaseModel):
    """
    更新微应用元信息请求模型
    """
    title: Optional[str] = Field(None, min_length=1, max_length=100, description="应用名称")
    description: Optional[str] = Field(None, max_length=500, description="应用简介")
    category: Optional[str] = Field(None, max_length=50, description="分类标签")
    icon: Optional[str] = Field(None, max_length=30, description="图标或 Emoji")

class AppResponse(BaseModel):
    """
    微应用返回数据模型
    """
    id: int
    slug: str
    title: str
    description: str
    category: str
    icon: str
    entry_type: str
    view_count: int
    created_at: str
    updated_at: str
    url_path: str = Field("", description="微应用可访问的相对路径，例如 /s/my-app/")

class AppListResponse(BaseModel):
    """
    微应用列表响应模型
    """
    total: int
    items: List[AppResponse]
    categories: List[str]

class AppSourceResponse(BaseModel):
    """
    微应用源码与元数据（用于在 AI 工坊中再次编辑）
    """
    slug: str
    title: str
    description: str
    category: str
    icon: str
    entry_type: str
    html_content: str

class AppVersionResponse(BaseModel):
    """
    微应用版本快照响应模型
    """
    id: int
    app_slug: str
    version_num: int
    entry_type: str
    description: str
    created_at: str

class AppMetadataInspectRequest(BaseModel):
    """
    请求提取或 AI 生成应用元信息
    """
    html_content: Optional[str] = Field(None, description="HTML 代码文本片段")
    filename: Optional[str] = Field(None, description="文件原始名称")
    use_ai: bool = Field(False, description="是否启用大模型深度提炼与生成")

class AppMetadataInspectResponse(BaseModel):
    """
    提取或 AI 生成的应用元信息结果
    """
    title: str = Field(..., description="应用标题")
    description: str = Field(..., description="应用简介")
    category: str = Field("通用", description="推荐分类")
    icon: str = Field("🚀", description="推荐图标 Emoji")
    slug: str = Field(..., description="推荐的 URL 标识 Slug")
    source: str = Field("html_tags", description="来源方式: html_tags(本地标签提取) 或 ai_generated(AI大模型生成)")

# ==================== 智能体高级功能扩展模型 ====================

class ToolDefinition(BaseModel):
    """
    智能体调用的 API 工具定义
    """
    name: str = Field(..., description="工具唯一英文标识，如 create_n8n_workflow")
    label: str = Field(..., description="工具友好中文名称，如 创建 n8n 工作流")
    description: str = Field("", description="工具功能描述，指导大模型在何种场景下调用")
    endpoint: str = Field(..., description="目标 API 请求地址 (支持 https://...)")
    method: str = Field("POST", description="HTTP 请求方式: GET, POST, PUT, DELETE")
    headers: Optional[Dict[str, str]] = Field(default_factory=dict, description="预设或自定义请求头")
    parameters_schema: Optional[Dict[str, Any]] = Field(default_factory=dict, description="参数 JSON Schema 定义")

class MCPServerConfig(BaseModel):
    """
    智能体挂载的 MCP 服务器配置
    """
    name: str = Field(..., description="MCP 服务标识名称")
    server_url: str = Field(..., description="MCP 服务连接地址")
    description: Optional[str] = Field("", description="服务描述")
    tools: Optional[List[str]] = Field(default_factory=list, description="启用的 MCP 工具列表")

class AgentAppGenerateRequest(BaseModel):
    """
    自定义 AI 智能体对话单页生成请求 (含 MCP、API 与 Skills 扩展)
    """
    title: str = Field(..., min_length=1, max_length=100, description="智能体助手名称")
    description: Optional[str] = Field("", max_length=500, description="助手功能简介")
    icon: Optional[str] = Field("🤖", max_length=30, description="助手图标 Emoji")
    category: Optional[str] = Field("AI助手", max_length=50, description="分类")
    system_prompt: str = Field("你是一个专业、严谨且富有亲和力的智能助手，请用清晰结构化的高质量中文回答用户的问题。", description="角色设定与系统提示词")
    welcome_message: Optional[str] = Field("你好！我是你的专属 AI 助手。请问今天有什么我可以帮你的？", description="初始问候语")
    quick_prompts: Optional[List[str]] = Field(default_factory=lambda: ["帮我列一个工作计划", "润色以下文字", "帮我撰写邮件回复"], description="推荐快捷引导提问")
    provider_id: Optional[int] = Field(None, description="绑定的系统 LLM 提供商 ID，留空使用当前系统激活模型")
    slug: Optional[str] = Field(None, description="指定的 slug，留空由系统自动生成")
    
    # 高级功能扩展
    skills: Optional[List[str]] = Field(default_factory=list, description="绑定的 Skills 技能包或预设标识，如 ['n8n_workflow', 'python_data']")
    tools: Optional[List[ToolDefinition]] = Field(default_factory=list, description="接入的 API 工具配置列表")
    mcp_servers: Optional[List[MCPServerConfig]] = Field(default_factory=list, description="接入的 MCP 服务配置列表")

class N8nAppGenerateRequest(BaseModel):
    """
    n8n Chat 嵌入或 Webhook 交互看板生成请求
    """
    title: str = Field(..., min_length=1, max_length=100, description="应用名称")
    description: Optional[str] = Field("", max_length=500, description="应用简介")
    icon: Optional[str] = Field("⚡", max_length=30, description="图标 Emoji")
    category: Optional[str] = Field("自动化流", max_length=50, description="分类")
    mode: str = Field("chat", description="模式: 'chat'(嵌入官方 n8n Chat) 或 'webhook'(表单触发与结果看板)")
    webhook_url: str = Field(..., description="n8n Webhook 或 Chat 的完整 HTTP/HTTPS 目标地址")
    http_method: Optional[str] = Field("POST", description="HTTP 请求方式 (POST/GET)")
    fields: Optional[List[Dict[str, Any]]] = Field(default_factory=list, description="入参字段定义列表")
    slug: Optional[str] = Field(None, description="指定的 slug，留空由系统自动生成")

class FormGeneratePromptRequest(BaseModel):
    """
    根据自然语言需求描述智能生成采集表单
    """
    title: str = Field(..., min_length=1, max_length=100, description="表单应用名称")
    description: Optional[str] = Field("", max_length=500, description="表单说明与填写引导")
    icon: Optional[str] = Field("📝", max_length=30, description="图标 Emoji")
    category: Optional[str] = Field("数据收集", max_length=50, description="分类")
    prompt: str = Field(..., min_length=5, description="表单需求描述，如：活动报名表，包含姓名、手机、部门、是否需要接送等")
    webhook_url: Optional[str] = Field(None, description="数据提交后异步推送的目标 Webhook URL")
    slug: Optional[str] = Field(None, description="指定的 slug，留空由系统自动生成")

class GeneratedAppResult(BaseModel):
    """
    应用生成结果模型
    """
    slug: str
    title: str
    description: str
    category: str
    icon: str
    html_content: str

# ==================== 输入框 AI 智能生成与代理调用模型 ====================

class FieldAIGenerateRequest(BaseModel):
    """
    输入框辅助 AI 生成请求模型
    """
    field_type: Optional[str] = Field("agent_suite", description="生成目标字段类型: 'prompt'(提示词), 'description'(简介), 'title'(标题与slug), 'agent_suite'(整套智能体构思)")
    context: str = Field(..., min_length=1, description="当前输入的内容、粗略概念或需求描述")
    provider_id: Optional[int] = Field(None, description="可选指定的大模型配置 ID")

class FieldAIGenerateResponse(BaseModel):
    """
    输入框 AI 辅助生成单字段响应
    """
    field_type: str
    content: str
    generated_content: Optional[str] = None

class AgentSuiteGenerateResponse(BaseModel):
    """
    一键 AI 生成整套智能体配置响应
    """
    title: str
    icon: str
    description: str
    category: str
    system_prompt: str
    welcome_message: str
    quick_prompts: List[str]
    skills: List[str]
    tools: List[ToolDefinition]

class AgentProxyCallRequest(BaseModel):
    """
    智能体后端通用 API 代理调用中继请求
    """
    url: Optional[str] = Field(None, description="目标 API 的完整 URL 地址")
    endpoint: Optional[str] = Field(None, description="兼容目标 API 别名字段")
    method: str = Field("POST", description="HTTP 请求方式 (POST/GET/PUT/DELETE)")
    headers: Optional[Dict[str, str]] = Field(default_factory=dict, description="传递给目标 API 的 Header (如 API Key)")
    payload: Optional[Dict[str, Any]] = Field(default_factory=dict, description="请求体 JSON 数据")

    @model_validator(mode="after")
    def resolve_url(self):
        if not self.url and not self.endpoint:
            raise ValueError("必须提供目标地址 url 或 endpoint")
        if not self.url and self.endpoint:
            self.url = self.endpoint
        return self
