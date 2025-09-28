"""
认证依赖：使用 Authlib + JWKS/HS256 本地校验 Supabase JWT
"""

from datetime import datetime
import json

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from loguru import logger

from fastapi_app.config import settings
from fastapi_app.models.auth import UserInfo
from fastapi_app.services.supabase_service import get_supabase_service
from fastapi_app.security.jwt import verify_jwt_and_get_claims

security = HTTPBearer()
optional_security = HTTPBearer(auto_error=False)


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> UserInfo:
    token = credentials.credentials
    # 基本校验，避免非字符串/空/占位符导致的解码异常
    if not isinstance(token, str):
        logger.warning(f"无效的Authorization类型: {type(token)}")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效的认证令牌")
    token = token.strip()
    if not token or token.lower() in {"null", "undefined", "none"}:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效的认证令牌")
    # 兼容某些前端误传JSON对象字符串的情况：{"access_token":"..."}
    if token.startswith("{") and token.endswith("}"):
        try:
            obj = json.loads(token)
            possible = obj.get("access_token") or obj.get("token")
            if isinstance(possible, str) and possible:
                token = possible
        except Exception:
            pass
    claims = await verify_jwt_and_get_claims(token)
    if not claims:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效的认证令牌")
    user_id = claims.get("sub") or claims.get("user_id")
    email = claims.get("email")
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
    credentials: HTTPAuthorizationCredentials | None = Depends(optional_security),
) -> UserInfo | None:
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
