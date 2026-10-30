"""
LiteApp 官方 MCP (Model Context Protocol) 协议服务器
提供一键发布静态微应用、查询应用列表、获取微应用源码与删除微应用等核心工具
支持作为本地 stdio 进程启动，亦支持作为 SSE 端点挂载于 Web 框架
"""

import sys
import json
from typing import Optional, Dict, Any
from mcp.server.fastmcp import FastMCP

from app.service import mcp_service

# 初始化 FastMCP 实例
mcp = FastMCP(
    name="LiteApp",
    instructions="LiteApp 静态微应用托管与发布平台 MCP 服务。提供一键发布独立单页静态微应用 (HTML/CSS/JS)、查询应用列表、获取源码进行二次迭代等能力。",
)

@mcp.tool(
    name="publish_static_app",
    description="一键将 HTML/CSS/JS 静态代码发布为独立的在线微应用。支持新建应用或覆盖更新已有应用，发布后自动生成可直接在浏览器中访问的 URL。",
)
def publish_static_app(
    title: str,
    html_content: str,
    slug: Optional[str] = None,
    description: Optional[str] = None,
    category: Optional[str] = "实用工具",
    icon: Optional[str] = "🚀",
    overwrite: bool = True,
) -> str:
    """
    一键发布静态微应用
    
    :param title: 应用名称（例如：'极简番茄钟'、'团队周报看板'）
    :param html_content: 完整的单文件 HTML 源码字符串（包含样式与交互逻辑）
    :param slug: 自定义微应用 URL 路由标识（仅允许英文、数字、中划线），不传时自动基于标题生成
    :param description: 微应用功能简要描述
    :param category: 微应用分类（如：'实用工具'、'AI应用'、'效率办公'、'数据分析' 等）
    :param icon: 图标 Emoji（例如：'⏱️'、'📊'、'🚀'）
    :param overwrite: 若应用已存在是否覆盖更新（默认 True，覆盖时自动创建历史版本快照）
    :returns: JSON 字符串，包含发布结果、状态及在线访问 URL
    """
    try:
        result = mcp_service.publish_static_app(
            title=title,
            html_content=html_content,
            slug=slug,
            description=description,
            category=category,
            icon=icon,
            overwrite=overwrite,
        )
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        error_res = {
            "status": "error",
            "message": f"发布静态应用失败: {str(e)}"
        }
        return json.dumps(error_res, ensure_ascii=False, indent=2)

@mcp.tool(
    name="list_static_apps",
    description="获取 LiteApp 平台上所有已发布的静态微应用列表，支持按分类筛选或关键字搜索。",
)
def list_static_apps(
    category: Optional[str] = None,
    search: Optional[str] = None,
) -> str:
    """
    查询微应用广场列表
    
    :param category: 按照分类筛选（可选）
    :param search: 搜索关键词（按标题或简介模糊匹配，可选）
    :returns: JSON 字符串，包含微应用总数、分类统计与应用元数据列表
    """
    try:
        result = mcp_service.list_static_apps(category=category, search=search)
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        error_res = {
            "status": "error",
            "message": f"查询应用列表失败: {str(e)}"
        }
        return json.dumps(error_res, ensure_ascii=False, indent=2)

@mcp.tool(
    name="get_static_app",
    description="根据 Slug 读取指定微应用的元数据以及完整的 index.html 源码内容，方便大模型读取现有代码进行分析与二次迭代修改。",
)
def get_static_app(slug: str) -> str:
    """
    获取微应用详情与完整源码
    
    :param slug: 微应用的唯一路由标识符
    :returns: JSON 字符串，包含微应用信息及完整的 HTML 源码
    """
    try:
        result = mcp_service.get_static_app(slug=slug)
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        error_res = {
            "status": "error",
            "message": f"获取微应用源码失败: {str(e)}"
        }
        return json.dumps(error_res, ensure_ascii=False, indent=2)

@mcp.tool(
    name="delete_static_app",
    description="删除指定的微应用及其磁盘静态资源文件和历史备份快照。",
)
def delete_static_app(slug: str) -> str:
    """
    删除微应用
    
    :param slug: 微应用的唯一路由标识符
    :returns: JSON 字符串，包含操作结果状态
    """
    try:
        result = mcp_service.delete_static_app(slug=slug)
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        error_res = {
            "status": "error",
            "message": f"删除微应用失败: {str(e)}"
        }
        return json.dumps(error_res, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    # 作为 stdio 传输服务运行
    mcp.run()
