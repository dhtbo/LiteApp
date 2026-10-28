import io
import csv
import json
import re
from typing import List, Dict, Any, Optional
from fastapi import HTTPException, status
import openpyxl

from app.core.logger import logger
from app.schema.app_schema import (
    AgentAppGenerateRequest,
    N8nAppGenerateRequest,
    FormGeneratePromptRequest,
    GeneratedAppResult,
)

def sanitize_slug(name: str) -> str:
    """
    将中文或混合名称转为合法的 URL slug 候选字符串 (只允许 a-z, 0-9, -, _，且以英文字母或数字开头)
    """
    import random
    clean = re.sub(r"[^a-zA-Z0-9\s-_]", "", name.lower())
    clean = re.sub(r"[-\s]+", "-", clean).strip("-_")
    if not clean or len(clean) < 2 or not clean[0].isalnum():
        ascii_words = re.findall(r"[a-z0-9]+", name.lower())
        if ascii_words and len(ascii_words[0]) >= 2:
            clean = f"{ascii_words[0]}-{random.randint(1000, 9999)}"
        else:
            clean = f"app-{random.randint(1000, 9999)}"
    return clean[:40]

def parse_table_file_to_fields(file_bytes: bytes, filename: str) -> List[Dict[str, Any]]:
    """
    读取上传的 CSV 或 Excel 文件，提取表头及类型推断
    """
    fields: List[Dict[str, Any]] = []
    filename_lower = filename.lower()

    try:
        if filename_lower.endswith(".csv"):
            try:
                text_content = file_bytes.decode("utf-8")
            except UnicodeDecodeError:
                text_content = file_bytes.decode("gbk", errors="ignore")

            reader = csv.reader(io.StringIO(text_content))
            rows = [r for r in reader if r]
            if not rows:
                raise ValueError("CSV 文件内容为空")
            headers = [h.strip() for h in rows[0] if h.strip()]
            sample_rows = rows[1:6]

        elif filename_lower.endswith((".xlsx", ".xls")):
            wb = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True)
            sheet = wb.active
            rows = []
            for row in sheet.iter_rows(values_only=True):
                if any(v is not None for v in row):
                    rows.append([str(v).strip() if v is not None else "" for v in row])
            if not rows:
                raise ValueError("Excel 工作表中未检测到有效数据")
            headers = [h for h in rows[0] if h]
            sample_rows = rows[1:6]
        else:
            raise ValueError("仅支持 .csv 或 .xlsx 格式文件")

        for idx, header in enumerate(headers):
            # 采样推断类型
            sample_values = [r[idx] for r in sample_rows if len(r) > idx and r[idx]]
            field_type = "text"
            placeholder = f"请输入{header}"

            # 关键字与样本推断
            header_lower = header.lower()
            if any(k in header_lower for k in ["邮箱", "email", "mail"]):
                field_type = "email"
                placeholder = "example@domain.com"
            elif any(k in header_lower for k in ["电话", "手机", "phone", "mobile", "tel"]):
                field_type = "tel"
                placeholder = "13800000000"
            elif any(k in header_lower for k in ["日期", "时间", "date", "time", "生日", "创建时间"]):
                field_type = "date"
            elif any(k in header_lower for k in ["备注", "详情", "简介", "评价", "说明", "desc", "remark", "content"]):
                field_type = "textarea"
            elif any(k in header_lower for k in ["数量", "金额", "年龄", "价格", "评分", "count", "num", "price", "age"]):
                field_type = "number"
            elif any(k in header_lower for k in ["是否", "需要", "同意", "is_", "has_"]):
                field_type = "select"

            # 安全变量名
            var_name = f"field_{idx+1}"
            english_chars = re.sub(r"[^a-zA-Z0-9_]", "", header)
            if english_chars and len(english_chars) >= 2:
                var_name = english_chars.lower()

            fields.append({
                "id": var_name,
                "label": header,
                "type": field_type,
                "placeholder": placeholder,
                "required": idx == 0,  # 默认首列必填
                "options": ["是", "否"] if field_type == "select" else [],
            })

        return fields

    except Exception as e:
        logger.error(f"解析表格文件失败: filename={filename}, err={e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"解析表格失败: {str(e)}"
        )

# ==================== 智能体单页代码模板 ====================

SKILL_KNOWLEDGE_MAP = {
    "n8n-workflow-spec": (
        "【挂载技能 Skill: n8n 工作流架构规范】\n"
        "- 节点连接拓扑结构：'connections': { 'Node A': { 'main': [ [ { 'node': 'Node B', 'type': 'main', 'index': 0 } ] ] } }\n"
        "- 常见节点：n8n-nodes-base.webhook, n8n-nodes-base.scheduleTrigger, n8n-nodes-base.httpRequest, n8n-nodes-base.code\n"
        "- 数据引用语法：使用 {{ $json.field_name }} 引用当前节点的输入字段\n"
        "- 输出必须是合法可解析的完整工作流 JSON，严禁尾随逗号或注释破坏语法。"
    ),
    "json-schema-validation": (
        "【挂载技能 Skill: JSON 规范与参数校验】\n"
        "- 严格保证所有数据输出符合 JSON RFC 8259 规范，结构清晰，属性名必须双引号包裹。"
    ),
    "cron-trigger-rules": (
        "【挂载技能 Skill: 定时触发器 Cron 规则】\n"
        "- 支持标准 5/6 段表达式，例如：0 9 * * * (每天早晨9点)；*/15 * * * * (每15分钟)。"
    ),
}

