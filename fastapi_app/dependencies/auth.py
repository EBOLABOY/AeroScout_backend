"""
认证依赖：切换为被动验证 Supabase JWT
"""

from typing import Optional
from datetime import datetime

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from loguru import logger

from fastapi_app.config import settings
from fastapi_app.models.auth import UserInfo
from fastapi_app.services.supabase_service import get_supabase_service


security = HTTPBearer()
optional_security = HTTPBearer(auto_error=False)


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> UserInfo:
    token = credentials.credentials
    supabase_jwt_secret = settings.SUPABASE_JWT_SECRET
    if not supabase_jwt_secret:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="服务器未配置JWT验证密钥",
        )

    user_id = None
    email = None
    # 优先用 Supabase JWT 解码
    try:
        payload = jwt.decode(token, supabase_jwt_secret, algorithms=["HS256"])
        user_id = payload.get("sub")
        email = payload.get("email")
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token已过期")
    except jwt.InvalidTokenError:
        # 向后兼容：尝试旧JWT
        try:
            legacy = jwt.decode(
                token,
                getattr(settings, "JWT_SECRET_KEY", None),
                algorithms=[getattr(settings, "JWT_ALGORITHM", "HS256")],
            )
            user_id = legacy.get("user_id")
        except Exception as e:
            logger.warning(f"JWT解码失败: {e}")
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效的认证令牌")

    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="令牌缺少用户标识")

    db = await get_supabase_service()
    # 从 profiles 表获取应用附属信息
    profile = await db.get_profile_by_id(user_id)
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户档案不存在")

    user_info = UserInfo(
        id=profile["id"],
        username=profile.get("username", ""),
        email=email or profile.get("email", ""),
        is_admin=profile.get("is_admin", False),
        created_at=str(profile.get("created_at", datetime.utcnow().isoformat())),
    )
    return user_info


async def get_current_active_user(current_user: UserInfo = Depends(get_current_user)) -> UserInfo:
    return current_user


async def optional_auth(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(optional_security),
) -> Optional[UserInfo]:
    """可选认证 - 允许匿名访问"""
    if credentials is None:
        return None
    try:
        return await get_current_user(credentials)  # type: ignore[arg-type]
    except HTTPException:
        return None


get_current_user_optional = optional_auth


class SecurityConfig:
    MIN_PASSWORD_LENGTH = 6
    MAX_PASSWORD_LENGTH = 128
    MIN_USERNAME_LENGTH = 3
    MAX_USERNAME_LENGTH = 50

    @classmethod
    def validate_password(cls, password: str) -> bool:
        return cls.MIN_PASSWORD_LENGTH <= len(password) <= cls.MAX_PASSWORD_LENGTH

    @classmethod
    def validate_username(cls, username: str) -> bool:
        return cls.MIN_USERNAME_LENGTH <= len(username) <= cls.MAX_USERNAME_LENGTH

