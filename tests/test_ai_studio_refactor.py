"""
测试 Google AI Studio 风格重构特性的后端与前端资产集成测试
"""
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_static_ui_contains_ai_studio_features():
    """验证前端静态页面完整包含 Google AI Studio 经典设计规范元素"""
    response = client.get("/")
    assert response.status_code == 200
    html_text = response.text

    # 1. 验证 Google AI Studio 顶栏与内联标题
    assert "studioTitle" in html_text
    assert "startEditStudioTitle" in html_text
    assert "isEditingStudioTitle" in html_text

    # 2. 验证 Get Code 生产级代码导出模态与特性
    assert "Get Code" in html_text
    assert "showGetCodeModal" in html_text
    assert "getCodeLang" in html_text
    assert "currentSnippetCode" in html_text
    assert "copySnippetCode" in html_text

    # 3. 验证 System Instructions 可折叠面板与 AI 增强优化
    assert "System Instructions" in html_text
    assert "showSystemInstruction" in html_text
    assert "systemInstructionText" in html_text
    assert "optimizeSystemInstruction" in html_text
    assert "resetSystemInstruction" in html_text

    # 4. 验证 Run Settings 运行参数检查器与滑块
    assert "Run Settings" in html_text
    assert "runSettings.temperature" in html_text
    assert "runSettings.top_p" in html_text
    assert "runSettings.max_tokens" in html_text
    assert "rightPanelTab" in html_text

    # 5. 验证快捷键支持
    assert "Ctrl+Enter" in html_text


def test_ai_chat_stream_with_system_instruction_and_hyperparameters(monkeypatch):
    """验证后端 /api/ai/chat/stream 接口正确接收并透传自定义 System Instruction、Temperature、Top P 与 Max Tokens"""
    # 模拟有效的 admin 登录以获取 token
    import os
    admin_pw = os.getenv("ADMIN_PASSWORD", "admin888")
    login_resp = client.post("/api/auth/login", json={"password": admin_pw})
    assert login_resp.status_code == 200
    token = login_resp.json()["token"]

    captured_payload = {}

    # Mock stream_openai_chat 验证参数接收与透传
    async def mock_stream_openai_chat(provider, messages, temperature=0.7, system_instruction=None, max_tokens=None, top_p=None):
        captured_payload["provider"] = provider
        captured_payload["messages"] = messages
        captured_payload["system_instruction"] = system_instruction
        captured_payload["temperature"] = temperature
        captured_payload["top_p"] = top_p
        captured_payload["max_tokens"] = max_tokens
        yield "data: {\"content\": \"<!DOCTYPE html><html><body><h1>Studio Hello</h1></body></html>\"}\n\n"
        yield "data: [DONE]\n\n"

    from app.api import llm
    monkeypatch.setattr(llm, "stream_openai_chat", mock_stream_openai_chat)

    custom_sys = "你是一位极简主义的前端架构师，只输出单文件 HTML。"
    chat_resp = client.post(
        "/api/ai/chat/stream",
        headers={"X-Admin-Token": token},
        json={
            "messages": [{"role": "user", "content": "创建一个极简时钟"}],
            "system_instruction": custom_sys,
            "temperature": 1.25,
            "top_p": 0.85,
            "max_tokens": 2048,
        }
    )

    assert chat_resp.status_code == 200
    assert captured_payload["system_instruction"] == custom_sys
    assert captured_payload["temperature"] == 1.25
    assert captured_payload["top_p"] == 0.85
    assert captured_payload["max_tokens"] == 2048
    assert "Studio Hello" in chat_resp.text


def test_system_instruction_optimization_field_generator(monkeypatch):
    """验证 System Instructions 可利用 /api/ai/generate-field 进行 AI 增强扩写"""
    import os
    admin_pw = os.getenv("ADMIN_PASSWORD", "admin888")
    login_resp = client.post("/api/auth/login", json={"password": admin_pw})
    token = login_resp.json()["token"]

    from app.api import llm
    async def mock_generate_field_with_ai(field_type, context, provider=None):
        return "增强后的专业 System Prompt：遵循严谨的设计原则与语义化 HTML 规范。"

    monkeypatch.setattr(llm, "generate_field_with_ai", mock_generate_field_with_ai)

    res = client.post(
        "/api/ai/generate-field",
        headers={"X-Admin-Token": token},
        json={
            "field_type": "prompt",
            "context": "写一个贪吃蛇游戏"
        }
    )

    assert res.status_code == 200
    data = res.json()
    assert "增强后的专业" in data["generated_content"]
