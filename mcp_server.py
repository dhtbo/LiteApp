#!/usr/bin/env python3
"""
LiteApp 本地 MCP (Model Context Protocol) 快捷启动入口
用于 Claude Desktop / Cursor / Antigravity 等 MCP 客户端直接运行:
  python mcp_server.py
"""

import sys
from pathlib import Path

# 确保项目根路径进入 sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.mcp_server import mcp

if __name__ == "__main__":
    mcp.run()