def generate_agent_app_html(req: AgentAppGenerateRequest) -> GeneratedAppResult:
    """
    生成独立 AI 智能体对话单页应用 (含 MCP、API 工具与 Skills 高级扩展能力)
    """
    slug = req.slug or sanitize_slug(req.title)
    
    # 1. 组装 Skills 补充知识
    extended_system_prompt = req.system_prompt
    if req.skills:
        skill_texts = []
        for s in req.skills:
            if s in SKILL_KNOWLEDGE_MAP:
                skill_texts.append(SKILL_KNOWLEDGE_MAP[s])
            else:
                skill_texts.append(f"【挂载技能 Skill: {s}】")
        extended_system_prompt += "\n\n" + "\n\n".join(skill_texts)

    # 2. 如果配置了 Tools，将工具列表说明也融入 System Prompt
    tools_list = [t.model_dump() if hasattr(t, "model_dump") else t for t in (req.tools or [])]
    if tools_list:
        tools_desc = "\n".join([f"- 工具标识: {t.get('name')}, 说明: {t.get('description')}, 请求方式: {t.get('method')} {t.get('endpoint')}" for t in tools_list])
        extended_system_prompt += f"\n\n【可用工具集 Tools】\n你拥有以下外部 API 与工具调用支持：\n{tools_desc}\n当用户需要执行这些操作时，请输出明确对应的 JSON 参数供系统执行。"

    quick_prompts_json = json.dumps(req.quick_prompts or [], ensure_ascii=False)
    system_prompt_escaped = json.dumps(extended_system_prompt, ensure_ascii=False)
    welcome_msg_escaped = json.dumps(req.welcome_message or "你好！有什么我可以帮你的？", ensure_ascii=False)
    provider_id_val = str(req.provider_id) if req.provider_id is not None else "null"
    tools_json = json.dumps(tools_list, ensure_ascii=False)
    skills_json = json.dumps(req.skills or [], ensure_ascii=False)
    mcp_servers_json = json.dumps([m.model_dump() if hasattr(m, "model_dump") else m for m in (req.mcp_servers or [])], ensure_ascii=False)

    html_code = f"""<!DOCTYPE html>
<html lang="zh-CN" class="dark">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{req.title} - AI 智能助手</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <script src="https://unpkg.com/lucide@latest"></script>
  <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
  <script src="https://cdn.jsdelivr.net/gh/highlightjs/cdn-release@11.9.0/build/highlight.min.js"></script>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/highlightjs/cdn-release@11.9.0/build/styles/github-dark.min.css">
  <script>
    tailwind.config = {{
      darkMode: 'class',
      theme: {{
        extend: {{
          colors: {{
            brand: {{ 50: '#eef2ff', 500: '#6366f1', 600: '#4f46e5', 700: '#4338ca' }}
          }}
        }}
      }}
    }}
  </script>
  <style>
    pre code.hljs {{ padding: 0.75rem; border-radius: 0.5rem; }}
    .markdown-body pre {{ background: #0f172a !important; margin: 0.5rem 0; border: 1px solid #1e293b; border-radius: 0.5rem; overflow-x: auto; position: relative; }}
    .markdown-body p {{ margin-bottom: 0.5rem; line-height: 1.6; }}
    .markdown-body p:last-child {{ margin-bottom: 0; }}
    .markdown-body ul, .markdown-body ol {{ padding-left: 1.25rem; margin-bottom: 0.5rem; }}
    .markdown-body ul {{ list-style-type: disc; }}
    .markdown-body ol {{ list-style-type: decimal; }}
    .typing-cursor::after {{ content: '▋'; animation: blink 1s infinite; margin-left: 2px; color: #818cf8; }}
    @keyframes blink {{ 0%, 100% {{ opacity: 1; }} 50% {{ opacity: 0; }} }}
    .workflow-action-bar {{ display: flex; align-items: center; justify-content: flex-end; gap: 0.5rem; padding: 0.4rem 0.6rem; background: #1e293b; border-top: 1px solid #334155; border-bottom-left-radius: 0.5rem; border-bottom-right-radius: 0.5rem; }}
  </style>
</head>
<body class="bg-slate-950 text-slate-100 flex flex-col h-screen overflow-hidden selection:bg-indigo-500 selection:text-white">

  <!-- 顶部导航栏 -->
  <header class="h-14 border-b border-slate-800 bg-slate-900/80 backdrop-blur px-4 flex items-center justify-between z-10 shrink-0">
    <div class="flex items-center space-x-3">
      <div class="w-9 h-9 rounded-xl bg-indigo-600/20 border border-indigo-500/30 flex items-center justify-center text-xl shrink-0">
        {req.icon}
      </div>
      <div>
        <h1 class="text-sm font-semibold tracking-wide flex items-center gap-1.5">
          {req.title}
          <span class="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">Online</span>
        </h1>
        <p class="text-xs text-slate-400 truncate max-w-xs">{req.description or '专属智能对话助理'}</p>
      </div>
    </div>
    <div class="flex items-center space-x-2">
      <!-- 工具与扩展配置抽屉按钮 -->
      <button id="openToolsDrawerBtn" class="text-xs px-2.5 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 flex items-center gap-1.5 transition-colors" title="查看或配置接入的 API、MCP 工具与 Skills">
        <i data-lucide="wrench" class="w-3.5 h-3.5 text-indigo-400"></i>
        <span>工具与扩展</span>
        <span id="toolsBadge" class="w-1.5 h-1.5 rounded-full bg-emerald-400"></span>
      </button>
      <button id="clearChatBtn" title="清空对话" class="p-2 text-slate-400 hover:text-slate-200 hover:bg-slate-800 rounded-lg transition-colors">
        <i data-lucide="trash-2" class="w-4 h-4"></i>
      </button>
      <button id="helpBtn" title="角色设定" class="p-2 text-slate-400 hover:text-slate-200 hover:bg-slate-800 rounded-lg transition-colors">
        <i data-lucide="info" class="w-4 h-4"></i>
      </button>
    </div>
  </header>

  <!-- 消息滚动列表 -->
  <main id="chatContainer" class="flex-1 overflow-y-auto p-4 md:p-6 space-y-4 max-w-4xl w-full mx-auto">
    <!-- 欢迎卡片 -->
    <div class="flex gap-3 items-start animate-fade-in">
      <div class="w-8 h-8 rounded-lg bg-indigo-600/20 border border-indigo-500/30 flex items-center justify-center shrink-0 text-base">
        {req.icon}
      </div>
      <div class="bg-slate-900 border border-slate-800 rounded-2xl rounded-tl-sm px-4 py-3 max-w-[85%] text-sm shadow-sm leading-relaxed">
        <div class="markdown-body" id="welcomeMsg"></div>
        <div id="quickPromptBox" class="mt-3 pt-3 border-t border-slate-800 flex flex-wrap gap-2"></div>
      </div>
    </div>
  </main>

  <!-- 底部输入框 -->
  <footer class="p-3 md:p-4 bg-slate-900/90 border-t border-slate-800 backdrop-blur shrink-0">
    <div class="max-w-4xl mx-auto relative flex items-end gap-2">
      <textarea id="promptInput" rows="1" placeholder="输入您的问题 (Shift+Enter 换行，Enter 发送)..." 
        class="w-full bg-slate-950 border border-slate-700 focus:border-indigo-500 rounded-xl px-4 py-3 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-1 focus:ring-indigo-500 transition-all resize-none max-h-36"></textarea>
      <button id="sendBtn" class="h-11 px-4 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl flex items-center justify-center font-medium shadow-lg shadow-indigo-600/20 transition-all disabled:opacity-50 disabled:cursor-not-allowed shrink-0">
        <i data-lucide="send" class="w-4 h-4"></i>
      </button>
    </div>
  </footer>

  <!-- 侧边抽屉：工具与扩展配置 (Tools, MCP & Skills) -->
  <div id="toolsDrawer" class="fixed inset-y-0 right-0 w-80 md:w-96 bg-slate-900 border-l border-slate-800 z-50 transform translate-x-full transition-transform duration-300 flex flex-col shadow-2xl">
    <div class="p-4 border-b border-slate-800 flex items-center justify-between">
      <h3 class="text-sm font-semibold flex items-center gap-2">
        <i data-lucide="wrench" class="w-4 h-4 text-indigo-400"></i>
        <span>扩展功能与工具配置</span>
      </h3>
      <button id="closeToolsDrawerBtn" class="p-1 text-slate-400 hover:text-slate-200">
        <i data-lucide="x" class="w-4 h-4"></i>
      </button>
    </div>

    <div class="flex-1 overflow-y-auto p-4 space-y-5 text-xs">
      <!-- Skills 技能包标签 -->
      <div>
        <label class="block font-semibold text-slate-300 mb-2 flex items-center gap-1.5">
          <i data-lucide="book-open" class="w-3.5 h-3.5 text-cyan-400"></i>
          已挂载技能 (Skills)
        </label>
        <div id="skillsContainer" class="flex flex-wrap gap-1.5"></div>
      </div>

      <!-- API 工具列表与 Key 覆盖 -->
      <div>
        <label class="block font-semibold text-slate-300 mb-2 flex items-center gap-1.5">
          <i data-lucide="globe" class="w-3.5 h-3.5 text-emerald-400"></i>
          API 工具接入 (Tools)
        </label>
        <div id="toolsContainer" class="space-y-3"></div>
      </div>

      <!-- MCP 工具服务 -->
      <div>
        <label class="block font-semibold text-slate-300 mb-2 flex items-center gap-1.5">
          <i data-lucide="cpu" class="w-3.5 h-3.5 text-orange-400"></i>
          MCP 工具服务 (Model Context Protocol)
        </label>
        <div id="mcpContainer" class="space-y-2"></div>
      </div>
    </div>

    <div class="p-3 border-t border-slate-800 bg-slate-950/60 flex items-center justify-between">
      <span class="text-[11px] text-slate-500">配置保存在本地浏览器</span>
      <button id="saveConfigBtn" class="px-3 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg font-medium text-xs">保存修改</button>
    </div>
  </div>

  <script>
    lucide.createIcons();
    const SYSTEM_PROMPT = {system_prompt_escaped};
    const WELCOME_MESSAGE = {welcome_msg_escaped};
    const QUICK_PROMPTS = {quick_prompts_json};
    const PROVIDER_ID = {provider_id_val};
    const APP_SLUG = "{slug}";
    
    // 工具与技能配置
    const TOOLS_CONFIG = {tools_json};
    const SKILLS_CONFIG = {skills_json};
    const MCP_CONFIG = {mcp_servers_json};

    // 本地覆盖配置存储
    const STORAGE_KEY = 'agent_tools_' + APP_SLUG;
    let localOverrides = {{}};
    try {{
      localOverrides = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{{}}');
    }} catch (e) {{}}

    document.getElementById('welcomeMsg').innerHTML = marked.parse(WELCOME_MESSAGE);

    // 渲染快捷预设问题
    const qBox = document.getElementById('quickPromptBox');
    QUICK_PROMPTS.forEach(q => {{
      const btn = document.createElement('button');
      btn.className = 'text-xs px-2.5 py-1 bg-slate-800 hover:bg-indigo-600/20 hover:text-indigo-300 hover:border-indigo-500/40 border border-slate-700 rounded-full text-slate-300 transition-colors';
      btn.textContent = q;
      btn.onclick = () => {{
        document.getElementById('promptInput').value = q;
        sendMessage();
      }};
      qBox.appendChild(btn);
    }});

    // 渲染 Skills 技能标签
    const skillsBox = document.getElementById('skillsContainer');
    if (SKILLS_CONFIG.length === 0) {{
      skillsBox.innerHTML = '<span class="text-slate-500">基础通用对话能力</span>';
    }} else {{
      SKILLS_CONFIG.forEach(s => {{
        const sp = document.createElement('span');
        sp.className = 'px-2 py-0.5 rounded bg-cyan-500/10 text-cyan-300 border border-cyan-500/20 font-mono text-[11px]';
        sp.textContent = s;
        skillsBox.appendChild(sp);
      }});
    }}

    // 渲染 Tools 列表与用户配置输入框
    const toolsBox = document.getElementById('toolsContainer');
    if (TOOLS_CONFIG.length === 0) {{
      toolsBox.innerHTML = '<span class="text-slate-500">未接入外部 API 工具</span>';
    }} else {{
      TOOLS_CONFIG.forEach((t, idx) => {{
        const div = document.createElement('div');
        div.className = 'p-2.5 rounded-xl bg-slate-950 border border-slate-800 space-y-1.5';
        const savedUrl = localOverrides[t.name + '_endpoint'] || t.endpoint || '';
        const savedKey = localOverrides[t.name + '_key'] || '';

        div.innerHTML = `
          <div class="flex items-center justify-between font-semibold text-slate-200">
            <span>${{t.label || t.name}}</span>
            <span class="text-[10px] font-mono px-1.5 py-0.2 rounded bg-indigo-500/20 text-indigo-400">${{t.method || 'POST'}}</span>
          </div>
          <p class="text-[11px] text-slate-400">${{t.description || ''}}</p>
          <div class="space-y-1 pt-1">
            <input type="text" id="endpoint_${{idx}}" value="${{savedUrl}}" placeholder="API Endpoint" class="w-full bg-slate-900 border border-slate-800 rounded px-2 py-1 text-[11px] font-mono text-slate-300 outline-none" />
            <input type="password" id="key_${{idx}}" value="${{savedKey}}" placeholder="API Key / Token (选填)" class="w-full bg-slate-900 border border-slate-800 rounded px-2 py-1 text-[11px] font-mono text-slate-300 outline-none" />
          </div>
        `;
        toolsBox.appendChild(div);
      }});
    }}

    // 渲染 MCP 配置
    const mcpBox = document.getElementById('mcpContainer');
    if (MCP_CONFIG.length === 0) {{
      mcpBox.innerHTML = '<span class="text-slate-500">未挂载 MCP 服务</span>';
    }} else {{
      MCP_CONFIG.forEach(m => {{
        const div = document.createElement('div');
        div.className = 'p-2 rounded-lg bg-slate-950 border border-slate-800 text-[11px]';
        div.innerHTML = `<span class="font-bold text-orange-400">${{m.name}}</span>: <span class="text-slate-400 font-mono">${{m.server_url}}</span>`;
        mcpBox.appendChild(div);
      }});
    }}

    // 抽屉开关
    const drawer = document.getElementById('toolsDrawer');
    document.getElementById('openToolsDrawerBtn').onclick = () => drawer.classList.remove('translate-x-full');
    document.getElementById('closeToolsDrawerBtn').onclick = () => drawer.classList.add('translate-x-full');
    document.getElementById('saveConfigBtn').onclick = () => {{
      TOOLS_CONFIG.forEach((t, idx) => {{
        const epEl = document.getElementById('endpoint_' + idx);
        const keyEl = document.getElementById('key_' + idx);
        if (epEl) localOverrides[t.name + '_endpoint'] = epEl.value.trim();
        if (keyEl) localOverrides[t.name + '_key'] = keyEl.value.trim();
      }});
      localStorage.setItem(STORAGE_KEY, JSON.stringify(localOverrides));
      alert('工具与 API 配置已成功保存至本地！');
      drawer.classList.add('translate-x-full');
    }};

    const chatContainer = document.getElementById('chatContainer');
    const promptInput = document.getElementById('promptInput');
    const sendBtn = document.getElementById('sendBtn');
    let messages = [{{ role: 'system', content: SYSTEM_PROMPT }}];
    let isGenerating = false;

    // 自适应文本框高度
    promptInput.addEventListener('input', function() {{
      this.style.height = 'auto';
      this.style.height = Math.min(this.scrollHeight, 140) + 'px';
    }});

    promptInput.addEventListener('keydown', (e) => {{
      if (e.key === 'Enter' && !e.shiftKey) {{
        e.preventDefault();
        sendMessage();
      }}
    }});

    sendBtn.addEventListener('click', sendMessage);

    document.getElementById('clearChatBtn').addEventListener('click', () => {{
      if (confirm('确定要清空当前的对话记录吗？')) {{
        messages = [{{ role: 'system', content: SYSTEM_PROMPT }}];
        location.reload();
      }}
    }});

    document.getElementById('helpBtn').addEventListener('click', () => {{
      alert('【智能体设定与技能】\\n\\n' + SYSTEM_PROMPT);
    }});

    function scrollToBottom() {{
      chatContainer.scrollTop = chatContainer.scrollHeight;
    }}

    async function sendMessage() {{
      const text = promptInput.value.trim();
      if (!text || isGenerating) return;

      promptInput.value = '';
      promptInput.style.height = 'auto';
      isGenerating = true;
      sendBtn.disabled = true;

      // 渲染用户气泡
      appendMessage('user', text);
      messages.push({{ role: 'user', content: text }});

      // 创建助手气泡与流式容器
      const aiBubble = appendMessage('assistant', '');
      const contentEl = aiBubble.querySelector('.ai-content');
      contentEl.classList.add('typing-cursor');

      let accumulated = '';

      try {{
        const payload = {{
          messages: messages,
          provider_id: PROVIDER_ID,
          system_prompt: SYSTEM_PROMPT
        }};

        const res = await fetch('/api/ai/agent/stream', {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify(payload)
        }});

        if (!res.ok) {{
          throw new Error('服务请求异常: ' + res.status);
        }}

        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {{
          const {{ done, value }} = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, {{ stream: true }});
          const lines = buffer.split('\\n');
          buffer = lines.pop() || '';

          for (const line of lines) {{
            const trimmed = line.trim();
            if (trimmed.startsWith('data:')) {{
              const dataStr = trimmed.substring(5).trim();
              if (dataStr === '[DONE]') break;
              try {{
                const parsed = JSON.parse(dataStr);
                if (parsed.delta) {{
                  accumulated += parsed.delta;
                  renderAiMessageWithActions(contentEl, accumulated);
                  scrollToBottom();
                }}
              }} catch (err) {{}}
            }}
          }}
        }}

        messages.push({{ role: 'assistant', content: accumulated }});
      }} catch (err) {{
        contentEl.innerHTML = '<span class="text-rose-400">调用失败: ' + err.message + '</span>';
      }} finally {{
        contentEl.classList.remove('typing-cursor');
        isGenerating = false;
        sendBtn.disabled = false;
        promptInput.focus();
        scrollToBottom();
      }}
    }}

    function renderAiMessageWithActions(containerEl, markdownText) {{
      containerEl.innerHTML = marked.parse(markdownText);
      containerEl.querySelectorAll('pre code').forEach((block) => {{
        hljs.highlightElement(block);
        
        // 智能检测代码块是否为 JSON 或 n8n 工作流
        const rawCode = block.innerText.trim();
        if (rawCode.startsWith('{{') && (rawCode.includes('"nodes"') || rawCode.includes('"connections"') || rawCode.includes('"name"'))) {{
          const pre = block.parentElement;
          if (!pre.querySelector('.workflow-action-bar')) {{
            const bar = document.createElement('div');
            bar.className = 'workflow-action-bar';
            bar.innerHTML = `
              <span class="text-[10px] text-orange-400 font-semibold mr-auto">⚡ 检测到 n8n 工作流结构</span>
              <button class="copy-wf-btn px-2 py-1 text-[11px] bg-slate-800 hover:bg-slate-700 text-slate-300 rounded transition">📋 复制</button>
              <button class="download-wf-btn px-2 py-1 text-[11px] bg-slate-800 hover:bg-slate-700 text-slate-300 rounded transition">💾 下载 JSON</button>
              <button class="deploy-wf-btn px-2.5 py-1 text-[11px] bg-orange-600 hover:bg-orange-500 text-white rounded font-medium shadow transition">🚀 一键推送到 n8n</button>
            `;

            bar.querySelector('.copy-wf-btn').onclick = () => {{
              navigator.clipboard.writeText(rawCode).then(() => alert('工作流 JSON 已复制到剪贴板！'));
            }};

            bar.querySelector('.download-wf-btn').onclick = () => {{
              const blob = new Blob([rawCode], {{ type: 'application/json' }});
              const url = URL.createObjectURL(blob);
              const a = document.createElement('a');
              a.href = url;
              a.download = 'n8n_workflow_' + Date.now() + '.json';
              a.click();
              URL.revokeObjectURL(url);
            }};

            bar.querySelector('.deploy-wf-btn').onclick = async () => {{
              await deployWorkflowToN8n(rawCode);
            }};

            pre.appendChild(bar);
          }}
        }}
      }});
    }}

    // 通过后端代理将工作流部署至 n8n API
    async function deployWorkflowToN8n(rawJsonStr) {{
      let targetEndpoint = localOverrides['create_n8n_workflow_endpoint'] || '';
      let apiKey = localOverrides['create_n8n_workflow_key'] || '';

      if (!targetEndpoint) {{
        const defaultTool = TOOLS_CONFIG.find(t => t.name === 'create_n8n_workflow');
        if (defaultTool && defaultTool.endpoint) {{
          targetEndpoint = defaultTool.endpoint;
        }}
      }}

      if (!targetEndpoint || targetEndpoint.includes('your-domain.com')) {{
        const userUrl = prompt('请输入您的 n8n 实例地址 (例如 https://n8n.my-site.com/api/v1/workflows):', targetEndpoint);
        if (!userUrl) return;
        targetEndpoint = userUrl.trim();
        localOverrides['create_n8n_workflow_endpoint'] = targetEndpoint;
        localStorage.setItem(STORAGE_KEY, JSON.stringify(localOverrides));
      }}

      let parsedPayload;
      try {{
        parsedPayload = JSON.parse(rawJsonStr);
      }} catch (err) {{
        return alert('解析工作流 JSON 失败: ' + err.message);
      }}

      const headers = {{ 'Content-Type': 'application/json' }};
      if (apiKey) {{
        headers['X-N8N-API-KEY'] = apiKey;
      }}

      try {{
        const res = await fetch('/api/agent/proxy-call', {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify({{
            url: targetEndpoint,
            method: 'POST',
            headers: headers,
            payload: parsedPayload
          }})
        }});
        const result = await res.json();
        if (result.status_code >= 200 && result.status_code < 300) {{
          const wfId = (result.data && result.data.id) ? result.data.id : '未知ID';
          alert('🎉 恭喜！工作流已成功通过 API 发布至 n8n 实例！\\n工作流 ID: ' + wfId);
        }} else {{
          alert('推送 n8n 失败: HTTP ' + result.status_code + '\\n' + (result.message || JSON.stringify(result.data || '')));
        }}
      }} catch (e) {{
        alert('调用代理接口异常: ' + e.message);
      }}
    }}

    function appendMessage(role, text) {{
      const wrapper = document.createElement('div');
      wrapper.className = 'flex gap-3 items-start animate-fade-in ' + (role === 'user' ? 'flex-row-reverse' : '');

      if (role === 'user') {{
        wrapper.innerHTML = `
          <div class="w-8 h-8 rounded-lg bg-indigo-600 flex items-center justify-center shrink-0 text-white text-xs font-bold">ME</div>
          <div class="bg-indigo-600 text-white rounded-2xl rounded-tr-sm px-4 py-2.5 max-w-[85%] text-sm shadow-sm whitespace-pre-wrap leading-relaxed">${{escapeHtml(text)}}</div>
        `;
      }} else {{
        wrapper.innerHTML = `
          <div class="w-8 h-8 rounded-lg bg-indigo-600/20 border border-indigo-500/30 flex items-center justify-center shrink-0 text-base">{req.icon}</div>
          <div class="bg-slate-900 border border-slate-800 rounded-2xl rounded-tl-sm px-4 py-3 max-w-[85%] text-sm shadow-sm leading-relaxed">
            <div class="markdown-body ai-content">${{marked.parse(text)}}</div>
          </div>
        `;
      }}
      chatContainer.appendChild(wrapper);
      scrollToBottom();
      return wrapper;
    }}

    function escapeHtml(str) {{
      return str.replace(/[&<>'"]/g, tag => ({{ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }}[tag] || tag));
    }}
  </script>
</body>
</html>"""

    return GeneratedAppResult(
        slug=slug,
        title=req.title,
        description=req.description or "专属 AI 智能助手",
        category=req.category or "AI助手",
        icon=req.icon or "🤖",
        html_content=html_code,
    )

