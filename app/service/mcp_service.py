import os
import re
import random
from typing import Optional, Dict, Any, List
from fastapi import HTTPException
import httpx

from app.core.config import settings
from app.core.logger import logger
from app.schema.app_schema import AppCreateRequest, AppUpdateRequest
from app.service import app_service
from app.service.generator_service import sanitize_slug

def _get_base_url() -> str:
    """
    获取微应用访问的基础公网/局域网地址
    优先读取环境变量 LITEAPP_BASE_URL，否则基于当前 HOST 和 PORT 生成
    """
    env_base = os.getenv("LITEAPP_BASE_URL", "").strip().rstrip("/")
    if env_base:
        return env_base
    host = settings.HOST if settings.HOST not in ["0.0.0.0", "::"] else "localhost"
    return f"http://{host}:{settings.PORT}"

def publish_static_app(
    title: str,
    html_content: str,
    slug: Optional[str] = None,
    description: Optional[str] = None,
    category: Optional[str] = "实用工具",
    icon: Optional[str] = "🚀",
    overwrite: bool = True,
) -> Dict[str, Any]:
    """
    一键发布或更新静态微应用单页（HTML/CSS/JS）
    
    :param title: 应用名称（例如：'极简番茄钟'）
    :param html_content: 完整的单文件 HTML 源码字符串
    :param slug: 自定义应用 URL 路由标识，若不指定将自动基于标题生成
    :param description: 应用功能简述
    :param category: 应用所属分类，默认 '实用工具'
    :param icon: 应用图标 Emoji，默认 '🚀'
    :param overwrite: 若应用已存在是否覆盖更新并归档历史版本，默认为 True
    :returns: 包含发布状态、访问链接与应用详情的字典
    """
    if not title or not title.strip():
        raise ValueError("应用标题 (title) 不能为空")
    if not html_content or not html_content.strip():
        raise ValueError("HTML 源码内容 (html_content) 不能为空")

    # 规范化 Slug
    actual_slug = slug.strip().lower() if slug else sanitize_slug(title)
    # 限制 slug 字符规范
    actual_slug = re.sub(r"[^a-zA-Z0-9_-]", "-", actual_slug).strip("-_")
    if not actual_slug:
        actual_slug = f"app-{random.randint(1000, 9999)}"

    # 检查是否配置了远程 API 模式 (当 MCP 客户端运行在外部机器，目标为远程 LiteApp 实例)
    remote_url = os.getenv("LITEAPP_REMOTE_URL", "").strip().rstrip("/")
    remote_token = os.getenv("LITEAPP_ADMIN_TOKEN", "").strip() or settings.ADMIN_PASSWORD
    if remote_url:
        return _publish_to_remote_liteapp(
            remote_url=remote_url,
            remote_token=remote_token,
            title=title,
            html_content=html_content,
            slug=actual_slug,
            description=description or "",
            category=category or "实用工具",
            icon=icon or "🚀",
            overwrite=overwrite,
        )

    # 本地嵌入式直连处理
    base_url = _get_base_url()
    from app.repository import app_repo
    existing = app_repo.get_app_by_slug(actual_slug)

    action = "created"
    if existing:
        if not overwrite:
            raise ValueError(f"微应用标识 '{actual_slug}' 已存在，若需覆盖更新请设置 overwrite=True")
        # 覆盖更新现有微应用的 index.html 并自动创建历史快照
        app_service.overwrite_app_html(
            slug=actual_slug,
            html_content=html_content,
            description="通过本地 MCP 工具自动发布更新"
        )
        # 同步更新元数据
        app_service.update_app(
            slug=actual_slug,
            req=AppUpdateRequest(
                title=title,
                description=description or existing.description,
                category=category or existing.category,
                icon=icon or existing.icon,
            )
        )
        action = "updated"
        logger.info(f"[MCP] 成功更新微应用: {actual_slug} ({title})")
    else:
        # 新建微应用
        app_service.create_app_with_html(
            AppCreateRequest(
                slug=actual_slug,
                title=title,
                description=description or f"{title} 微应用",
                category=category or "实用工具",
                icon=icon or "🚀",
                html_content=html_content,
            )
        )
        action = "created"
        logger.info(f"[MCP] 成功创建并发布微应用: {actual_slug} ({title})")

    url_path = f"/s/{actual_slug}/"
    full_url = f"{base_url}{url_path}"

    return {
        "status": "success",
        "action": action,
        "slug": actual_slug,
        "title": title,
        "url": full_url,
        "url_path": url_path,
        "category": category or "实用工具",
        "icon": icon or "🚀",
        "message": f"微应用 '{title}' 已成功发布！在线访问地址: {full_url}",
    }

