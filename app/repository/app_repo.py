import sqlite3
from typing import List, Optional
from app.model.models import AppModel, AppVersionModel
from app.repository.database import get_connection
from app.core.logger import logger

def row_to_app(row: sqlite3.Row) -> AppModel:
    """
    将 sqlite3.Row 映射为 AppModel 实体
    """
    return AppModel(
        id=row["id"],
        slug=row["slug"],
        title=row["title"],
        description=row["description"],
        category=row["category"],
        icon=row["icon"],
        entry_type=row["entry_type"],
        view_count=row["view_count"],
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
    )

def list_apps(category: Optional[str] = None, search: Optional[str] = None) -> List[AppModel]:
    """
    根据分类和关键词搜索获取微应用列表
    
    :param category: 分类过滤条件
    :param search: 关键词搜索（支持匹配 slug、title、description）
    :returns: 微应用实体列表
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        query = "SELECT * FROM apps WHERE 1=1"
        params: List[str] = []

        if category and category.strip() and category != "全部":
            query += " AND category = ?"
            params.append(category.strip())

        if search and search.strip():
            kw = f"%{search.strip()}%"
            query += " AND (slug LIKE ? OR title LIKE ? OR description LIKE ?)"
            params.extend([kw, kw, kw])

        query += " ORDER BY updated_at DESC, id DESC"
        cursor.execute(query, params)
        rows = cursor.fetchall()
        return [row_to_app(r) for r in rows]
    finally:
        conn.close()

def get_app_by_slug(slug: str) -> Optional[AppModel]:
    """
    根据唯一标识 Slug 查询微应用
    
    :param slug: 应用唯一标识
    :returns: 微应用实体或 None
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM apps WHERE slug = ? LIMIT 1", (slug,))
        row = cursor.fetchone()
        return row_to_app(row) if row else None
    finally:
        conn.close()

def create_app(app: AppModel) -> AppModel:
    """
    新增微应用元数据记录
    
    :param app: 微应用实体
    :returns: 创建成功后的微应用实体（含自增 ID）
    """
    conn = get_connection()
    try:
        with conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO apps (slug, title, description, category, icon, entry_type, view_count)
                VALUES (?, ?, ?, ?, ?, ?, 0)
                """,
                (app.slug, app.title, app.description, app.category, app.icon, app.entry_type)
            )
            app.id = cursor.lastrowid
            logger.info(f"成功入库微应用元数据: slug={app.slug}, id={app.id}")
            return app
    finally:
        conn.close()

def update_app_metadata(
    slug: str,
    title: Optional[str] = None,
    description: Optional[str] = None,
    category: Optional[str] = None,
    icon: Optional[str] = None,
) -> Optional[AppModel]:
    """
    更新已有微应用的元信息
    
    :param slug: 应用 Slug
    :returns: 更新后的实体或 None
    """
    conn = get_connection()
    try:
        with conn:
            cursor = conn.cursor()
            fields = []
            params = []
            if title is not None:
                fields.append("title = ?")
                params.append(title)
            if description is not None:
                fields.append("description = ?")
                params.append(description)
            if category is not None:
                fields.append("category = ?")
                params.append(category)
            if icon is not None:
                fields.append("icon = ?")
                params.append(icon)

            if not fields:
                return get_app_by_slug(slug)

            fields.append("updated_at = CURRENT_TIMESTAMP")
            params.append(slug)

            set_clause = ", ".join(fields)
            cursor.execute(f"UPDATE apps SET {set_clause} WHERE slug = ?", params)
            if cursor.rowcount == 0:
                return None
        return get_app_by_slug(slug)
    finally:
        conn.close()

def update_app_entry_type(slug: str, entry_type: str) -> None:
    """
    更新微应用的入口类型（例如从 html 变为 zip）
    """
    conn = get_connection()
    try:
        with conn:
            conn.execute(
                "UPDATE apps SET entry_type = ?, updated_at = CURRENT_TIMESTAMP WHERE slug = ?",
                (entry_type, slug)
            )
    finally:
        conn.close()

def increment_view_count(slug: str) -> None:
    """
    原子累加微应用访问计数
    
    :param slug: 应用 Slug
    """
    conn = get_connection()
    try:
        with conn:
            conn.execute("UPDATE apps SET view_count = view_count + 1 WHERE slug = ?", (slug,))
    except Exception as e:
        logger.warning(f"累加微应用访问计数失败: slug={slug}, err={e}")
    finally:
        conn.close()

def delete_app(slug: str) -> bool:
    """
    根据 Slug 从数据库删除微应用记录及版本快照历史
    
    :param slug: 应用唯一标识
    :returns: 是否成功删除
    """
    conn = get_connection()
    try:
        with conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM form_submissions WHERE form_slug = ?", (slug,))
            cursor.execute("DELETE FROM app_versions WHERE app_slug = ?", (slug,))
            cursor.execute("DELETE FROM apps WHERE slug = ?", (slug,))
            return cursor.rowcount > 0
    finally:
        conn.close()

def get_all_categories() -> List[str]:
    """
    获取数据库中现存的所有不重复分类列表
    
    :returns: 分类字符串列表
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT category FROM apps WHERE category IS NOT NULL AND category != '' ORDER BY category ASC")
        rows = cursor.fetchall()
        cats = [r["category"] for r in rows]
        # 始终包含基础分类
        defaults = ["效率工具", "实用小工具", "小游戏", "数据可视化", "娱乐日常"]
        merged = list(dict.fromkeys(defaults + cats))
        return merged
    finally:
        conn.close()

def row_to_version(row: sqlite3.Row) -> AppVersionModel:
    """
    将 sqlite3.Row 映射为 AppVersionModel 实体
    """
    return AppVersionModel(
        id=row["id"],
        app_slug=row["app_slug"],
        version_num=row["version_num"],
        entry_type=row["entry_type"],
        description=row["description"],
        storage_path=row["storage_path"],
        created_at=str(row["created_at"]),
    )

def create_app_version(
    app_slug: str,
    entry_type: str,
    description: str,
    storage_path: str,
) -> AppVersionModel:
    """
    新建微应用快照版本记录
    """
    conn = get_connection()
    try:
        with conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COALESCE(MAX(version_num), 0) + 1 AS next_ver FROM app_versions WHERE app_slug = ?",
                (app_slug,)
            )
            next_ver = cursor.fetchone()["next_ver"]
            cursor.execute(
                """
                INSERT INTO app_versions (app_slug, version_num, entry_type, description, storage_path)
                VALUES (?, ?, ?, ?, ?)
                """,
                (app_slug, next_ver, entry_type, description, storage_path)
            )
            version_id = cursor.lastrowid
            cursor.execute("SELECT * FROM app_versions WHERE id = ?", (version_id,))
            row = cursor.fetchone()
            logger.info(f"成功保存应用快照版本: slug={app_slug}, v={next_ver}, id={version_id}")
            return row_to_version(row)
    finally:
        conn.close()

def list_app_versions(app_slug: str) -> List[AppVersionModel]:
    """
    获取指定应用的所有历史版本（按版本号倒序）
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM app_versions WHERE app_slug = ? ORDER BY version_num DESC",
            (app_slug,)
        )
        rows = cursor.fetchall()
        return [row_to_version(r) for r in rows]
    finally:
        conn.close()

def get_app_version_by_id(version_id: int) -> Optional[AppVersionModel]:
    """
    根据主键 ID 获取指定版本实体
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM app_versions WHERE id = ?", (version_id,))
        row = cursor.fetchone()
        return row_to_version(row) if row else None
    finally:
        conn.close()
