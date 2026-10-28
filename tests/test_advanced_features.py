import os
import sys
import io
import csv
import json
from pathlib import Path

# 确保项目根目录在 python path 中，避免 ModuleNotFoundError
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# 控制台 UTF-8 输出
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from fastapi.testclient import TestClient
from app.main import app
from app.core.config import settings

client = TestClient(app)

def test_full_advanced_pipeline():
    print("=== 开始全流程验证进阶特性 ===")

    # 1. 管理员登录并获取鉴权 Token
    admin_pwd = settings.ADMIN_PASSWORD
    login_res = client.post("/api/auth/login", json={"password": admin_pwd})
    assert login_res.status_code == 200, f"登录失败: {login_res.text}"
    token = login_res.json()["token"]
    headers = {"X-Admin-Token": token}
    print("✓ 1. 管理员鉴权成功")

    # 2. 创建一个测试微应用 v1
    test_slug = "test-agent-suite"
    # 先清理可能存在的旧数据
    client.delete(f"/api/apps/{test_slug}", headers=headers)

    create_payload = {
        "slug": test_slug,
        "title": "测试微应用-初代",
        "description": "初始版本描述",
        "category": "效率工具",
        "icon": "🧪",
        "html_content": "<html><head><title>Version 1</title></head><body><h1>Hello V1</h1></body></html>"
    }
    create_res = client.post("/api/apps", json=create_payload, headers=headers)
    assert create_res.status_code == 200, f"创建应用失败: {create_res.text}"
    print("✓ 2. 成功创建测试微应用 v1 并自动生成初版快照")

    # 3. 验证微应用源码获取接口 (用于 AI 工坊二次编辑加载)
    source_res = client.get(f"/api/apps/{test_slug}/source")
    assert source_res.status_code == 200, f"获取源码失败: {source_res.text}"
    source_data = source_res.json()
    assert "Version 1" in source_data["html_content"]
    assert source_data["title"] == "测试微应用-初代"
    print("✓ 3. 源码读取成功 (支持在 AI 工坊中 100% 还原代码与二次迭代)")

    # 4. 覆盖更新微应用为 v2
    v2_html = "<html><head><title>Version 2</title></head><body><h1>Hello V2 Updated</h1></body></html>"
    overwrite_res = client.post(
        f"/api/apps/{test_slug}/overwrite",
        data={"html_content": v2_html, "description": "更新为带有新特性的 V2 版本"},
        headers=headers,
    )
    assert overwrite_res.status_code == 200, f"覆盖更新失败: {overwrite_res.text}"
    print("✓ 4. 成功覆盖更新微应用为 v2，并自动归档新快照")

    # 5. 获取版本历史列表
    versions_res = client.get(f"/api/apps/{test_slug}/versions")
    assert versions_res.status_code == 200, f"获取版本列表失败: {versions_res.text}"
    versions = versions_res.json()
    assert len(versions) >= 2, f"版本数量异常: {len(versions)}"
    print(f"✓ 5. 成功查询版本历史列表: 共 {len(versions)} 个快照版本")
    for v in versions:
        print(f"   - v{v['version_num']}: {v['description']} ({v['created_at']})")

    # 6. 验证历史版本预览接口
    v1_id = versions[-1]["id"]  # 初始版本
    preview_res = client.get(f"/api/apps/{test_slug}/versions/{v1_id}/preview")
    assert preview_res.status_code == 200
    assert "Version 1" in preview_res.text
    print(f"✓ 6. 成功预览历史快照版本 (v{versions[-1]['version_num']})")

    # 7. 验证一键版本回滚
    rollback_res = client.post(f"/api/apps/{test_slug}/versions/{v1_id}/rollback", headers=headers)
    assert rollback_res.status_code == 200, f"回滚失败: {rollback_res.text}"
    # 验证当前应用的实际文件内容已被还原
    source_after_rollback = client.get(f"/api/apps/{test_slug}/source").json()
    assert "Version 1" in source_after_rollback["html_content"]
    print("✓ 7. 成功执行一键版本回滚，线上目录已安全恢复为 V1 内容！")

    # 8. 验证 AI 对话智能体单页生成器
    agent_gen_res = client.post(
        "/api/generator/agent?auto_publish=true",
        json={
            "title": "法律咨询专属助手",
            "icon": "⚖️",
            "description": "企业合规与法务解答",
            "system_prompt": "你是一名资深中国执业律师，擅长民商法。",
            "welcome_message": "您好，请问有什么法律疑问？",
            "quick_prompts": ["劳动合同违约金条款如何约定", "公司股权转让注意事项"],
            "slug": "legal-advisor-bot"
        },
        headers=headers,
    )
    assert agent_gen_res.status_code == 200, f"生成智能体失败: {agent_gen_res.text}"
    agent_data = agent_gen_res.json()
    assert "法律咨询专属助手" in agent_data["html_content"]
    assert "lucide" in agent_data["html_content"]
    print("✓ 8. 成功生成并自动发布 AI 对话智能体微应用: /s/legal-advisor-bot/")

    # 9. 验证 n8n 自动化微应用生成器
    n8n_gen_res = client.post(
        "/api/generator/n8n?auto_publish=true",
        json={
            "title": "n8n 数据触发看板",
            "icon": "⚡",
            "mode": "webhook",
            "webhook_url": "https://httpbin.org/post",
            "http_method": "POST",
            "slug": "n8n-trigger-board"
        },
        headers=headers,
    )
    assert n8n_gen_res.status_code == 200, f"生成 n8n 看板失败: {n8n_gen_res.text}"
    assert "n8n 数据触发看板" in n8n_gen_res.json()["html_content"]
    print("✓ 9. 成功生成并自动发布 n8n Webhook 触发看板微应用: /s/n8n-trigger-board/")

    # 10. 验证自然语言需求生成动态数据采集表单
    form_gen_res = client.post(
        "/api/generator/form-prompt?auto_publish=true",
        json={
            "title": "客户满意度问卷表单",
            "icon": "📋",
            "prompt": "包含客户姓名、联系电话、所属公司、服务满意度评分、改进建议、是否愿意推荐",
            "slug": "feedback-survey-form"
        },
        headers=headers,
    )
    assert form_gen_res.status_code == 200, f"生成表单失败: {form_gen_res.text}"
    form_html = form_gen_res.json()["html_content"]
    assert "客户满意度问卷表单" in form_html
    assert "导出 CSV" in form_html
    print("✓ 10. 成功根据自然语言需求生成带本地存储与 CSV 导出的动态采集表单: /s/feedback-survey-form/")

    # 11. 验证上传表格文件 (.csv) 提取字段生成表单
    csv_buffer = io.StringIO()
    writer = csv.writer(csv_buffer)
    writer.writerow(["姓名", "电子邮箱", "手机号", "应聘职位", "期望薪资", "自我评价", "是否已离职"])
    writer.writerow(["张三", "zhangsan@test.com", "13800138000", "全栈工程师", "25000", "具有丰富全栈经验", "是"])
    csv_bytes = csv_buffer.getvalue().encode("utf-8")

    file_form_res = client.post(
        "/api/generator/form-file",
        files={"file": ("interview.csv", csv_bytes, "text/csv")},
        data={
            "title": "面试应聘信息登记表",
            "icon": "💼",
            "category": "人事行政",
            "slug": "interview-reg-form",
            "auto_publish": "true"
        },
        headers=headers,
    )
    assert file_form_res.status_code == 200, f"文件推导生成表单失败: {file_form_res.text}"
    file_form_html = file_form_res.json()["html_content"]
    assert "面试应聘信息登记表" in file_form_html
    assert "应聘职位" in file_form_html
    print("✓ 11. 成功解析上传的 CSV 表格并推断字段，生成并自动发布数据录入表单: /s/interview-reg-form/")

    # 12. 验证表单数据提交与后端 SQLite 持久化
    sub_res = client.post(
        "/api/forms/interview-reg-form/submit",
        json={
            "field_1": "李四",
            "field_2": "lisi@example.com",
            "field_3": "13912345678",
            "field_4": "高级前端开发",
            "field_5": "28000",
            "field_6": "精通 Vue3/React 与 Tailwind",
            "field_7": "否"
        }
    )
    assert sub_res.status_code == 200, f"表单提交失败: {sub_res.text}"
    print("✓ 12. 客户端公开提交表单数据成功，数据已持久化至后端 SQLite")

    # 13. 验证管理员查看已收集数据列表与导出 CSV
    list_subs_res = client.get("/api/forms/interview-reg-form/submissions", headers=headers)
    assert list_subs_res.status_code == 200
    subs_data = list_subs_res.json()
    assert subs_data["total"] >= 1
    assert subs_data["items"][0]["data"]["field_1"] == "李四"
    print(f"✓ 13. 管理员成功查询表单入库记录: 共 {subs_data['total']} 条数据")

    export_res = client.get("/api/forms/interview-reg-form/export", headers=headers)
    assert export_res.status_code == 200
    assert "text/csv" in export_res.headers["content-type"]
    assert "李四" in export_res.text
    print("✓ 14. 成功导出表单已收集数据为完整 CSV 报表")

    # 15. 验证已发布的各应用在静态路由 /s/{slug}/ 可正常访问
    for slug in ["test-agent-suite", "legal-advisor-bot", "n8n-trigger-board", "feedback-survey-form", "interview-reg-form"]:
        site_res = client.get(f"/s/{slug}/")
        assert site_res.status_code == 200, f"访问静态应用 /s/{slug}/ 失败: {site_res.status_code}"
    print("✓ 15. 验证所有新生成的微应用静态路由 /s/{slug}/ 均可顺畅访问！")

    # 清理测试应用
    for slug in ["test-agent-suite", "legal-advisor-bot", "n8n-trigger-board", "feedback-survey-form", "interview-reg-form"]:
        client.delete(f"/api/apps/{slug}", headers=headers)
    print("✓ 16. 测试环境资源自动清理完毕")

    print("\n🎉🎉🎉 全部进阶特性与表单采集引擎测试 100% 通过！")

if __name__ == "__main__":
    test_full_advanced_pipeline()
