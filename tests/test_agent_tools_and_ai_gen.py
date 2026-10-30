"""
测试 LiteApp Studio 的 AI 智能体快速生成、API 工具集成、Skills 挂载、输入框 AI 辅助与中继代理端点
"""

import sys
import json
from pathlib import Path

# 确保项目根目录在 python path 中
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# 控制台 UTF-8 输出
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from fastapi.testclient import TestClient
from app.main import app
from app.core.config import settings

client = TestClient(app)

def test_agent_tools_and_ai_gen_pipeline():
    print("=== 开始验证 AI 智能体生成、MCP/API工具扩展与AI辅助生成功能 ===")

    # 1. 登录管理员
    login_res = client.post("/api/auth/login", json={"password": settings.ADMIN_PASSWORD})
    assert login_res.status_code == 200, f"登录失败: {login_res.text}"
    token = login_res.json()["token"]
    admin_headers = {"X-Admin-Token": token}
    print("✓ 1. 管理员登录成功")

    # 2. 测试输入框单项 AI 生成/扩写端点 (/api/ai/generate-field)
    # 测试未登录鉴权拦截
    unauth_res = client.post("/api/ai/generate-field", json={"field_type": "title", "context": "番茄钟"})
    assert unauth_res.status_code in [401, 403], f"预期鉴权拦截，实际: {unauth_res.status_code}"

    # 测试生成标题 (title)
    title_res = client.post(
        "/api/ai/generate-field",
        json={"field_type": "title", "context": "根据需求自动生成并创建 n8n 工作流"},
        headers=admin_headers
    )
    assert title_res.status_code == 200, f"生成标题失败: {title_res.text}"
    title_data = title_res.json()
    assert len(title_data["generated_content"]) > 0
    print(f"✓ 2.1 AI 生成标题成功: 「{title_data['generated_content']}」")

    # 测试生成简介 (description)
    desc_res = client.post(
        "/api/ai/generate-field",
        json={"field_type": "description", "context": "n8n 工作流专家，帮助用户连接各个 API"},
        headers=admin_headers
    )
    assert desc_res.status_code == 200, f"生成简介失败: {desc_res.text}"
    desc_data = desc_res.json()
    assert len(desc_data["generated_content"]) > 0
    print(f"✓ 2.2 AI 生成简介成功: 「{desc_data['generated_content']}」")

    # 测试扩写提示词 (prompt)
    prompt_res = client.post(
        "/api/ai/generate-field",
        json={"field_type": "prompt", "context": "帮我写一个合同审查助手"},
        headers=admin_headers
    )
    assert prompt_res.status_code == 200, f"扩写提示词失败: {prompt_res.text}"
    prompt_data = prompt_res.json()
    assert len(prompt_data["generated_content"]) > 20
    print(f"✓ 2.3 AI 扩写 System Prompt 成功 (长度 {len(prompt_data['generated_content'])} 字符)")

    # 3. 测试全套智能体快速 AI 构思端点 (/api/ai/generate-agent-suite)
    # 测试 n8n 场景下的智能推断
    suite_res = client.post(
        "/api/ai/generate-agent-suite",
        json={"context": "帮我做一个根据自然语言需求生成 n8n 工作流并自动通过 n8n API 创建 workflow 的专家智能体"},
        headers=admin_headers
    )
    assert suite_res.status_code == 200, f"全套构思失败: {suite_res.text}"
    suite_data = suite_res.json()
    assert suite_data["title"]
    assert suite_data["system_prompt"]
    assert suite_data["welcome_message"]
    assert len(suite_data["quick_prompts"]) > 0
    assert "n8n-workflow-spec" in suite_data["skills"]
    assert len(suite_data["tools"]) > 0
    print(f"✓ 3. 全套智能体构思成功 (标题: {suite_data['title']}, Skills: {suite_data['skills']}, Tools: {len(suite_data['tools'])} 个)")

    # 4. 测试生成包含 Tools 与 Skills 的智能体微应用
    test_slug = "test-n8n-architect-agent"
    client.delete(f"/api/apps/{test_slug}", headers=admin_headers)

    agent_req = {
        "slug": test_slug,
        "title": "n8n 自动化工作流架构专家",
        "icon": "⚡",
        "description": "智能生成标准 n8n 工作流 JSON 并支持安全推送到 n8n API 实例",
        "system_prompt": "你是一位资深 n8n 自动化专家与系统架构师。输出合法规范的 n8n workflow JSON，并在 ```json 代码块中返回。",
        "welcome_message": "您好！我是 n8n 工作流架构专家。请告诉我您的自动化需求！",
        "quick_prompts": ["每天早上 9 点抓取 GitHub trending 并发送邮件提醒", "监听 Webhook 并转存至数据库"],
        "skills": ["n8n-workflow-spec", "json-schema-validation"],
        "tools": [
            {
                "name": "create_n8n_workflow",
                "label": "创建 n8n 工作流 (POST /api/v1/workflows)",
                "description": "调用 n8n 官方 API 一键创建工作流",
                "endpoint": "https://n8n.example.com/api/v1/workflows",
                "method": "POST",
                "headers": {"X-N8N-API-KEY": "test-key-12345"},
                "payload_template": ""
            }
        ],
        "mcp_servers": []
    }

    gen_res = client.post(
        "/api/generator/agent?auto_publish=true",
        json=agent_req,
        headers=admin_headers
    )
    assert gen_res.status_code == 200, f"生成智能体失败: {gen_res.text}"
    gen_data = gen_res.json()
    app_slug = gen_data["slug"]
    print(f"✓ 4. 成功自动生成并发布智能体应用: /s/{app_slug}/")

    # 5. 验证发布的微应用代码中具备工具、Skills 与 n8n 一键推送逻辑
    source_res = client.get(f"/api/apps/{app_slug}/source")
    assert source_res.status_code == 200, f"获取微应用代码失败: {source_res.text}"
    html = source_res.json()["html_content"]

    # 校验代码中包含扩展抽屉和 n8n 推送工具
    assert "openToolsDrawerBtn" in html or "工具与扩展" in html or "API 工具接入" in html, "微应用中应包含工具面板"
    assert "create_n8n_workflow" in html, "微应用中应包含定义的 API 工具"
    assert "n8n-workflow-spec" in html or "n8n 工作流架构规范" in html, "微应用中应包含挂载的技能说明"
    assert "/api/agent/proxy-call" in html, "微应用中应使用后端 API 代理网关进行安全中继"
    assert "/api/ai/agent/stream" in html, "微应用应调用公开免密流式对话端点"
    print("✓ 5. 校验微应用源码: 成功注入 Tools 抽屉、Skills 技能包规范、n8n 工作流识别栏及 API 代理中继")

    # 6. 验证公开访问微应用与自增访问计数
    view_res = client.get(f"/s/{app_slug}/")
    assert view_res.status_code == 200, f"访问微应用失败: {view_res.status_code}"
    assert "n8n 自动化工作流架构专家" in view_res.text

    # 验证 app 访问计数增加了
    app_info = client.get(f"/api/apps/{app_slug}")
    assert app_info.status_code == 200
    assert app_info.json()["view_count"] >= 1
    print(f"✓ 6. 验证微应用公开访问成功，访问计数自增: {app_info.json()['view_count']}")

    # 7. 验证第三方 API 代理端点 (/api/agent/proxy-call)
    # 7.1 测试协议拦截 (非 http/https 拒绝)
    bad_proxy = client.post("/api/agent/proxy-call", json={
        "url": "ftp://malicious.host/test",
        "method": "POST"
    })
    assert bad_proxy.status_code == 400
    assert "只支持 HTTP/HTTPS" in bad_proxy.text
    print("✓ 7.1 验证 API 代理网关协议过滤机制正常 (阻止非 http/https)")

    # 7.2 测试连通性处理 (访问一个本地快速响应端点或测试响应结构)
    # 测试通过代理中继访问健康检查端点 (验证 endpoint 兼容别名)
    proxy_test = client.post("/api/agent/proxy-call", json={
        "endpoint": "http://127.0.0.1:8000/api/health",
        "method": "GET"
    })
    # 在测试客户端中，如果目标未启动单独端口可能连接失败，但代理端点本身应正常处理异常并返回 status_code
    assert proxy_test.status_code in [200, 502], f"代理测试状态码异常: {proxy_test.status_code}"
    print(f"✓ 7.2 验证 API 代理中继网关链路完整 (支持 endpoint 别名, 响应状态码: {proxy_test.status_code})")

    # 8. 清理测试产生的应用
    cleanup_res = client.delete(f"/api/apps/{app_slug}", headers=admin_headers)
    assert cleanup_res.status_code == 200
    print(f"✓ 8. 清理测试微应用 /s/{app_slug}/ 成功")

    print("\n🎉 === 所有 AI 智能体生成、MCP/API 工具、Skills 与中继端点自动化测试全部通过！ ===")

if __name__ == "__main__":
    test_agent_tools_and_ai_gen_pipeline()
