import sys
from pathlib import Path

# 确保项目根目录在 python path 中
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from fastapi.testclient import TestClient
from app.main import app
from app.core.config import settings

client = TestClient(app)

def test_system_config_endpoints():
    # 1. 未登录读取配置（公开字段）
    res = client.get("/api/system/config")
    assert res.status_code == 200
    data = res.json()
    assert "n8n_base_url" in data
    assert "n8n_api_key" in data
    assert data["n8n_base_url"].startswith("http")

    # 2. 未登录修改配置被拦截
    unauth_res = client.post("/api/system/config", json={
        "n8n_base_url": "https://ai.ljcode.cn",
        "n8n_api_key": "test-key"
    })
    assert unauth_res.status_code in [401, 403]

    # 3. 登录管理员
    login_res = client.post("/api/auth/login", json={"password": settings.ADMIN_PASSWORD})
    assert login_res.status_code == 200
    token = login_res.json()["token"]

    # 4. 管理员保存新配置
    save_res = client.post(
        "/api/system/config",
        json={
            "n8n_base_url": "https://ai.ljcode.cn",
            "n8n_api_key": "test_n8n_api_key_valid"
        },
        headers={"X-Admin-Token": token}
    )
    assert save_res.status_code == 200
    save_data = save_res.json()
    assert save_data["n8n_base_url"] == "https://ai.ljcode.cn"

    # 5. 再次读取确认更新
    res_after = client.get("/api/system/config")
    assert res_after.status_code == 200
    assert res_after.json()["n8n_base_url"] == "https://ai.ljcode.cn"
