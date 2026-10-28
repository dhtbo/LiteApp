import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.logger import logger
from app.repository.database import init_db
from app.api import auth, apps, llm, sites, generator, forms, system

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    FastAPI 生命周期管理：启动时初始化 SQLite 数据库及必要目录
    """
    logger.info("=== LiteApp Studio 正在启动 ===")
    logger.info(f"数据根目录: {settings.data_path}")
    logger.info(f"站点存放目录: {settings.sites_path}")
    
    # 初始化数据库建表及初始种子
    init_db()
    
    yield
    logger.info("=== LiteApp Studio 已安全停机 ===")

app = FastAPI(
    title="LiteApp Studio",
    description="AI 静态微应用开发与发布平台",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

# 允许跨域
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册 API 路由
app.include_router(auth.router)
app.include_router(apps.router)
app.include_router(llm.router)
app.include_router(sites.router)
app.include_router(generator.router)
app.include_router(forms.router)
app.include_router(system.router)

# 容器健康检查端点 (Docker HEALTHCHECK / Coolify 探针)
@app.get("/api/health", tags=["系统监控"])
async def health_check() -> dict:
    """
    容器健康检查端点，返回当前平台运行状态与配置
    """
    return {
        "status": "healthy",
        "service": "LiteApp Studio",
        "database": "connected",
        "sites_dir_exists": settings.sites_path.exists(),
    }

# 静态 UI 与主页分发
STATIC_UI_DIR = Path(__file__).resolve().parent / "static_ui"

@app.get("/favicon.ico", include_in_schema=False)
@app.get("/favicon.svg", include_in_schema=False)
async def serve_favicon() -> FileResponse:
    """
    分发平台 Favicon 矢量图标
    """
    icon_file = STATIC_UI_DIR / "favicon.svg"
    if icon_file.exists():
        return FileResponse(str(icon_file), media_type="image/svg+xml")
    return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"error": "Not found"})

@app.get("/", include_in_schema=False)
@app.get("/index.html", include_in_schema=False)
@app.get("/portal", include_in_schema=False)
@app.get("/ai", include_in_schema=False)
@app.get("/studio", include_in_schema=False)
@app.get("/workbench", include_in_schema=False)
@app.get("/upload", include_in_schema=False)
@app.get("/settings", include_in_schema=False)
async def serve_index() -> FileResponse:
    """
    分发主管理门户 SPA 页面，兼容各种前端工作台与子页面路由
    """
    index_file = STATIC_UI_DIR / "index.html"
    if not index_file.exists():
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": "前端静态文件 index.html 缺失"}
        )
    return FileResponse(
        str(index_file),
        media_type="text/html; charset=utf-8",
        headers={"Cache-Control": "no-cache"}
    )

# 挂载静态资源目录
if STATIC_UI_DIR.exists():
    app.mount("/static_ui", StaticFiles(directory=str(STATIC_UI_DIR)), name="static_ui")

# 全局异常兜底处理
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    统一捕获未处理的运行时异常
    """
    logger.error(f"全局未捕获异常: url={request.url}, error={str(exc)}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "服务器内部处理异常，请检查后台日志"}
    )
