import re
import json
from typing import AsyncGenerator, List, Dict, Any, Optional
import httpx
from fastapi import HTTPException, status
from app.core.logger import logger
from app.model.models import LLMProviderModel
from app.schema.llm_schema import AIChatMessage

SYSTEM_PROMPT_FOR_LITEAPP = """你是一位顶尖的前端全栈专家与极简单文件微应用（Single-File Micro App）架构师。
你的任务是根据用户的需求，生成一段完整、健壮、可立即在浏览器中独立运行的单文件 HTML 代码。

【代码生成核心规则】
1. **完整单文件 HTML**：
   - 必须输出包含 `<!DOCTYPE html>`、`<html>`、`<head>`、`<body>` 的完整 HTML5 文档。
   - 严禁拆分为多个文件，严禁使用外部本地相对路径（如 href="style.css" 或 src="app.js"）。
   - 所有自定义样式置于 `<style>`，所有业务逻辑置于 `<script>`。

2. **UI 与现代设计系统**：
   - 必须在 `<head>` 中引入 TailwindCSS CDN：`<script src="https://cdn.tailwindcss.com"></script>`。
   - 必须引入 Lucide 图标库 CDN：`<script src="https://unpkg.com/lucide@latest"></script>`，并在页面脚本底部或 DOMContentLoaded 执行 `lucide.createIcons()`。
   - 采用现代专业质感设计：支持自适应响应式（移动端 + 桌面端）、细腻的交互微动效、优雅的深浅色配色、圆角与层次阴影。

3. **零构建环境依赖**：
   - 仅使用浏览器原生 JavaScript (ES6+) 或通过 CDN 引入的无构建库（如 Canvas、Chart.js 等）。
   - 严禁需要 Webpack/Vite/Babel 编译的语法或 require/import 本地模块。

4. **状态持久化与错误处理**：
   - 若涉及数据保存（如待办事项、历史记录、计算器历史、配置等），必须使用 `localStorage` 进行本地持久化。
   - 具备完备的边界处理与异常捕获，确保即使遇到非法输入也不会白屏崩溃。

5. **输出格式严格要求**：
   - 直接输出以 ```html 开头，以 ``` 结尾的代码块。
   - 不要包含多余的客套废话或分析说明，只输出核心代码块。
"""