def get_static_app(slug: str) -> Dict[str, Any]:
    """
    根据 Slug 获取微应用的元数据与完整的入口 HTML 源码
    
    :param slug: 微应用标识符
    :returns: 微应用详情与源码
    """
    source = app_service.get_app_source(slug)
    base_url = _get_base_url()
    return {
        "slug": source.slug,
        "title": source.title,
        "description": source.description,
        "category": source.category,
        "icon": source.icon,
        "entry_type": source.entry_type,
        "url": f"{base_url}/s/{source.slug}/",
        "html_content": source.html_content,
    }

def list_static_apps(category: Optional[str] = None, search: Optional[str] = None) -> Dict[str, Any]:
    """
    获取当前已发布的微应用列表
    
    :param category: 按分类筛选（可选）
    :param search: 按应用标题或描述搜索（可选）
    :returns: 微应用列表及统计
    """
    res = app_service.list_all_apps(category=category, search=search)
    base_url = _get_base_url()
    app_list = []
    for item in res.items:
        app_list.append({
            "slug": item.slug,
            "title": item.title,
            "description": item.description,
            "category": item.category,
            "icon": item.icon,
            "view_count": item.view_count,
            "url": f"{base_url}{item.url_path}",
            "updated_at": item.updated_at,
        })
    return {
        "total": res.total,
        "categories": res.categories,
        "apps": app_list,
    }

def delete_static_app(slug: str) -> Dict[str, Any]:
    """
    删除指定的静态微应用及其关联资源
    
    :param slug: 微应用标识符
    :returns: 删除结果
    """
    app_service.delete_app(slug)
    return {
        "status": "success",
        "slug": slug,
        "message": f"微应用 '{slug}' 已成功删除",
    }

def _publish_to_remote_liteapp(
    remote_url: str,
    remote_token: str,
    title: str,
    html_content: str,
    slug: str,
    description: str,
    category: str,
    icon: str,
    overwrite: bool,
) -> Dict[str, Any]:
    """
    调用远程 LiteApp REST API 执行静态页发布
    """
    headers = {
        "X-Admin-Token": remote_token,
        "Content-Type": "application/json",
    }
    with httpx.Client(timeout=30.0) as client:
        # 1. 检查是否存在
        check_res = client.get(f"{remote_url}/api/apps/{slug}")
        if check_res.status_code == 200:
            if not overwrite:
                raise ValueError(f"远程微应用 '{slug}' 已存在，若需覆盖请设置 overwrite=True")
            # 覆盖更新
            ov_res = client.post(
                f"{remote_url}/api/apps/{slug}/overwrite",
                headers=headers,
                json={"html_code": html_content, "description": "通过 MCP 远程发布覆盖"},
            )
            if ov_res.status_code != 200:
                raise RuntimeError(f"覆盖远程应用失败: {ov_res.text}")
            # 更新元信息
            client.put(
                f"{remote_url}/api/apps/{slug}",
                headers=headers,
                json={"title": title, "description": description, "category": category, "icon": icon},
            )
            action = "updated"
        else:
            # 创建新应用
            create_res = client.post(
                f"{remote_url}/api/apps",
                headers=headers,
                json={
                    "slug": slug,
                    "title": title,
                    "description": description,
                    "category": category,
                    "icon": icon,
                    "html_content": html_content,
                },
            )
            if create_res.status_code != 200:
                raise RuntimeError(f"创建远程应用失败: {create_res.text}")
            action = "created"

    full_url = f"{remote_url}/s/{slug}/"
    return {
        "status": "success",
        "action": action,
        "slug": slug,
        "title": title,
        "url": full_url,
        "url_path": f"/s/{slug}/",
        "category": category,
        "icon": icon,
        "message": f"微应用 '{title}' 已成功发布至远程平台！在线访问地址: {full_url}",
    }