# ==================== n8n 集成单页代码模板 ====================

def generate_n8n_app_html(req: N8nAppGenerateRequest) -> GeneratedAppResult:
    """
    生成 n8n 自动化微应用 (Chat 嵌入 或 Webhook 触发看板)
    """
    slug = req.slug or sanitize_slug(req.title)

    if req.mode == "chat":
        # 生成 n8n Chat 嵌入应用
        html_code = f"""<!DOCTYPE html>
<html lang="zh-CN" class="dark">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{req.title} - n8n AI Chat</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <script src="https://unpkg.com/lucide@latest"></script>
  <link href="https://cdn.jsdelivr.net/npm/@n8n/chat/dist/style.css" rel="stylesheet" />
</head>
<body class="bg-slate-950 text-slate-100 flex flex-col h-screen overflow-hidden">
  <!-- 顶部状态栏 -->
  <header class="h-14 border-b border-slate-800 bg-slate-900 px-4 flex items-center justify-between z-10 shrink-0">
    <div class="flex items-center space-x-3">
      <div class="w-9 h-9 rounded-xl bg-orange-600/20 border border-orange-500/30 flex items-center justify-center text-xl">
        {req.icon}
      </div>
      <div>
        <h1 class="text-sm font-semibold tracking-wide flex items-center gap-2">
          {req.title}
          <span class="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium bg-orange-500/10 text-orange-400 border border-orange-500/20">n8n Workflow</span>
        </h1>
        <p class="text-xs text-slate-400 truncate max-w-sm">{req.description or '基于 n8n 的智能助手'}</p>
      </div>
    </div>
    <div class="flex items-center space-x-2">
      <a href="{req.webhook_url}" target="_blank" class="text-xs px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg flex items-center gap-1.5 border border-slate-700">
        <i data-lucide="external-link" class="w-3.5 h-3.5"></i>
        <span>直达链接</span>
      </a>
    </div>
  </header>

  <!-- n8n Chat 全屏容器 -->
  <main id="n8n-chat-container" class="flex-1 w-full h-full relative">
    <iframe src="{req.webhook_url}" class="w-full h-full border-none" allow="microphone; camera; clipboard-read; clipboard-write"></iframe>
  </main>

  <script>
    lucide.createIcons();
  </script>
</body>
</html>"""
    else:
        # 生成 n8n Webhook 触发与执行结果看板
        fields_json = json.dumps(req.fields or [
            {"id": "query", "label": "输入参数 / Query", "type": "text", "placeholder": "请输入测试参数...", "required": True}
        ], ensure_ascii=False)

        html_code = f"""<!DOCTYPE html>
<html lang="zh-CN" class="dark">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{req.title} - n8n Webhook 看板</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <script src="https://unpkg.com/lucide@latest"></script>
  <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
  <script src="https://cdn.jsdelivr.net/gh/highlightjs/cdn-release@11.9.0/build/highlight.min.js"></script>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/highlightjs/cdn-release@11.9.0/build/styles/atom-one-dark.min.css">
</head>
<body class="bg-slate-950 text-slate-100 flex flex-col h-screen overflow-hidden">
  
  <header class="h-14 border-b border-slate-800 bg-slate-900 px-4 flex items-center justify-between shrink-0">
    <div class="flex items-center space-x-3">
      <div class="w-9 h-9 rounded-xl bg-orange-600/20 border border-orange-500/30 flex items-center justify-center text-xl">
        {req.icon}
      </div>
      <div>
        <h1 class="text-sm font-semibold tracking-wide flex items-center gap-2">
          {req.title}
          <span class="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-mono bg-orange-500/10 text-orange-400 border border-orange-500/20">{req.http_method or 'POST'}</span>
        </h1>
        <p class="text-xs text-slate-400 truncate max-w-sm">{req.description or 'n8n 自动化工作流触发看板'}</p>
      </div>
    </div>
    <div class="text-xs font-mono text-slate-400 bg-slate-800/80 px-2.5 py-1 rounded border border-slate-700 max-w-xs truncate" title="{req.webhook_url}">
      {req.webhook_url}
    </div>
  </header>

  <div class="flex-1 flex flex-col md:flex-row overflow-hidden">
    <!-- 左侧：入参表单面板 -->
    <div class="w-full md:w-5/12 border-r border-slate-800 bg-slate-900/50 p-6 flex flex-col overflow-y-auto">
      <div class="mb-4 flex items-center justify-between">
        <h2 class="text-xs font-semibold text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
          <i data-lucide="sliders" class="w-4 h-4 text-orange-400"></i>
          请求入参配置
        </h2>
        <span class="text-xs text-slate-500">Payload Builder</span>
      </div>

      <form id="webhookForm" class="space-y-4 flex-1">
        <div id="dynamicFieldsContainer" class="space-y-4"></div>

        <div class="pt-2">
          <button type="submit" id="submitBtn" class="w-full py-3 bg-orange-600 hover:bg-orange-500 text-white rounded-xl font-medium shadow-lg shadow-orange-600/20 flex items-center justify-center gap-2 transition-all">
            <i data-lucide="play" class="w-4 h-4"></i>
            <span>触发执行工作流</span>
          </button>
        </div>
      </form>
    </div>

    <!-- 右侧：执行回显看板 -->
    <div class="flex-1 bg-slate-950 p-6 flex flex-col overflow-hidden">
      <div class="flex items-center justify-between mb-3 shrink-0">
        <div class="flex items-center gap-2">
          <h2 class="text-xs font-semibold text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
            <i data-lucide="terminal" class="w-4 h-4 text-emerald-400"></i>
            工作流执行响应看板
          </h2>
          <span id="statusBadge" class="hidden px-2 py-0.5 rounded text-[11px] font-mono"></span>
          <span id="timeBadge" class="hidden text-xs text-slate-500 font-mono"></span>
        </div>
        <div class="flex items-center gap-2">
          <button id="copyBtn" class="text-xs px-2.5 py-1 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded border border-slate-700 flex items-center gap-1 transition-colors">
            <i data-lucide="copy" class="w-3.5 h-3.5"></i>
            <span>复制内容</span>
          </button>
        </div>
      </div>

      <div class="flex-1 border border-slate-800 rounded-xl bg-slate-900/40 overflow-hidden flex flex-col">
        <pre id="outputCode" class="flex-1 p-4 font-mono text-xs overflow-auto text-slate-300 leading-relaxed"><code class="language-json">// 点击左侧“触发执行工作流”发送请求，此处将实时展示响应回显结果...</code></pre>
      </div>
    </div>
  </div>

  <script>
    lucide.createIcons();
    const WEBHOOK_URL = "{req.webhook_url}";
    const HTTP_METHOD = "{req.http_method or 'POST'}";
    const FIELDS = {fields_json};

    const container = document.getElementById('dynamicFieldsContainer');
    FIELDS.forEach(f => {{
      const div = document.createElement('div');
      div.className = 'space-y-1.5';
      div.innerHTML = `
        <label class="block text-xs font-medium text-slate-300">
          ${{f.label}} ${{f.required ? '<span class="text-rose-400">*</span>' : ''}}
        </label>
        ${{f.type === 'textarea' 
          ? `<textarea name="${{f.id}}" rows="3" class="w-full bg-slate-950 border border-slate-800 focus:border-orange-500 rounded-lg px-3 py-2 text-sm text-slate-200 outline-none transition-colors" placeholder="${{f.placeholder || ''}}"></textarea>`
          : `<input type="${{f.type || 'text'}}" name="${{f.id}}" class="w-full bg-slate-950 border border-slate-800 focus:border-orange-500 rounded-lg px-3 py-2 text-sm text-slate-200 outline-none transition-colors" placeholder="${{f.placeholder || ''}}" ${{f.required ? 'required' : ''}} />`
        }}
      `;
      container.appendChild(div);
    }});

    const form = document.getElementById('webhookForm');
    const submitBtn = document.getElementById('submitBtn');
    const outputCode = document.getElementById('outputCode');
    const statusBadge = document.getElementById('statusBadge');
    const timeBadge = document.getElementById('timeBadge');

    form.addEventListener('submit', async (e) => {{
      e.preventDefault();
      submitBtn.disabled = true;
      submitBtn.classList.add('opacity-50');

      const formData = new FormData(form);
      const payload = {{}};
      formData.forEach((val, key) => {{ payload[key] = val; }});

      outputCode.innerHTML = '<code>正在向 n8n Webhook 发送请求，等待处理...</code>';
      const startTime = performance.now();

      try {{
        const options = {{
          method: HTTP_METHOD,
          headers: {{ 'Content-Type': 'application/json' }}
        }};
        if (HTTP_METHOD === 'POST') {{
          options.body = JSON.stringify(payload);
        }}

        const res = await fetch(WEBHOOK_URL, options);
        const duration = Math.round(performance.now() - startTime);

        statusBadge.classList.remove('hidden');
        timeBadge.classList.remove('hidden');
        timeBadge.textContent = duration + 'ms';

        if (res.ok) {{
          statusBadge.className = 'px-2 py-0.5 rounded text-[11px] font-mono bg-emerald-500/10 text-emerald-400 border border-emerald-500/20';
          statusBadge.textContent = 'HTTP ' + res.status;
        }} else {{
          statusBadge.className = 'px-2 py-0.5 rounded text-[11px] font-mono bg-rose-500/10 text-rose-400 border border-rose-500/20';
          statusBadge.textContent = 'HTTP ' + res.status;
        }}

        const text = await res.text();
        try {{
          const jsonObj = JSON.parse(text);
          outputCode.innerHTML = `<code class="language-json">${{hljs.highlight(JSON.stringify(jsonObj, null, 2), {{ language: 'json' }}).value}}</code>`;
        }} catch (err) {{
          outputCode.innerText = text;
        }}
      }} catch (err) {{
        statusBadge.classList.remove('hidden');
        statusBadge.className = 'px-2 py-0.5 rounded text-[11px] font-mono bg-rose-500/10 text-rose-400 border border-rose-500/20';
        statusBadge.textContent = 'ERR';
        outputCode.innerText = '请求触发失败: ' + err.message + '\\n(请检查目标 Webhook 是否允许跨域 CORS 或公网可访问)';
      }} finally {{
        submitBtn.disabled = false;
        submitBtn.classList.remove('opacity-50');
      }}
    }});

    document.getElementById('copyBtn').addEventListener('click', () => {{
      navigator.clipboard.writeText(outputCode.innerText).then(() => {{
        alert('响应内容已复制到剪贴板！');
      }});
    }});
  </script>
</body>
</html>"""

    return GeneratedAppResult(
        slug=slug,
        title=req.title,
        description=req.description or "n8n 自动化流应用",
        category=req.category or "自动化流",
        icon=req.icon or "⚡",
        html_content=html_code,
    )