async def stream_openai_chat(
    provider: LLMProviderModel,
    messages: List[AIChatMessage],
    temperature: float = 0.7,
    system_instruction: Optional[str] = None,
    max_tokens: Optional[int] = None,
    top_p: Optional[float] = 1.0,
) -> AsyncGenerator[str, None]:
    """
    通过 HTTPX 异步流式请求 OpenAI 兼容接口，并将增量数据以 SSE 格式对外推送
    
    :param provider: 当前选中的模型提供商配置
    :param messages: 用户对话上下文
    :param temperature: 采样温度
    :param system_instruction: 自定义系统指令 (System Instructions)
    :param max_tokens: 最大生成 Token 限制
    :param top_p: Top P 采样值
    :yields: SSE 标准格式行（如 data: {"content": "..."}\n\n）
    """
    base_url = provider.base_url.rstrip("/")
    url = f"{base_url}/chat/completions"

    # 构建带 System Prompt 的完整消息链路 (支持 Google AI Studio 自定义 System Instructions)
    sys_prompt = system_instruction.strip() if (system_instruction and system_instruction.strip()) else SYSTEM_PROMPT_FOR_LITEAPP
    formatted_messages = [{"role": "system", "content": sys_prompt}]
    for m in messages:
        if m.role != "system":
            formatted_messages.append({"role": m.role, "content": m.content})

    headers = {
        "Authorization": f"Bearer {provider.api_key}",
        "Content-Type": "application/json",
    }

    payload: Dict[str, Any] = {
        "model": provider.model_name,
        "messages": formatted_messages,
        "temperature": temperature,
        "top_p": top_p if top_p is not None else 1.0,
        "stream": True,
    }
    if max_tokens:
        payload["max_tokens"] = max_tokens

    logger.info(f"发起大模型流式调用: url={url}, model={provider.model_name}")

    timeout = httpx.Timeout(connect=15.0, read=120.0, write=15.0, pool=30.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            async with client.stream("POST", url, headers=headers, json=payload) as response:
                if response.status_code != 200:
                    err_body = await response.aread()
                    err_msg = f"上游大模型接口返回异常 HTTP {response.status_code}: {err_body.decode('utf-8', errors='ignore')}"
                    logger.error(err_msg)
                    yield f"data: {json.dumps({'error': err_msg}, ensure_ascii=False)}\n\n"
                    return

                async for line in response.aiter_lines():
                    if not line:
                        continue
                    line = line.strip()
                    if line.startswith("data: "):
                        data_str = line[6:].strip()
                        if data_str == "[DONE]":
                            yield "data: [DONE]\n\n"
                            break
                        try:
                            parsed = json.loads(data_str)
                            delta = parsed.get("choices", [{}])[0].get("delta", {})
                            content = delta.get("content", "")
                            if content:
                                sse_event = json.dumps({"content": content}, ensure_ascii=False)
                                yield f"data: {sse_event}\n\n"
                        except Exception:
                            # 忽略无法解析的心跳或特殊帧
                            continue
        except httpx.RequestError as exc:
            err_text = f"请求大模型接口网络失败: {exc}"
            logger.error(err_text)
            yield f"data: {json.dumps({'error': err_text}, ensure_ascii=False)}\n\n"

async def test_llm_connection(provider: LLMProviderModel) -> Dict[str, Any]:
    """
    轻量测试大模型提供商连接与 API Key 有效性
    """
    base_url = provider.base_url.rstrip("/")
    url = f"{base_url}/chat/completions"

    headers = {
        "Authorization": f"Bearer {provider.api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": provider.model_name,
        "messages": [
            {"role": "user", "content": "ping"}
        ],
        "max_tokens": 5,
    }

    timeout = httpx.Timeout(10.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            res = await client.post(url, headers=headers, json=payload)
            if res.status_code == 200:
                return {"success": True, "message": f"连接成功！HTTP {res.status_code}"}
            else:
                return {
                    "success": False,
                    "message": f"上游接口返回错误码 HTTP {res.status_code}: {res.text[:200]}"
                }
        except Exception as e:
            return {"success": False, "message": f"连接发生异常: {str(e)}"}

def extract_html_basic_metadata(html_content: str, filename: Optional[str] = None) -> Dict[str, str]:
    """
    通过正则快速提取 HTML 文件的标题、简介以及生成规范 Slug
    
    :param html_content: HTML 源码
    :param filename: 上传的原始文件名
    :returns: 包含 title, description, category, icon, slug, source 的字典
    """
    title = ""
    description = ""
    category = "实用小工具"
    icon = "🚀"
    slug = ""

    # 1. 提取 <title>...</title>
    title_match = re.search(r"<title\b[^>]*>(.*?)</title>", html_content, re.IGNORECASE | re.DOTALL)
    if title_match:
        candidate_title = re.sub(r"<[^>]+>", "", title_match.group(1)).strip()
        # 排除无意义的空标题或脚手架占位词
        if candidate_title.lower() not in {"document", "vite app", "react app", "vue app", "untitled", "index.html"}:
            title = candidate_title

    # 2. 提取 meta description 或 og:description
    desc_match = re.search(
        r'<meta\b[^>]*(?:name|property)=["\'](?:description|og:description)["\'][^>]*content=["\'](.*?)["\']',
        html_content,
        re.IGNORECASE | re.DOTALL
    )
    if not desc_match:
        # 兼容 content 属性在前的情形
        desc_match = re.search(
            r'<meta\b[^>]*content=["\'](.*?)["\'][^>]*(?:name|property)=["\'](?:description|og:description)["\']',
            html_content,
            re.IGNORECASE | re.DOTALL
        )
    if desc_match:
        description = desc_match.group(1).strip()

    # 3. 兜底标题生成
    if not title:
        if filename:
            title = re.sub(r"\.(html?|zip)$", "", filename, flags=re.IGNORECASE).replace("-", " ").replace("_", " ").title()
        else:
            title = "自定义微应用"

    # 4. 根据页面内容特征智能推荐分类与图标（优先分析标题，其次分析正文）
    lower_title = title.lower()
    lower_content = (html_content[:5000]).lower()

    if any(k in lower_title for k in ["时钟", "clock", "timer", "倒计时", "番茄", "pomodoro", "待办", "todo", "清单"]):
        category = "效率工具"
        icon = "⏱️"
    elif any(k in lower_title for k in ["游戏", "game", "snake", "贪吃蛇", "俄罗斯方块", "2048", "棋", "play"]):
        category = "小游戏"
        icon = "🎮"
    elif any(k in lower_title for k in ["图表", "chart", "数据", "统计", "看板", "dashboard", "visual"]):
        category = "数据可视化"
        icon = "📊"
    elif any(k in lower_title for k in ["计算器", "calc", "换算", "convert", "格式化", "format", "json", "tool"]):
        category = "开发辅助"
        icon = "🛠️"
    elif any(k in lower_content for k in ["pomodoro", "timer", "clock", "番茄", "倒计时", "时钟", "待办", "todo"]):
        category = "效率工具"
        icon = "⏱️"
    elif any(k in lower_content for k in ["game", "snake", "tetris", "游戏", "贪吃蛇", "俄罗斯方块", "2048", "canvas", "score"]):
        category = "小游戏"
        icon = "🎮"
    elif any(k in lower_content for k in ["chart", "echarts", "visual", "图表", "数据", "统计", "看板", "dashboard"]):
        category = "数据可视化"
        icon = "📊"
    elif any(k in lower_content for k in ["calc", "convert", "计算器", "换算", "汇率", "工具", "format", "json"]):
        category = "开发辅助"
        icon = "🛠️"
    elif any(k in lower_content for k in ["resume", "markdown", "简历", "笔记", "note", "editor"]):
        category = "效率工具"
        icon = "📝"

    # 5. 生成合规的 URL Slug
    if filename:
        raw_name = re.sub(r"\.(html?|zip)$", "", filename, flags=re.IGNORECASE).lower()
        cleaned_slug = re.sub(r"[^a-z0-9-_]", "-", raw_name).strip("-")
        if len(cleaned_slug) >= 2:
            slug = cleaned_slug[:30]

    if not slug:
        cleaned_slug = re.sub(r"[^a-z0-9-_]", "-", title.lower()).strip("-")
        if len(cleaned_slug) >= 2:
            slug = cleaned_slug[:30]
        else:
            import random
            slug = f"app-{random.randint(1000, 9999)}"

    if not description:
        description = f"{title} - 基于 HTML5 单页构建的轻量级微应用。"

    return {
        "title": title[:50],
        "description": description[:200],
        "category": category,
        "icon": icon,
        "slug": slug,
        "source": "html_tags"
    }

async def analyze_app_metadata_with_ai(
    html_content: str,
    filename: Optional[str] = None,
    provider: Optional[LLMProviderModel] = None,
) -> Dict[str, str]:
    """
    通过调用当前激活的 OpenAI 兼容接口，深度解析 HTML 代码并生成专业精准的名称、简介、分类与 Slug
    
    :param html_content: HTML 源码
    :param filename: 上传文件名
    :param provider: 大模型配置（若未提供则调用全局激活项）
    :returns: 包含 title, description, category, icon, slug, source 的字典
    """
    # 提取基础元数据作为备底保底
    fallback = extract_html_basic_metadata(html_content, filename)

    if not provider:
        from app.repository import llm_repo
        provider = llm_repo.get_active_provider()

    if not provider or not provider.api_key:
        logger.warning("未配置有效大模型 API Key，降级使用本地 HTML 标签提取")
        return fallback

    # 截取前 4000 个字符提供给 LLM 分析（过滤掉极长 base64）
    clean_sample = re.sub(r"data:image/[^;]+;base64,[A-Za-z0-9+/=]{100,}", "data:image/...[base64 omitted]", html_content)
    snippet = clean_sample[:4000]

    system_prompt = (
        "你是一位资深前端架构师与应用商店内容专家。"
        "请根据提供的微应用网页 HTML 源码，深刻理解其核心业务功能、设计风格与使用场景，并提炼输出其元信息。\n"
        "要求输出严格的纯 JSON 格式，字段如下：\n"
        "{\n"
        '  "title": "简练且吸引人的中文标题（3-12字，例如：赛博朋克番茄钟）",\n'
        '  "description": "一句清晰到位的功能介绍与亮点（30-80字）",\n'
        '  "category": "从以下类别中选取一个最贴切的：[效率工具, 实用小工具, 小游戏, 数据可视化, 影音娱乐, 娱乐日常, 开发辅助]",\n'
        '  "icon": "一个最匹配该功能的单个 Emoji 图标（如 ⏱️, 🎮, 📊, 🛠️, 📝 等）",\n'
        '  "slug": "2-25位小写英文字母、数字和短横线构成的URL标识（如 pomodoro-timer, retro-snake）"\n'
        "}\n"
        "注意：只输出纯 JSON，严禁输出任何多余的 Markdown 标记或前后解释！"
    )

    user_prompt = f"【文件名】: {filename or 'index.html'}\n【HTML源码片段】:\n```html\n{snippet}\n```"

    base_url = provider.base_url.rstrip("/")
    url = f"{base_url}/chat/completions"
    headers = {
        "Authorization": f"Bearer {provider.api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": provider.model_name,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.3,
        "max_tokens": 400,
    }

    timeout = httpx.Timeout(15.0)
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            res = await client.post(url, headers=headers, json=payload)
            if res.status_code == 200:
                data = res.json()
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
                
                # 尝试提取 JSON 内容
                json_match = re.search(r"\{[\s\S]*\}", content)
                if json_match:
                    parsed = json.loads(json_match.group(0))
                    return {
                        "title": str(parsed.get("title") or fallback["title"])[:50],
                        "description": str(parsed.get("description") or fallback["description"])[:200],
                        "category": str(parsed.get("category") or fallback["category"])[:20],
                        "icon": str(parsed.get("icon") or fallback["icon"])[:10],
                        "slug": re.sub(r"[^a-z0-9-_]", "-", str(parsed.get("slug") or fallback["slug"]).lower()).strip("-")[:30] or fallback["slug"],
                        "source": "ai_generated"
                    }
    except Exception as e:
        logger.warning(f"大模型解析元信息请求异常，降级使用标签提取: {e}")

    return fallback

async def generate_field_with_ai(
    field_type: str,
    context: str,
    provider: Optional[LLMProviderModel] = None,
) -> str:
    """
    针对输入框场景（应用简介、智能体角色提示词、标题等）提供即时 AI 生成与扩写优化
    """
    if not provider:
        from app.repository import llm_repo
        provider = llm_repo.get_active_provider()

    clean_ctx = context.strip()

    # 1. 如果大模型可用且配置了非占位 API Key，发起快速提示词请求
    has_valid_key = bool(
        provider 
        and provider.api_key 
        and not any(fake in provider.api_key.lower() for fake in ["sk-xxx", "test", "example", "placeholder"])
    )
    if has_valid_key:
        if field_type == "prompt":
            sys_prompt = (
                "你是一位资深 Prompt 工程师与 AI 智能体架构师。"
                "请将用户输入的简要需求扩写为专业、结构清晰、具备严谨约束的高质量 System Prompt（角色设定）。\n"
                "内容应包含：【角色定位】、【专业能力与职责】、【交互与思考原则】、【输出格式规范】。\n"
                "要求用纯中文，不要输出任何额外的问候或包裹说明，直接输出 System Prompt 正文。"
            )
        elif field_type == "description":
            sys_prompt = (
                "你是一位出色的产品文案专家。"
                "请根据用户提供的主题或功能词，生成 1-2 句言简意赅、富有科技感且清晰明了的简介（30-80字）。\n"
                "直接输出简介文本，严禁包含多余修饰。"
            )
        elif field_type == "title":
            sys_prompt = (
                "你是一位产品起名专家。"
                "请根据用户需求，提炼一个简短、富有记忆点的中文应用或智能体名称（4-10字）。\n"
                "直接输出名称文本即可。"
            )
        else:
            sys_prompt = "请根据用户需求进行精简高质量的文本生成，直接输出正文。"

        url = f"{provider.base_url.rstrip('/')}/chat/completions"
        headers = {
            "Authorization": f"Bearer {provider.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": provider.model_name,
            "messages": [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": clean_ctx}
            ],
            "temperature": 0.7,
            "max_tokens": 800 if field_type == "prompt" else 150,
        }

        try:
            timeout = httpx.Timeout(4.0, connect=1.5)
            async with httpx.AsyncClient(timeout=timeout) as client:
                res = await client.post(url, headers=headers, json=payload)
                if res.status_code == 200:
                    text = res.json().get("choices", [{}])[0].get("message", {}).get("content", "").strip()
                    if text:
                        return text
        except Exception as e:
            logger.warning(f"AI 字段生成请求异常，启用本地模板兜底: {e}")

    # 2. 本地高质量规则与模板兜底 (保证 100% 可用)
    if field_type == "prompt":
        if any(k in clean_ctx.lower() for k in ["n8n", "工作流", "workflow", "自动化"]):
            return (
                "你是一位资深的 n8n 自动化工作流架构专家与全栈集成顾问。\n\n"
                "【核心定位与使命】\n"
                "你精通 n8n 的底层节点架构、连接拓扑、数据表达式（$json/$node）以及官方 REST API 规范。你的使命是协助用户设计高可用、容错性强的自动化工作流，并生成可直接导入或通过 API 部署的合法 JSON。\n\n"
                "【专业技能与知识库】\n"
                "1. 节点设计：熟练运用 Webhook、Cron (Schedule Trigger)、HTTP Request、Code (JavaScript/Python)、Switch、Filter、Merge 等核心节点。\n"
                "2. 错误处理与重试机制：主动建议配置 Error Trigger 与自动重试逻辑。\n"
                "3. API 集成能力：严格遵循 n8n POST /api/v1/workflows 的 Payload 规范，输出包含合法 nodes 数组与 connections 拓扑对象的结构。\n\n"
                "【输出格式规范】\n"
                "- 对话中遇到工作流设计需求，先清晰解释工作流逻辑流程与所需凭据。\n"
                "- 然后输出标准合法的 ```json 代码块，并提供关键参数的配置指引。"
            )
        elif any(k in clean_ctx.lower() for k in ["法律", "合同", "合规", "法务"]):
            return (
                "你是一位资深中国执业律师与企业法务合规顾问。\n\n"
                "【职责与原则】\n"
                "1. 专注于公司法、劳动合同法、民商事合同审查与知识产权保护。\n"
                "2. 提供严谨、有条理、引用法条条款的分析意见。\n"
                "3. 遇到潜在法律风险主动标红预警，并提供切实可行的防范修改建议。"
            )
        else:
            return (
                f"你是一位专注于【{clean_ctx}】领域的专业智能专家顾问。\n\n"
                "【角色设定与职责】\n"
                f"1. 具备深厚的{clean_ctx}专业知识体系，善于将复杂需求拆解为结构化方案。\n"
                "2. 始终使用专业、客观、富有启发性的中文进行解答。\n"
                "3. 回答条理清晰，善于使用要点列表与实际示例，确保用户能够直接落地应用。"
            )
    elif field_type == "description":
        return f"专注于{clean_ctx}场景的专业智能助手，提供精准高效的交互与解决方案。"
    elif field_type == "title":
        return f"{clean_ctx[:8]}智能专家"

    return clean_ctx

async def generate_agent_suite_with_ai(
    context: str,
    provider: Optional[LLMProviderModel] = None,
) -> Dict[str, Any]:
    """
    根据用户的一句概念描述，一键全自动构思并生成整套智能体配置 (含标题、图标、角色提示词、问候语、推荐问题、Skills、Tools)
    """
    clean_ctx = context.strip()
    is_n8n_related = any(k in clean_ctx.lower() for k in ["n8n", "工作流", "workflow", "自动化", "集成"])

    # 预设 n8n 标杆套件
    if is_n8n_related:
        return {
            "title": "n8n 工作流架构师",
            "icon": "⚡",
            "description": "智能设计、排查并一键向 n8n 实例发布高可用自动化工作流的专业顾问",
            "category": "自动化流",
            "system_prompt": (
                "你是一位顶尖的 n8n 自动化工作流架构专家与全栈集成顾问。\n\n"
                "【核心定位与使命】\n"
                "你精通 n8n 的底层节点架构、连接拓扑、数据流转表达式（$json/$node）以及官方 REST API 规范。你的使命是根据用户的自然语言业务需求，设计出高内聚、易维护的自动化工作流，并输出标准合法的完整工作流 JSON。\n\n"
                "【专业技能与知识库 (Skills)】\n"
                "1. 核心触发器：熟练配置 Webhook、Schedule Trigger (Cron)、Email Read 等。\n"
                "2. 数据处理与转换：精通 Code (JS/Python)、Edit Fields (Set)、Filter、Item Lists、Merge 等操作。\n"
                "3. 外部系统对接：熟练配置 HTTP Request、飞书/钉钉机器人、Postgres/MySQL 数据库操作。\n"
                "4. 错误捕获：主动引入 Error Trigger 节点保障生产环境健壮性。\n\n"
                "【工具集成 (Tools) 与 API 规范】\n"
                "当用户确认要部署或测试工作流时，输出标准的 n8n POST /api/v1/workflows 所需格式：\n"
                "```json\n"
                "{\n"
                '  "name": "工作流名称",\n'
                '  "nodes": [...],\n'
                '  "connections": {...},\n'
                '  "settings": { "executionOrder": "v1" }\n'
                "}\n"
                "```\n"
                "并指导用户可在本页面右上角「API与工具设置」中填入 n8n Instance URL 与 X-N8N-API-KEY，由系统通过 API 代理直接一键完成实例部署！"
            ),
            "welcome_message": "您好！我是您的 n8n 工作流架构师。请告诉我您想实现的自动化流程（例如：“定时抓取每日新闻推送到飞书”或“监控 GitHub Release 并发送邮件”），我将为您生成标准工作流并支持一键部署到您的 n8n 实例！",
            "quick_prompts": [
                "帮我设计一个定时抓取 GitHub Trending 推送通知的工作流",
                "如何通过 Webhook 节点接收表单提交数据并写入数据库",
                "写一个自动重试和错误报警的标准化子工作流",
                "帮我排查当前工作流 JSON 语法与连接关系"
            ],
            "skills": ["n8n-workflow-spec", "json-schema-validation", "cron-trigger-rules"],
            "tools": [
                {
                    "name": "create_n8n_workflow",
                    "label": "一键推送创建至 n8n 实例",
                    "description": "调用 n8n 官方 REST API (POST /api/v1/workflows) 创建工作流",
                    "endpoint": "https://n8n.your-domain.com/api/v1/workflows",
                    "method": "POST",
                    "headers": {
                        "X-N8N-API-KEY": "",
                        "Content-Type": "application/json"
                    },
                    "parameters_schema": {
                        "name": "工作流名称",
                        "nodes": "节点数组",
                        "connections": "连接映射"
                    }
                }
            ]
        }

    # 如果有大模型，让大模型生成结构化 JSON
    if not provider:
        from app.repository import llm_repo
        provider = llm_repo.get_active_provider()

    has_valid_key = bool(
        provider 
        and provider.api_key 
        and not any(fake in provider.api_key.lower() for fake in ["sk-xxx", "test", "example", "placeholder"])
    )
    if has_valid_key:
        sys_prompt = (
            "你是一位资深 AI Agent 产品架构师。"
            "请根据用户的粗略想法，全套构思并设计一个专业的智能体应用。\n"
            "要求必须输出严格的纯 JSON 格式，包含以下字段：\n"
            "{\n"
            '  "title": "智能体名称（4-10字）",\n'
            '  "icon": "匹配的单个 Emoji 图标",\n'
            '  "description": "功能简介（30-80字）",\n'
            '  "category": "类别，如：AI助手/效率工具/开发辅助/数据分析/自动化流",\n'
            '  "system_prompt": "工业级专业的 System Prompt 角色设定（200-500字）",\n'
            '  "welcome_message": "富有亲和力的首句欢迎语",\n'
            '  "quick_prompts": ["推荐提问1", "推荐提问2", "推荐提问3"],\n'
            '  "skills": ["技能标识1", "技能标识2"],\n'
            '  "tools": [\n'
            '    {\n'
            '      "name": "工具英文名",\n'
            '      "label": "工具中文名",\n'
            '      "description": "工具用途说明",\n'
            '      "endpoint": "https://api.example.com/endpoint",\n'
            '      "method": "POST",\n'
            '      "headers": {},\n'
            '      "parameters_schema": {}\n'
            '    }\n'
            '  ]\n'
            "}\n"
            "只输出纯 JSON，严禁输出任何多余说明！"
        )

        url = f"{provider.base_url.rstrip('/')}/chat/completions"
        headers = {
            "Authorization": f"Bearer {provider.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": provider.model_name,
            "messages": [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": clean_ctx}
            ],
            "temperature": 0.5,
            "max_tokens": 1000,
        }

        try:
            timeout = httpx.Timeout(20.0)
            async with httpx.AsyncClient(timeout=timeout) as client:
                res = await client.post(url, headers=headers, json=payload)
                if res.status_code == 200:
                    content = res.json().get("choices", [{}])[0].get("message", {}).get("content", "").strip()
                    json_match = re.search(r"\{[\s\S]*\}", content)
                    if json_match:
                        parsed = json.loads(json_match.group(0))
                        return {
                            "title": str(parsed.get("title") or f"{clean_ctx[:6]}助手")[:30],
                            "icon": str(parsed.get("icon") or "🤖")[:10],
                            "description": str(parsed.get("description") or f"专注于{clean_ctx}的专属智能助手")[:200],
                            "category": str(parsed.get("category") or "AI助手")[:20],
                            "system_prompt": str(parsed.get("system_prompt") or f"你是一个专业的{clean_ctx}助手。"),
                            "welcome_message": str(parsed.get("welcome_message") or f"您好！我是您的{clean_ctx}助手，有什么可以协助您？"),
                            "quick_prompts": list(parsed.get("quick_prompts") or ["请帮我分析当前需求", "列出主要实施步骤"]),
                            "skills": list(parsed.get("skills") or ["domain-expert"]),
                            "tools": list(parsed.get("tools") or []),
                        }
        except Exception as e:
            logger.warning(f"大模型全套智能体构思异常，启用本地通用兜底: {e}")

    # 通用本地兜底
    title = f"{clean_ctx[:8]}专业助手" if len(clean_ctx) <= 12 else "定制领域专属智能体"
    return {
        "title": title,
        "icon": "🤖",
        "description": f"专为{clean_ctx}打造的智能对话与分析助手，提供全流程指导与方案生成。",
        "category": "AI助手",
        "system_prompt": (
            f"你是一位精通【{clean_ctx}】领域的专业智能架构师。\n\n"
            "【角色设定】\n"
            "1. 具备深厚且严谨的专业知识，回答结构分明、逻辑清晰。\n"
            "2. 主动运用最佳实践引导用户，提出前瞻性建议与风险提示。\n"
            "3. 遇到代码、配置或数据格式时，严格提供规范清晰的示例展示。"
        ),
        "welcome_message": f"您好！我是您的专属【{title}】。请问今天有什么我可以帮您的？",
        "quick_prompts": [
            f"请帮我梳理关于{clean_ctx}的核心要点",
            "帮我列一个完整的执行方案清单",
            "检查我的方案并提出优化建议"
        ],
        "skills": ["domain-knowledge", "problem-solving"],
        "tools": []
    }
