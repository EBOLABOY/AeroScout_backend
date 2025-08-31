"""
Supabase认证依赖 - 纯Supabase认证方案
遵循KISS原则，移除传统JWT认证
"""
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from loguru import logger

from fastapi_app.models.auth import UserInfo
from fastapi_app.services.supabase_service import get_supabase_service
from fastapi_app.services.supabase_auth_service import get_supabase_auth_service

# Supabase安全方案
security = HTTPBearer(auto_error=False)
optional_security = HTTPBearer(auto_error=False)


async def get_current_user(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> UserInfo:
    """获取当前用户（纯Supabase认证）"""
    if credentials is None:
        logger.error("认证失败: 没有提供认证凭据")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="需要认证",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token = credentials.credentials
    logger.info(f"收到认证请求，Token长度: {len(token) if token else 0}")
    
    try:
        # 使用Supabase Auth服务验证token
        auth_service = get_supabase_auth_service()
        result = await auth_service.get_user_by_access_token(token)
        
        if not result["success"]:
            logger.error(f"Token验证失败: {result.get('error', 'Unknown error')}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="无效的认证令牌",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        supabase_user = result["user"]
        logger.info(f"用户认证成功: {supabase_user.email}")
        
        # 同步用户数据到业务表
        db_service = await get_supabase_service()
        synced_user = await db_service.sync_user_from_supabase_auth(supabase_user)
        
        if not synced_user:
            logger.warning(f"用户数据同步失败: {supabase_user.id}")
            # 即使同步失败，也允许使用基本用户信息
        
        # 从Supabase用户数据构建UserInfo
        user_info = UserInfo(
            id=supabase_user.id,
            username=supabase_user.user_metadata.get("username") or supabase_user.email.split("@")[0],
            email=supabase_user.email,
            is_admin=supabase_user.app_metadata.get("is_admin", False),
            user_level_id=supabase_user.user_metadata.get("user_level_id"),
            user_level_name=supabase_user.user_metadata.get("user_level_name", "user"),
            created_at=supabase_user.created_at
        )
        
        logger.debug(f"用户认证成功: {user_info.username}")
        return user_info
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"认证验证异常: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="认证处理失败",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_active_user(current_user: UserInfo = Depends(get_current_user)) -> UserInfo:
    """获取当前活跃用户"""
    return current_user


async def optional_auth(credentials: Optional[HTTPAuthorizationCredentials] = Depends(optional_security)) -> Optional[UserInfo]:
    """可选认证 - 允许匿名访问"""
    if credentials is None:
        return None

    try:
        return await get_current_user(credentials)
    except HTTPException:
        return None


# 为了保持一致性，创建一个别名
get_current_user_optional = optional_auth


# 安全配置类 - 保留用于密码验证
class SecurityConfig:
    """安全配置"""
    # 密码策略（用于Supabase注册验证）
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
        return True