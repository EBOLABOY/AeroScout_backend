"""
权限控制系统
"""
from enum import Enum
from typing import List, Optional, Callable
from functools import wraps
from fastapi import Depends, HTTPException, status
from loguru import logger

from fastapi_app.models.auth import UserInfo
from fastapi_app.dependencies.auth import get_current_active_user


class Permission(Enum):
    """权限枚举"""
    # 用户管理权限
    USER_READ = "user:read"
    USER_WRITE = "user:write"
    USER_DELETE = "user:delete"
    
    # 旅行规划权限
    TRAVEL_PLAN_CREATE = "travel:plan:create"
    TRAVEL_PLAN_READ = "travel:plan:read"
    TRAVEL_PLAN_UNLIMITED = "travel:plan:unlimited"  # 无限制使用
    
    # 航班搜索权限
    FLIGHT_SEARCH = "flight:search"
    FLIGHT_MONITOR = "flight:monitor"
    
    # 系统管理权限
    SYSTEM_ADMIN = "system:admin"
    SYSTEM_CONFIG = "system:config"
    SYSTEM_LOGS = "system:logs"
    
    # 数据管理权限
    DATA_EXPORT = "data:export"
    DATA_IMPORT = "data:import"
    DATA_BACKUP = "data:backup"


class Role(Enum):
    """角色枚举"""
    GUEST = "guest"          # 游客（未登录）
    USER = "user"            # 普通用户
    VIP = "vip"              # VIP用户
    ADMIN = "admin"          # 管理员
    SUPER_ADMIN = "super_admin"  # 超级管理员


# 角色权限映射
ROLE_PERMISSIONS = {
    Role.GUEST: [
        # 游客只能查看基本信息
    ],
    Role.USER: [
        Permission.TRAVEL_PLAN_CREATE,
        Permission.TRAVEL_PLAN_READ,
        Permission.FLIGHT_SEARCH,
    ],
    Role.VIP: [
        Permission.TRAVEL_PLAN_CREATE,
        Permission.TRAVEL_PLAN_READ,
        Permission.TRAVEL_PLAN_UNLIMITED,
        Permission.FLIGHT_SEARCH,
        Permission.FLIGHT_MONITOR,
        Permission.DATA_EXPORT,
    ],
    Role.ADMIN: [
        Permission.USER_READ,
        Permission.USER_WRITE,
        Permission.TRAVEL_PLAN_CREATE,
        Permission.TRAVEL_PLAN_READ,
        Permission.TRAVEL_PLAN_UNLIMITED,
        Permission.FLIGHT_SEARCH,
        Permission.FLIGHT_MONITOR,
        Permission.SYSTEM_CONFIG,
        Permission.SYSTEM_LOGS,
        Permission.DATA_EXPORT,
        Permission.DATA_IMPORT,
    ],
    Role.SUPER_ADMIN: [
        # 超级管理员拥有所有权限
        Permission.USER_READ,
        Permission.USER_WRITE,
        Permission.USER_DELETE,
        Permission.TRAVEL_PLAN_CREATE,
        Permission.TRAVEL_PLAN_READ,
        Permission.TRAVEL_PLAN_UNLIMITED,
        Permission.FLIGHT_SEARCH,
        Permission.FLIGHT_MONITOR,
        Permission.SYSTEM_ADMIN,
        Permission.SYSTEM_CONFIG,
        Permission.SYSTEM_LOGS,
        Permission.DATA_EXPORT,
        Permission.DATA_IMPORT,
        Permission.DATA_BACKUP,
    ]
}


class PermissionChecker:
    """权限检查器"""
    
    @staticmethod
    def get_user_role(user: Optional[UserInfo]) -> Role:
        """获取用户角色"""
        if not user:
            return Role.GUEST

        if user.is_admin:
            # 将所有管理员视为超级管理员，拥有完整的系统管理权限
            return Role.SUPER_ADMIN

        # 这里可以根据用户的其他属性判断是否为VIP
        # 目前简单地将所有普通用户视为USER
        return Role.USER
    
    @staticmethod
    def get_user_permissions(user: Optional[UserInfo]) -> List[Permission]:
        """获取用户权限列表"""
        role = PermissionChecker.get_user_role(user)
        return ROLE_PERMISSIONS.get(role, [])
    
    @staticmethod
    def has_permission(user: Optional[UserInfo], permission: Permission) -> bool:
        """检查用户是否拥有指定权限"""
        user_permissions = PermissionChecker.get_user_permissions(user)
        return permission in user_permissions
    
    @staticmethod
    def has_any_permission(user: Optional[UserInfo], permissions: List[Permission]) -> bool:
        """检查用户是否拥有任意一个指定权限"""
        user_permissions = PermissionChecker.get_user_permissions(user)
        return any(perm in user_permissions for perm in permissions)
    
    @staticmethod
    def has_all_permissions(user: Optional[UserInfo], permissions: List[Permission]) -> bool:
        """检查用户是否拥有所有指定权限"""
        user_permissions = PermissionChecker.get_user_permissions(user)
        return all(perm in user_permissions for perm in permissions)


def require_permission(permission: Permission) -> Callable:
    """
    依赖注入函数生成器，用于要求特定权限
    """
    async def _require_permission(current_user: UserInfo = Depends(get_current_active_user)) -> UserInfo:
        if not PermissionChecker.has_permission(current_user, permission):
            logger.warning(f"用户 {current_user.username} 缺少权限: {permission.value}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"缺少权限: {permission.value}"
            )
        return current_user
    return _require_permission


# ==================== 具体权限依赖 ====================

# 使用依赖注入函数生成器创建具体的权限依赖
require_user_read_permission = require_permission(Permission.USER_READ)
require_user_write_permission = require_permission(Permission.USER_WRITE)
require_travel_plan_permission = require_permission(Permission.TRAVEL_PLAN_CREATE)
require_system_admin_permission = require_permission(Permission.SYSTEM_ADMIN)


# 权限信息获取函数
async def get_user_permissions_info(current_user: UserInfo = Depends(get_current_active_user)) -> dict:
    """获取用户权限信息"""
    role = PermissionChecker.get_user_role(current_user)
    permissions = PermissionChecker.get_user_permissions(current_user)
    
    return {
        "user_id": current_user.id,
        "username": current_user.username,
        "role": role.value,
        "permissions": [perm.value for perm in permissions],
        "is_admin": current_user.is_admin
    }
