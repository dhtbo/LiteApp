"""
测试 LiteApp 的 MCP (Model Context Protocol) 核心服务逻辑与工具链
包括静态微应用发布、覆盖更新、详情与源码读取、列表查询与删除
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.service import mcp_service
from app.repository.database import init_db

def test_mcp_service_lifecycle():
    # 初始化数据库
    init_db()

    test_slug = "mcp-test-timer"
    test_title = "极简番茄钟 (MCP测试)"
    test_html = """<!DOCTYPE html>
<html>
<head><title>Timer</title></head>
<body><h1>25:00</h1></body>
</html>"""

    # 1. 确保旧测试残留已清理
    try:
        mcp_service.delete_static_app(test_slug)
    except Exception:
        pass

    # 2. 测试通过 MCP 发布静态单页
    pub_res = mcp_service.publish_static_app(
        title=test_title,
        html_content=test_html,
        slug=test_slug,
        description="这是一个由 MCP 自动发布的番茄钟静态微应用",
        category="实用工具",
        icon="⏱️",
        overwrite=True,
    )
    assert pub_res["status"] == "success"
    assert pub_res["action"] == "created"
    assert pub_res["slug"] == test_slug
    assert "/s/mcp-test-timer/" in pub_res["url_path"]

    # 3. 测试通过 MCP 读取微应用元数据与源码
    get_res = mcp_service.get_static_app(slug=test_slug)
    assert get_res["slug"] == test_slug
    assert get_res["title"] == test_title
    assert "25:00" in get_res["html_content"]

    # 4. 测试通过 MCP 覆盖更新源码 (产生新版本快照)
    updated_html = """<!DOCTYPE html>
<html>
<head><title>Timer v2</title></head>
<body><h1>50:00</h1><p>专注模式</p></body>
</html>"""
    update_res = mcp_service.publish_static_app(
        title="双倍番茄钟 (MCP更新)",
        html_content=updated_html,
        slug=test_slug,
        description="更新为 50 分钟沉浸专注模式",
        category="效率办公",
        icon="🔥",
        overwrite=True,
    )
    assert update_res["status"] == "success"
    assert update_res["action"] == "updated"

    # 验证源码已更新
    get_res2 = mcp_service.get_static_app(slug=test_slug)
    assert "50:00" in get_res2["html_content"]
    assert get_res2["icon"] == "🔥"

    # 5. 测试通过 MCP 查询微应用列表
    list_res = mcp_service.list_static_apps(search="番茄钟")
    assert list_res["total"] >= 1
    slugs = [a["slug"] for a in list_res["apps"]]
    assert test_slug in slugs

    # 6. 测试通过 MCP 删除微应用
    del_res = mcp_service.delete_static_app(test_slug)
    assert del_res["status"] == "success"
    assert del_res["slug"] == test_slug

    # 再次查询确认已不存在
    try:
        mcp_service.get_static_app(test_slug)
        assert False, "应当抛出 404 异常"
    except Exception as e:
        assert "未找到微应用" in str(e)
