import sqlite3
from typing import List, Optional
from app.model.models import FormSubmissionModel
from app.repository.database import get_connection
from app.core.logger import logger

def row_to_submission(row: sqlite3.Row) -> FormSubmissionModel:
    """
    将 sqlite3.Row 映射为 FormSubmissionModel 实体
    """
    return FormSubmissionModel(
        id=row["id"],
        form_slug=row["form_slug"],
        data_json=row["data_json"],
        ip_address=row["ip_address"] or "",
        user_agent=row["user_agent"] or "",
        created_at=str(row["created_at"]),
    )

def create_submission(
    form_slug: str,
    data_json: str,
    ip_address: str = "",
    user_agent: str = "",
) -> FormSubmissionModel:
    """
    持久化存储一条表单采集数据
    """
    conn = get_connection()
    try:
        with conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO form_submissions (form_slug, data_json, ip_address, user_agent)
                VALUES (?, ?, ?, ?)
                """,
                (form_slug, data_json, ip_address, user_agent)
            )
            sub_id = cursor.lastrowid
            cursor.execute("SELECT * FROM form_submissions WHERE id = ?", (sub_id,))
            row = cursor.fetchone()
            logger.info(f"成功保存表单提交数据: form_slug={form_slug}, id={sub_id}")
            return row_to_submission(row)
    finally:
        conn.close()

def list_submissions(form_slug: str, limit: int = 1000) -> List[FormSubmissionModel]:
    """
    获取指定表单收集到的所有历史提交数据（按时间倒序）
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM form_submissions WHERE form_slug = ? ORDER BY id DESC LIMIT ?",
            (form_slug, limit)
        )
        rows = cursor.fetchall()
        return [row_to_submission(r) for r in rows]
    finally:
        conn.close()

def count_submissions(form_slug: str) -> int:
    """
    统计指定表单的提交总条数
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) AS cnt FROM form_submissions WHERE form_slug = ?", (form_slug,))
        row = cursor.fetchone()
        return row["cnt"] if row else 0
    finally:
        conn.close()

def delete_submissions_by_slug(form_slug: str) -> int:
    """
    删除指定表单的所有采集数据记录
    """
    conn = get_connection()
    try:
        with conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM form_submissions WHERE form_slug = ?", (form_slug,))
            return cursor.rowcount
    finally:
        conn.close()
