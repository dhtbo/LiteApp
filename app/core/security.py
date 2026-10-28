import hmac
import hashlib
from typing import Optional
from fastapi import Header, HTTPException, status
from app.core.config import settings
from app.core.logger import logger

def generate_admin_token(password: str) -> str:
    """
    根据管理员密码生成 HMAC-SHA256 签名 Token
    
    :param password: 输入的管理员密码
    :returns: 十六进制哈希 Token
    """
    secret = settings.ADMIN_PASSWORD.encode("utf-8")
    return hmac.new(secret, password.encode("utf-8"), hashlib.sha256).hexdigest()

def verify_admin_password(password: str) -> bool:
    """
    验证输入的密码是否与设定的管理员密码匹配
    
    :param password: 用户输入的密码
    :returns: 是否匹配
    """
    return hmac.compare_digest(password, settings.ADMIN_PASSWORD)

async def verify_admin_token(
    x_admin_token: Optional[str] = Header(None, alias="X-Admin-Token"),
    authorization: Optional[str] = Header(None, alias="Authorization"),
) -> bool:
    """
    FastAPI 依赖项：验证管理员权限
    优先校验 X-Admin-Token，其次支持 Authorization: Bearer <token>
    
    :raises HTTPException: 401 状态码，当令牌无效或缺失时
    :returns: 验证通过返回 True
    """
    token = x_admin_token
    if not token and authorization:
        parts = authorization.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            token = parts[1]

    if not token:
        logger.warning("鉴权拦截：未提供管理员凭证")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="需要管理员权限，请先登录",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # NOTE: 支持直接传入明文密码或由后端生成的 HMAC 签名 Token，保障多端灵活接入
    expected_token = generate_admin_token(settings.ADMIN_PASSWORD)
    is_valid_plain = hmac.compare_digest(token, settings.ADMIN_PASSWORD)
    is_valid_hmac = hmac.compare_digest(token, expected_token)

    if not (is_valid_plain or is_valid_hmac):
        logger.warning("鉴权拦截：管理员凭证错误")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="管理员凭证无效或已过期，请重新登录",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return True
