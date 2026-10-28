from typing import Optional
from fastapi import APIRouter, Header, HTTPException, status
from app.schema.auth_schema import LoginRequest, LoginResponse, AuthStatusResponse
from app.core.security import verify_admin_password, generate_admin_token, verify_admin_token
from app.core.config import settings

router = APIRouter(prefix="/api/auth", tags=["鉴权管理"])

@router.post("/login", response_model=LoginResponse, summary="管理员登录")
async def login(req: LoginRequest) -> LoginResponse:
    """
    输入管理员密码获取鉴权 Token
    """
    if not verify_admin_password(req.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="管理员密码错误，请重试"
        )
    token = generate_admin_token(req.password)
    return LoginResponse(token=token, message="登录成功")

@router.get("/status", response_model=AuthStatusResponse, summary="查询当前管理员登录状态")
async def check_status(
    x_admin_token: Optional[str] = Header(None, alias="X-Admin-Token"),
    authorization: Optional[str] = Header(None, alias="Authorization"),
) -> AuthStatusResponse:
    """
    检查前端存储的 Token 是否仍然有效
    """
    try:
        await verify_admin_token(x_admin_token=x_admin_token, authorization=authorization)
        return AuthStatusResponse(authenticated=True)
    except HTTPException:
        return AuthStatusResponse(authenticated=False)
