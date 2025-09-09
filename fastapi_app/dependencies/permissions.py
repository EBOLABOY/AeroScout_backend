"""
权限控制系统
"""

from collections.abc import Callable
from enum import Enum

from fastapi import HTTPException, status
from loguru import logger

from fastapi_app.models.auth import UserInfo


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
    FLIGHT_SEARCH_ENHANCED = "flight:search:enhanced"  # 增强搜索
    FLIGHT_MONITOR = "flight:monitor"
    FLIGHT_AI_UNLIMITED = "flight:ai:unlimited"  # 无限AI搜索

    # 数据管理权限
    DATA_EXPORT = "data:export"
    DATA_IMPORT = "data:import"
    DATA_BACKUP = "data:backup"

    # VIP特权
    PRIORITY_SUPPORT = "priority:support"
    ADVANCED_ANALYTICS = "advanced:analytics"

    # 系统管理权限
    SYSTEM_ADMIN = "system:admin"
    SYSTEM_CONFIG = "system:config"
    SYSTEM_LOGS = "system:logs"


class Role(Enum):
    """角色枚举 - 基于数据库中的用户等级"""

    GUEST = "guest"  # 游客（未登录用户）
    USER = "user"  # 普通用户（注册用户）
    PLUS = "plus"  # PLUS会员（中度订阅用户）
    PRO = "pro"  # PRO会员（高度订阅用户）
    MAX = "max"  # MAX会员（最高订阅用户）
    VIP = "vip"  # 铂金旅客（高活跃用户）
    ADMIN = "admin"  # 系统管理员（超级权限）


# 角色权限映射
ROLE_PERMISSIONS = {
    Role.GUEST: [
        # 游客仅可基础搜索
        Permission.FLIGHT_SEARCH,
    ],
    Role.USER: [
        # 普通用户基础功能
        Permission.FLIGHT_SEARCH,
        Permission.TRAVEL_PLAN_CREATE,
        Permission.TRAVEL_PLAN_READ,
    ],
    Role.PLUS: [
        # PLUS会员增强功能
        Permission.FLIGHT_SEARCH,
        Permission.FLIGHT_SEARCH_ENHANCED,
        Permission.FLIGHT_MONITOR,
        Permission.TRAVEL_PLAN_CREATE,
        Permission.TRAVEL_PLAN_READ,
        Permission.DATA_EXPORT,
    ],
    Role.PRO: [
        # PRO会员专业功能
        Permission.FLIGHT_SEARCH,
        Permission.FLIGHT_SEARCH_ENHANCED,
        Permission.FLIGHT_MONITOR,
        Permission.TRAVEL_PLAN_CREATE,
        Permission.TRAVEL_PLAN_READ,
        Permission.TRAVEL_PLAN_UNLIMITED,
        Permission.DATA_EXPORT,
        Permission.ADVANCED_ANALYTICS,
    ],
    Role.MAX: [
        # MAX会员顶级功能
        Permission.FLIGHT_SEARCH,
        Permission.FLIGHT_SEARCH_ENHANCED,
        Permission.FLIGHT_MONITOR,
        Permission.FLIGHT_AI_UNLIMITED,
        Permission.TRAVEL_PLAN_UNLIMITED,
        Permission.DATA_EXPORT,
        Permission.DATA_IMPORT,
        Permission.ADVANCED_ANALYTICS,
    ],
    Role.VIP: [
        # VIP铂金旅客特权
        Permission.FLIGHT_SEARCH,
        Permission.FLIGHT_SEARCH_ENHANCED,
        Permission.FLIGHT_MONITOR,
        Permission.FLIGHT_AI_UNLIMITED,
        Permission.TRAVEL_PLAN_UNLIMITED,
        Permission.DATA_EXPORT,
        Permission.PRIORITY_SUPPORT,
        Permission.ADVANCED_ANALYTICS,
    ],
    Role.ADMIN: [
        # 管理员拥有所有权限
        Permission.USER_READ,
        Permission.USER_WRITE,
        Permission.USER_DELETE,
        Permission.FLIGHT_SEARCH,
        Permission.FLIGHT_SEARCH_ENHANCED,
        Permission.FLIGHT_MONITOR,
        Permission.FLIGHT_AI_UNLIMITED,
        Permission.TRAVEL_PLAN_CREATE,
        Permission.TRAVEL_PLAN_READ,
        Permission.TRAVEL_PLAN_UNLIMITED,
        Permission.DATA_EXPORT,
        Permission.DATA_IMPORT,
        Permission.DATA_BACKUP,
        Permission.PRIORITY_SUPPORT,
        Permission.ADVANCED_ANALYTICS,
        Permission.SYSTEM_ADMIN,
        Permission.SYSTEM_CONFIG,
        Permission.SYSTEM_LOGS,
    ],
}


