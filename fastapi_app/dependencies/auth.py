"""
认证相关的依赖注入
"""
import os
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from datetime import datetime, timedelta
from loguru import logger

from fastapi_app.config import settings
from fastapi_app.models.auth import UserInfo
from fastapi_app.services.supabase_service import get_supabase_service
from fastapi_app.utils.password import get_password_hash, verify_password

# JWT安全方案
security = HTTPBearer()
optional_security = HTTPBearer(auto_error=False)  # 可选认证，不自动抛出错误

# JWT配置
SECRET_KEY = settings.JWT_SECRET_KEY
ALGORITHM = settings.JWT_ALGORITHM
ACCESS_TOKEN_EXPIRE_MINUTES = settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> UserInfo:
    """获取当前用户（异步版本）"""
    token = credentials.credentials

    try:
        # 解码JWT token
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get('user_id')

        if user_id is None:
            logger.warning("JWT token中缺少user_id")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="无效的认证令牌",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # 查询用户
        db_service = await get_supabase_service()
        user_data = await db_service.get_user_by_id(user_id)
        
        if user_data is None:
            logger.warning(f"用户不存在: user_id={user_id}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户不存在",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # 构建用户信息对象
        user_info = UserInfo(
            id=user_data['id'],
            username=user_data['username'],
            email=user_data['email'],
            is_admin=user_data.get('is_admin', False),
            created_at=user_data['created_at']
        )

        logger.debug(f"用户认证成功: {user_info.username}")
        return user_info

    except jwt.ExpiredSignatureError:
        logger.warning("JWT token已过期")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="认证令牌已过期",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError as e:
        logger.warning(f"JWT token无效: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的认证令牌",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_active_user(current_user: UserInfo = Depends(get_current_user)) -> UserInfo:
    """获取当前活跃用户（异步版本）"""
    # 这里可以添加用户状态检查逻辑
    # 例如：检查用户是否被禁用、是否需要重新验证等
    return current_user




async def optional_auth(credentials: Optional[HTTPAuthorizationCredentials] = Depends(optional_security)) -> Optional[UserInfo]:
    """可选认证 - 允许匿名访问（异步版本）"""
    if credentials is None:
        return None

    try:
        return await get_current_user(credentials)
    except HTTPException:
        return None


# 为了保持一致性，创建一个别名
get_current_user_optional = optional_auth


def create_access_token(user_id: int, expires_delta: Optional[timedelta] = None) -> str:
    """创建访问令牌"""
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode = {
        "user_id": user_id,
        "exp": expire,
        "iat": datetime.utcnow(),
        "type": "access"
    }

    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    logger.debug(f"创建访问令牌成功: user_id={user_id}, expires={expire}")
    return encoded_jwt




# 安全配置类
class SecurityConfig:
    """安全配置"""
    SECRET_KEY = SECRET_KEY
    ALGORITHM = ALGORITHM
    ACCESS_TOKEN_EXPIRE_MINUTES = ACCESS_TOKEN_EXPIRE_MINUTES

    # 密码策略
    MIN_PASSWORD_LENGTH = 6
    MAX_PASSWORD_LENGTH = 128

    # 用户名策略
    MIN_USERNAME_LENGTH = 3
    MAX_USERNAME_LENGTH = 50

    @classmethod
    def validate_password(cls, password: str) -> bool:
        """验证密码强度"""
        if len(password) < cls.MIN_PASSWORD_LENGTH:
            return False
        if len(password) > cls.MAX_PASSWORD_LENGTH:
            return False
        return True

    @classmethod
    def validate_username(cls, username: str) -> bool:
        """验证用户名格式"""
        if len(username) < cls.MIN_USERNAME_LENGTH:
            return False
        if len(username) > cls.MAX_USERNAME_LENGTH:
            return False
        # 可以添加更多验证规则，如字符限制等
        return True
