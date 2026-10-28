import sys
import os
import io
import asyncio
import zipfile

sys.path.insert(0, os.path.abspath("."))
# 确保在 Windows 控制台输出正常显示
sys.stdout.reconfigure(encoding='utf-8')

from httpx import AsyncClient, ASGITransport
from app.main import app
from app.repository.database import init_db

async def run_tests():
    init_db()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. 健康检查
        r = await client.get("/api/health")
        assert r.status_code == 200, f"Health check failed: {r.status_code}"
        print("✓ Health check passed:", r.json())

        # 2. 获取预置应用
        r = await client.get("/api/apps")
        assert r.status_code == 200
        data = r.json()
        assert data["total"] >= 1
        slugs = [x["slug"] for x in data["items"]]
        print(f"✓ Apps list passed (found {data['total']} apps): {slugs}")

        # 3. 访问微应用重定向与首页
        r = await client.get("/s/welcome-timer", follow_redirects=False)
        assert r.status_code in (301, 302, 307), f"Expected redirect, got {r.status_code}"
        print("✓ /s/welcome-timer redirect passed:", r.headers.get("location"))

        r = await client.get("/s/welcome-timer/")
        assert r.status_code == 200
        assert "LiteApp Studio" in r.text
        print("✓ /s/welcome-timer/ served correctly")

        # 4. 管理员登录
        r = await client.post("/api/auth/login", json={"password": "wrong_password"})
        assert r.status_code == 401
        r = await client.post("/api/auth/login", json={"password": "admin888"})
        assert r.status_code == 200
        token = r.json()["token"]
        print("✓ Admin login passed, token generated")

        # 5. 鉴权测试
        r = await client.get("/api/auth/status", headers={"X-Admin-Token": token})
        assert r.json()["authenticated"] is True
        print("✓ Auth status check passed")

        # 清理旧测试残留数据
        await client.delete("/api/apps/test-counter", headers={"X-Admin-Token": token})
        await client.delete("/api/apps/test-zip-app", headers={"X-Admin-Token": token})
        await client.delete("/api/apps/evil-test", headers={"X-Admin-Token": token})

        # 6. 创建新微应用测试
        create_payload = {
            "slug": "test-counter",
            "title": "测试计数器",
            "description": "单元测试自动生成",
            "category": "测试",
            "icon": "🧪",
            "html_content": "<!DOCTYPE html><html><body><h1>Hello Test</h1></body></html>"
        }
        r = await client.post("/api/apps", json=create_payload, headers={"X-Admin-Token": token})
        assert r.status_code == 200, f"Create app failed: {r.text}"
        print("✓ App creation passed:", r.json()["slug"])

        # 访问刚创建的微应用
        r = await client.get("/s/test-counter/")
        assert r.status_code == 200
        assert "Hello Test" in r.text
        print("✓ Created app served correctly")

        # 7. ZIP 智能解包与扁平化测试 (模拟 dist/index.html 结构)
        zip_buf = io.BytesIO()
        with zipfile.ZipFile(zip_buf, "w") as zf:
            zf.writestr("my-build-dist/index.html", "<!DOCTYPE html><html><body><h1>Zip Flattened App</h1></body></html>")
            zf.writestr("my-build-dist/assets/app.js", "console.log('loaded');")
        zip_buf.seek(0)

        files = {"file": ("my-app.zip", zip_buf.getvalue(), "application/zip")}
        data = {
            "slug": "test-zip-app",
            "title": "ZIP 智能扁平化测试应用",
            "description": "自动消除外层目录测试",
            "category": "测试",
            "icon": "📦",
        }
        r = await client.post("/api/apps/upload", data=data, files=files, headers={"X-Admin-Token": token})
        assert r.status_code == 200, f"ZIP upload failed: {r.text}"
        print("✓ ZIP upload with smart flattening passed")

        # 验证解压后 /s/test-zip-app/ 可直接访问 index.html 与 assets/app.js
        r = await client.get("/s/test-zip-app/")
        assert r.status_code == 200
        assert "Zip Flattened App" in r.text
        print("✓ Flattened index.html verified successfully")

        r = await client.get("/s/test-zip-app/assets/app.js")
        assert r.status_code == 200
        assert "console.log" in r.text
        print("✓ Relative asset assets/app.js served correctly")

        # 清理可能残留的测试应用
        await client.delete("/api/apps/evil-test", headers={"X-Admin-Token": token})

        # 8. Zip Slip 恶意包防御测试
        evil_zip_buf = io.BytesIO()
        with zipfile.ZipFile(evil_zip_buf, "w") as zf:
            zf.writestr("../evil.txt", "pwned")
        evil_zip_buf.seek(0)

        evil_files = {"file": ("evil.zip", evil_zip_buf.getvalue(), "application/zip")}
        evil_data = {
            "slug": "evil-test",
            "title": "恶意攻击包测试",
            "description": "验证 Zip Slip",
            "category": "测试",
            "icon": "⚠️",
        }
        r = await client.post("/api/apps/upload", data=evil_data, files=evil_files, headers={"X-Admin-Token": token})
        assert r.status_code == 400
        assert "路径穿越" in r.json()["detail"] or "非法" in r.json()["detail"]
        print("✓ Zip Slip defense passed! Successfully rejected malicious ZIP")

        # 9. 清理测试产生的应用
        r = await client.delete("/api/apps/test-counter", headers={"X-Admin-Token": token})
        assert r.status_code == 200
        r = await client.delete("/api/apps/test-zip-app", headers={"X-Admin-Token": token})
        assert r.status_code == 200
        await client.delete("/api/apps/evil-test", headers={"X-Admin-Token": token})
        print("✓ Test cleanup completed successfully")

if __name__ == "__main__":
    asyncio.run(run_tests())