class PermissionChecker:
    """权限检查器"""

    @staticmethod
    def get_user_role(user: UserInfo | None) -> Role:
        """获取用户角色 - 基于数据库中的用户等级"""
        if not user:
            return Role.GUEST

        # 管理员用户直接返回ADMIN角色
        if user.is_admin:
            return Role.ADMIN

        # 基于数据库中的user_level_name确定角色
        level_name = user.user_level_name or "user"
        try:
            return Role(level_name)
        except ValueError:
            # 如果等级名称无效，默认为普通用户
            logger.warning(f"未知的用户等级名称: {level_name}，默认为user")
            return Role.USER

    @staticmethod
    def get_user_permissions(user: UserInfo | None) -> list[Permission]:
        """获取用户权限列表"""
        role = PermissionChecker.get_user_role(user)
        return ROLE_PERMISSIONS.get(role, [])

    @staticmethod
    def has_permission(user: UserInfo | None, permission: Permission) -> bool:
        """检查用户是否拥有指定权限"""
        user_permissions = PermissionChecker.get_user_permissions(user)
        return permission in user_permissions

    @staticmethod
    def has_any_permission(user: UserInfo | None, permissions: list[Permission]) -> bool:
        """检查用户是否拥有任意一个指定权限"""
        user_permissions = PermissionChecker.get_user_permissions(user)
        return any(perm in user_permissions for perm in permissions)

    @staticmethod
    def has_all_permissions(user: UserInfo | None, permissions: list[Permission]) -> bool:
        """检查用户是否拥有所有指定权限"""
        user_permissions = PermissionChecker.get_user_permissions(user)
        return all(perm in user_permissions for perm in permissions)


def require_permission(permission: Permission) -> Callable:
    """
    依赖注入函数生成器，用于要求特定权限
    """

    async def _require_permission(current_user: UserInfo = None) -> UserInfo:
        # 延迟导入避免循环依赖
        if current_user is None:
            # 这里需要手动获取当前用户，但这样会破坏依赖注入
            # 更好的方法是在路由层面处理权限检查
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="需要认证")

        if not PermissionChecker.has_permission(current_user, permission):
            logger.warning(f"用户 {current_user.username if current_user else '匿名'} 缺少权限: {permission.value}")
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"缺少权限: {permission.value}")
        return current_user

    return _require_permission


# ==================== 具体权限依赖 ====================

# 使用依赖注入函数生成器创建具体的权限依赖
require_user_read_permission = require_permission(Permission.USER_READ)
require_user_write_permission = require_permission(Permission.USER_WRITE)
require_travel_plan_permission = require_permission(Permission.TRAVEL_PLAN_CREATE)
require_system_admin_permission = require_permission(Permission.SYSTEM_ADMIN)


# 权限信息获取函数
async def get_user_permissions_info(current_user: UserInfo) -> dict:
    """获取用户权限信息"""
    role = PermissionChecker.get_user_role(current_user)
    permissions = PermissionChecker.get_user_permissions(current_user)

    return {
        "user_id": current_user.id,
        "username": current_user.username,
        "role": role.value,
        "permissions": [perm.value for perm in permissions],
        "is_admin": current_user.is_admin,
    }


# 权限检查辅助函数
def check_permission(user: UserInfo, permission: Permission) -> bool:
    """检查用户是否有指定权限"""
    return PermissionChecker.has_permission(user, permission)