# ==================== 自定义表单应用生成模板 ====================

def generate_form_app_html(
    title: str,
    description: str,
    icon: str,
    category: str,
    fields: List[Dict[str, Any]],
    webhook_url: Optional[str] = None,
    slug: Optional[str] = None,
) -> GeneratedAppResult:
    """
    生成开箱即用的现代化数据采集表单微应用 (支持本地存储、校验、导出与 Webhook 转发)
    """
    final_slug = slug or sanitize_slug(title)
    fields_json = json.dumps(fields, ensure_ascii=False)
    webhook_escaped = json.dumps(webhook_url or "", ensure_ascii=False)

    html_code = f"""<!DOCTYPE html>
<html lang="zh-CN" class="dark">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title} - 在线数据采集</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <script src="https://unpkg.com/lucide@latest"></script>
</head>
<body class="bg-slate-950 text-slate-100 min-h-screen py-8 px-4 flex flex-col justify-between selection:bg-indigo-500 selection:text-white">

  <!-- 顶部与表单卡片容器 -->
  <div class="max-w-2xl w-full mx-auto space-y-6">
    <!-- 头部信息 -->
    <div class="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl relative overflow-hidden">
      <div class="flex items-start justify-between">
        <div class="flex items-center gap-3">
          <div class="w-12 h-12 rounded-xl bg-indigo-600/20 border border-indigo-500/30 flex items-center justify-center text-2xl shrink-0">
            {icon}
          </div>
          <div>
            <h1 class="text-xl font-bold text-slate-100">{title}</h1>
            <p class="text-sm text-slate-400 mt-1">{description or '请按要求填写以下表单内容'}</p>
          </div>
        </div>
        <button id="viewRecordsBtn" class="text-xs px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg border border-slate-700 flex items-center gap-1.5 transition-colors">
          <i data-lucide="database" class="w-3.5 h-3.5"></i>
          <span>历史记录 (<span id="recordCount">0</span>)</span>
        </button>
      </div>
    </div>

    <!-- 动态表单 -->
    <div class="bg-slate-900 border border-slate-800 rounded-2xl p-6 md:p-8 shadow-xl">
      <form id="dataCollectionForm" class="space-y-5">
        <div id="formFieldsBox" class="space-y-5"></div>

        <div class="pt-4 flex items-center gap-3">
          <button type="submit" id="submitBtn" class="flex-1 py-3 px-6 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl font-semibold shadow-lg shadow-indigo-600/20 flex items-center justify-center gap-2 transition-all">
            <i data-lucide="check-circle" class="w-4 h-4"></i>
            <span>提交表单</span>
          </button>
          <button type="reset" id="resetBtn" class="px-4 py-3 bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-slate-200 rounded-xl font-medium transition-colors">
            重置
          </button>
        </div>
      </form>
    </div>
  </div>

  <!-- 历史提交记录抽屉 / 弹窗 -->
  <div id="recordsModal" class="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 hidden flex items-center justify-center p-4">
    <div class="bg-slate-900 border border-slate-800 rounded-2xl max-w-3xl w-full max-h-[85vh] flex flex-col shadow-2xl">
      <div class="p-4 border-b border-slate-800 flex items-center justify-between">
        <h3 class="text-base font-semibold flex items-center gap-2">
          <i data-lucide="database" class="w-4 h-4 text-indigo-400"></i>
          本地已收集数据列表
        </h3>
        <div class="flex items-center gap-2">
          <button id="exportCsvBtn" class="text-xs px-3 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg flex items-center gap-1 font-medium transition-colors">
            <i data-lucide="download" class="w-3.5 h-3.5"></i>
            <span>导出 CSV</span>
          </button>
          <button id="closeModalBtn" class="p-1.5 text-slate-400 hover:text-slate-200 rounded-lg">
            <i data-lucide="x" class="w-5 h-5"></i>
          </button>
        </div>
      </div>
      <div class="flex-1 overflow-auto p-4">
        <div id="tableWrapper" class="overflow-x-auto"></div>
      </div>
    </div>
  </div>

  <footer class="mt-8 text-center text-xs text-slate-500">
    由 LiteApp Studio 智能表单引擎强力驱动
  </footer>

  <script>
    lucide.createIcons();
    const FIELDS = {fields_json};
    const WEBHOOK_URL = {webhook_escaped};
    const STORAGE_KEY = 'liteapp_form_' + '{final_slug}';

    // 渲染动态字段
    const box = document.getElementById('formFieldsBox');
    FIELDS.forEach(f => {{
      const wrap = document.createElement('div');
      wrap.className = 'space-y-1.5';
      const reqBadge = f.required ? '<span class="text-rose-400 ml-1">*</span>' : '';

      if (f.type === 'textarea') {{
        wrap.innerHTML = `
          <label class="block text-xs font-semibold text-slate-300">${{f.label}}${{reqBadge}}</label>
          <textarea name="${{f.id}}" rows="3" class="w-full bg-slate-950 border border-slate-800 focus:border-indigo-500 rounded-xl px-3.5 py-2.5 text-sm text-slate-100 placeholder-slate-600 outline-none transition-colors" placeholder="${{f.placeholder || ''}}" ${{f.required ? 'required' : ''}}></textarea>
        `;
      }} else if (f.type === 'select') {{
        const opts = (f.options && f.options.length) ? f.options : ['是', '否'];
        wrap.innerHTML = `
          <label class="block text-xs font-semibold text-slate-300">${{f.label}}${{reqBadge}}</label>
          <select name="${{f.id}}" class="w-full bg-slate-950 border border-slate-800 focus:border-indigo-500 rounded-xl px-3.5 py-2.5 text-sm text-slate-100 outline-none transition-colors" ${{f.required ? 'required' : ''}}>
            <option value="">-- 请选择 --</option>
            ${{opts.map(o => `<option value="${{o}}">${{o}}</option>`).join('')}}
          </select>
        `;
      }} else {{
        wrap.innerHTML = `
          <label class="block text-xs font-semibold text-slate-300">${{f.label}}${{reqBadge}}</label>
          <input type="${{f.type || 'text'}}" name="${{f.id}}" class="w-full bg-slate-950 border border-slate-800 focus:border-indigo-500 rounded-xl px-3.5 py-2.5 text-sm text-slate-100 placeholder-slate-600 outline-none transition-colors" placeholder="${{f.placeholder || ''}}" ${{f.required ? 'required' : ''}} />
        `;
      }}
      box.appendChild(wrap);
    }});

    // 读取本地历史数据
    function getStoredRecords() {{
      try {{
        return JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]');
      }} catch (e) {{
        return [];
      }}
    }}

    function saveRecords(list) {{
      localStorage.setItem(STORAGE_KEY, JSON.stringify(list));
      updateCount();
    }}

    function updateCount() {{
      const records = getStoredRecords();
      document.getElementById('recordCount').textContent = records.length;
    }}
    updateCount();

    // 提交逻辑
    const form = document.getElementById('dataCollectionForm');
    const submitBtn = document.getElementById('submitBtn');

    form.addEventListener('submit', async (e) => {{
      e.preventDefault();
      submitBtn.disabled = true;

      const fd = new FormData(form);
      const dataObj = {{
        _id: 'rec_' + Date.now(),
        _submit_time: new Date().toLocaleString()
      }};
      fd.forEach((val, key) => {{ dataObj[key] = val; }});

      // 1. 本地存储副本
      const list = getStoredRecords();
      list.unshift(dataObj);
      saveRecords(list);

      // 2. 自动提交至 LiteApp Studio 后端数据库持久保存
      try {{
        await fetch('/api/forms/{final_slug}/submit', {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify(dataObj)
        }});
      }} catch (err) {{
        console.warn('后端数据持久化存储请求异常 (已存本地):', err);
      }}

      // 3. 尝试转发外部 Webhook (如配置)
      if (WEBHOOK_URL && WEBHOOK_URL.trim()) {{
        try {{
          await fetch(WEBHOOK_URL, {{
            method: 'POST',
            headers: {{ 'Content-Type': 'application/json' }},
            body: JSON.stringify(dataObj)
          }});
        }} catch (err) {{
          console.warn('Webhook 推送异常 (已存本地):', err);
        }}
      }}

      alert('🎉 恭喜！表单数据已成功提交并保存。');
      form.reset();
      submitBtn.disabled = false;
    }});

    // 历史弹窗与表格渲染
    const modal = document.getElementById('recordsModal');
    document.getElementById('viewRecordsBtn').onclick = () => {{
      renderTable();
      modal.classList.remove('hidden');
    }};
    document.getElementById('closeModalBtn').onclick = () => modal.classList.add('hidden');

    function renderTable() {{
      const records = getStoredRecords();
      const wrapper = document.getElementById('tableWrapper');
      if (!records.length) {{
        wrapper.innerHTML = '<p class="text-slate-500 text-sm py-8 text-center">暂无已提交的数据记录</p>';
        return;
      }}

      let html = '<table class="w-full text-xs text-left text-slate-300"><thead><tr class="border-b border-slate-800 text-slate-400 font-semibold">';
      html += '<th class="py-2.5 px-3">提交时间</th>';
      FIELDS.forEach(f => {{ html += `<th class="py-2.5 px-3">${{f.label}}</th>`; }});
      html += '</tr></thead><tbody>';

      records.forEach(r => {{
        html += '<tr class="border-b border-slate-800/60 hover:bg-slate-800/30">';
        html += `<td class="py-2.5 px-3 whitespace-nowrap text-slate-400">${{r._submit_time}}</td>`;
        FIELDS.forEach(f => {{
          html += `<td class="py-2.5 px-3 max-w-xs truncate">${{r[f.id] || '-'}}</td>`;
        }});
        html += '</tr>';
      }});
      html += '</tbody></table>';
      wrapper.innerHTML = html;
    }}

    // 导出 CSV
    document.getElementById('exportCsvBtn').onclick = () => {{
      const records = getStoredRecords();
      if (!records.length) return alert('暂无数据可导出');

      const headers = ['提交时间', ...FIELDS.map(f => f.label)];
      const rows = records.map(r => [
        `"${{r._submit_time}}"`,
        ...FIELDS.map(f => `"${{(r[f.id] || '').replace(/"/g, '""')}}"`)
      ]);

      const csvContent = '\\uFEFF' + [headers.join(','), ...rows.map(e => e.join(','))].join('\\n');
      const blob = new Blob([csvContent], {{ type: 'text/csv;charset=utf-8;' }});
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = '{final_slug}_records.csv';
      a.click();
      URL.revokeObjectURL(url);
    }};
  </script>
</body>
</html>"""

    return GeneratedAppResult(
        slug=final_slug,
        title=title,
        description=description or "在线数据采集表单",
        category=category or "数据收集",
        icon=icon or "📝",
        html_content=html_code,
    )

