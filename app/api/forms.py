import io
import csv
import json
from typing import Dict, Any, List
from fastapi import APIRouter, Depends, Request, Response, HTTPException, status
from app.api.deps import verify_admin_token
from app.repository import form_repo, app_repo
from app.core.logger import logger

router = APIRouter(prefix="/api/forms", tags=["表单数据采集引擎"])

@router.post("/{form_slug}/submit", summary="提交采集表单数据 (公开接口)")
async def submit_form_data(
    form_slug: str,
    payload: Dict[str, Any],
    request: Request,
) -> dict:
    """
    接收用户在微应用采集表单填报的数据，自动持久化存储至 SQLite 数据库
    """
    client_ip = request.client.host if request.client else ""
    user_agent = request.headers.get("user-agent", "")

    # 去除内部临时保留字段
    clean_data = {k: v for k, v in payload.items() if not k.startswith("_")}
    data_json_str = json.dumps(clean_data, ensure_ascii=False)

    record = form_repo.create_submission(
        form_slug=form_slug,
        data_json=data_json_str,
        ip_address=client_ip,
        user_agent=user_agent,
    )

    return {
        "success": True,
        "id": record.id,
        "message": "表单数据提交成功，已安全入库保存",
        "created_at": record.created_at,
    }

@router.get("/{form_slug}/submissions", summary="查看表单已收集数据列表 (需管理员权限)")
async def get_form_submissions(
    form_slug: str,
    limit: int = 500,
    _: bool = Depends(verify_admin_token),
) -> dict:
    """
    获取指定表单收集到的所有数据条目与总数
    """
    total = form_repo.count_submissions(form_slug)
    records = form_repo.list_submissions(form_slug, limit=limit)
    items = []
    for r in records:
        try:
            parsed = json.loads(r.data_json)
        except Exception:
            parsed = {}
        items.append({
            "id": r.id,
            "created_at": r.created_at,
            "ip_address": r.ip_address,
            "data": parsed,
        })

    return {
        "form_slug": form_slug,
        "total": total,
        "items": items,
    }

@router.get("/{form_slug}/export", summary="一键导出已收集数据为 CSV (需管理员权限)")
async def export_form_submissions_csv(
    form_slug: str,
    _: bool = Depends(verify_admin_token),
) -> Response:
    """
    将已收集的所有数据汇总导出为带 BOM 的 UTF-8 CSV 电子表格
    """
    records = form_repo.list_submissions(form_slug, limit=5000)
    if not records:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="暂无已收集的数据")

    # 提取所有不重复的字段名作为表头
    headers_set = []
    rows_data = []
    for r in records:
        try:
            d = json.loads(r.data_json)
        except Exception:
            d = {}
        for k in d.keys():
            if k not in headers_set:
                headers_set.append(k)
        rows_data.append((r.id, r.created_at, r.ip_address, d))

    output = io.StringIO()
    writer = csv.writer(output)
    full_headers = ["ID", "提交时间", "提交IP"] + headers_set
    writer.writerow(full_headers)

    for rid, created_at, ip, d in rows_data:
        row = [rid, created_at, ip] + [d.get(h, "") for h in headers_set]
        writer.writerow(row)

    csv_content = "\ufeff" + output.getvalue()
    return Response(
        content=csv_content.encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f"attachment; filename={form_slug}_submissions.csv"
        }
    )
