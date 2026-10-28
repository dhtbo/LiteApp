import sqlite3
from typing import List, Optional
from app.model.models import LLMProviderModel
from app.repository.database import get_connection
from app.core.logger import logger

def row_to_provider(row: sqlite3.Row) -> LLMProviderModel:
    """
    将 sqlite3.Row 映射为 LLMProviderModel 实体
    """
    return LLMProviderModel(
        id=row["id"],
        name=row["name"],
        base_url=row["base_url"],
        api_key=row["api_key"],
        model_name=row["model_name"],
        is_active=row["is_active"],
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
    )

def list_providers() -> List[LLMProviderModel]:
    """
    查询所有已配置的 LLM 提供商
    
    :returns: LLM 提供商列表
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM llm_providers ORDER BY is_active DESC, updated_at DESC, id DESC")
        rows = cursor.fetchall()
        return [row_to_provider(r) for r in rows]
    finally:
        conn.close()

def get_provider_by_id(provider_id: int) -> Optional[LLMProviderModel]:
    """
    根据主键 ID 获取提供商信息
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM llm_providers WHERE id = ? LIMIT 1", (provider_id,))
        row = cursor.fetchone()
        return row_to_provider(row) if row else None
    finally:
        conn.close()

def get_active_provider() -> Optional[LLMProviderModel]:
    """
    获取当前被激活的默认大模型配置
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM llm_providers WHERE is_active = 1 LIMIT 1")
        row = cursor.fetchone()
        if row:
            return row_to_provider(row)
        # 如果没有显式激活项，取第一条
        cursor.execute("SELECT * FROM llm_providers ORDER BY id ASC LIMIT 1")
        row = cursor.fetchone()
        return row_to_provider(row) if row else None
    finally:
        conn.close()

def create_provider(provider: LLMProviderModel) -> LLMProviderModel:
    """
    新增大模型提供商配置
    """
    conn = get_connection()
    try:
        with conn:
            cursor = conn.cursor()
            if provider.is_active:
                cursor.execute("UPDATE llm_providers SET is_active = 0")
            cursor.execute(
                """
                INSERT INTO llm_providers (name, base_url, api_key, model_name, is_active)
                VALUES (?, ?, ?, ?, ?)
                """,
                (provider.name, provider.base_url, provider.api_key, provider.model_name, provider.is_active)
            )
            provider.id = cursor.lastrowid
            logger.info(f"成功新增 LLM 提供商: id={provider.id}, name={provider.name}")
            return provider
    finally:
        conn.close()

def update_provider(
    provider_id: int,
    name: Optional[str] = None,
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
    model_name: Optional[str] = None,
    is_active: Optional[bool] = None,
) -> Optional[LLMProviderModel]:
    """
    更新大模型提供商参数
    """
    conn = get_connection()
    try:
        with conn:
            cursor = conn.cursor()
            if is_active is True:
                cursor.execute("UPDATE llm_providers SET is_active = 0")

            fields = []
            params = []
            if name is not None:
                fields.append("name = ?")
                params.append(name)
            if base_url is not None:
                fields.append("base_url = ?")
                params.append(base_url)
            if api_key is not None and api_key.strip():
                fields.append("api_key = ?")
                params.append(api_key.strip())
            if model_name is not None:
                fields.append("model_name = ?")
                params.append(model_name)
            if is_active is not None:
                fields.append("is_active = ?")
                params.append(1 if is_active else 0)

            if not fields:
                return get_provider_by_id(provider_id)

            fields.append("updated_at = CURRENT_TIMESTAMP")
            params.append(provider_id)

            cursor.execute(f"UPDATE llm_providers SET {', '.join(fields)} WHERE id = ?", params)
            if cursor.rowcount == 0:
                return None
        return get_provider_by_id(provider_id)
    finally:
        conn.close()

def set_active_provider(provider_id: int) -> bool:
    """
    将指定 ID 的提供商设为全局激活
    """
    conn = get_connection()
    try:
        with conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE llm_providers SET is_active = 0")
            cursor.execute("UPDATE llm_providers SET is_active = 1, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (provider_id,))
            return cursor.rowcount > 0
    finally:
        conn.close()

def delete_provider(provider_id: int) -> bool:
    """
    删除大模型提供商配置
    """
    conn = get_connection()
    try:
        with conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM llm_providers WHERE id = ?", (provider_id,))
            return cursor.rowcount > 0
    finally:
        conn.close()
