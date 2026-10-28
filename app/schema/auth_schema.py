from pydantic import BaseModel, Field

class LoginRequest(BaseModel):
    """
    管理员登录请求体
    """
    password: str = Field(..., description="管理员密码", min_length=1)

class LoginResponse(BaseModel):
    """
    管理员登录成功响应体
    """
    token: str = Field(..., description="管理员鉴权 Token")
    message: str = Field("登录成功", description="状态提示")

class AuthStatusResponse(BaseModel):
    """
    管理员鉴权状态查询响应
    """
    authenticated: bool = Field(..., description="当前 Token 是否拥有有效管理员权限")
