import os
from pathlib import Path
from fastapi import APIRouter, Depends
from app.api.deps import verify_admin_token
from app.core.config import settings
from app.schema.system_schema import SystemConfigResponse, SystemConfigUpdateRequest

router = APIRouter(prefix="/api/system", tags=["系统配置"])

def _update_env_file(key: str, value: str) -> None:
    """
    同步更新本地 .env 文件中的配置项，保持容器重启后依然生效
    """
    try:
        env_path = Path(".env")
        if not env_path.exists():
            return
        content = env_path.read_text(encoding="utf-8")
        lines = content.splitlines()
        found = False
        new_lines = []
        for line in lines:
            if line.startswith(f"{key}="):
                new_lines.append(f"{key}={value}")
                found = True
            else:
                new_lines.append(line)
        if not found:
            new_lines.append(f"{key}={value}")
        env_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    except Exception:
        pass

@router.get("/config", response_model=SystemConfigResponse, summary="获取系统全局集成配置")
async def get_system_config() -> SystemConfigResponse:
    """
    获取当前系统的外部集成配置（如 n8n 地址与 API Key）
    """
    return SystemConfigResponse(
        n8n_base_url=settings.N8N_BASE_URL,
        n8n_api_key=settings.N8N_API_KEY
    )

@router.post("/config", response_model=SystemConfigResponse, summary="更新系统全局集成配置 (管理员权限)")
async def update_system_config(
    req: SystemConfigUpdateRequest,
    _: bool = Depends(verify_admin_token)
) -> SystemConfigResponse:
    """
    更新系统外部集成配置，支持热更新与 .env 持久化
    """
    if req.n8n_base_url is not None:
        new_url = req.n8n_base_url.strip().rstrip("/")
        settings.N8N_BASE_URL = new_url
        _update_env_file("N8N_BASE_URL", new_url)
    if req.n8n_api_key is not None:
        new_key = req.n8n_api_key.strip()
        settings.N8N_API_KEY = new_key
        _update_env_file("N8N_API_KEY", new_key)
    return SystemConfigResponse(
        n8n_base_url=settings.N8N_BASE_URL,
        n8n_api_key=settings.N8N_API_KEY
    )