def parse_prompt_to_form_fields(prompt: str) -> List[Dict[str, Any]]:
    """
    根据自然语言需求描述智能推导表单字段
    """
    fields: List[Dict[str, Any]] = []

    # 尝试按逗号、顿号、换行切分
    segments = re.split(r"[,，、\n]+", prompt)
    clean_segments = [s.strip() for s in segments if s.strip() and len(s.strip()) <= 30]

    if not clean_segments or len(clean_segments) < 2:
        # 如果一段话较长，使用正则提取常见字段关键词
        keywords = ["姓名", "手机", "电话", "邮箱", "部门", "职位", "工号", "日期", "时间", "数量", "金额", "地址", "是否需要", "评分", "备注", "反馈"]
        extracted = [k for k in keywords if k in prompt]
        if extracted:
            clean_segments = extracted
        else:
            clean_segments = ["姓名", "手机号码", "所属部门", "主要需求或反馈", "是否同意协议"]

    for idx, seg in enumerate(clean_segments):
        field_type = "text"
        placeholder = f"请输入{seg}"

        if any(k in seg for k in ["邮箱", "email"]):
            field_type = "email"
            placeholder = "name@example.com"
        elif any(k in seg for k in ["手机", "电话", "联系方式"]):
            field_type = "tel"
            placeholder = "13800000000"
        elif any(k in seg for k in ["日期", "时间", "生日"]):
            field_type = "date"
        elif any(k in seg for k in ["备注", "详情", "反馈", "建议", "说明", "需求"]):
            field_type = "textarea"
        elif any(k in seg for k in ["数量", "金额", "年龄", "预算"]):
            field_type = "number"
        elif any(k in seg for k in ["是否", "需要", "选择"]):
            field_type = "select"

        fields.append({
            "id": f"field_{idx+1}",
            "label": seg,
            "type": field_type,
            "placeholder": placeholder,
            "required": idx < 2,
            "options": ["是", "否"] if field_type == "select" else [],
        })

    return fields
