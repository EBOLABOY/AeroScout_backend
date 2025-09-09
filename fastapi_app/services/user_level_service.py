#!/usr/bin/env python3
"""
用户等级管理服务
"""

from typing import Any

from loguru import logger

from fastapi_app.services.supabase_service import get_supabase_service


class UserLevelService:
    """用户等级管理服务"""

    def __init__(self):
        """初始化用户等级服务"""
        pass

    async def get_all_user_levels(self) -> list[dict[str, Any]]:
        """获取所有用户等级"""
        try:
            db_service = await get_supabase_service()
            result = (
                db_service.client.table("user_levels").select("*").eq("is_active", True).order("sort_order").execute()
            )

            if result.data:
                logger.debug(f"获取到 {len(result.data)} 个用户等级")
                return result.data
            return []
        except Exception as e:
            logger.error(f"获取用户等级失败: {e}")
            return []

    async def get_user_level_by_id(self, level_id: int) -> dict[str, Any] | None:
        """根据ID获取用户等级"""
        try:
            db_service = await get_supabase_service()
            result = db_service.client.table("user_levels").select("*").eq("id", level_id).execute()

            if result.data:
                return result.data[0]
            return None
        except Exception as e:
            logger.error(f"根据ID获取用户等级失败: {e}")
            return None

    async def get_user_level_by_name(self, level_name: str) -> dict[str, Any] | None:
        """根据名称获取用户等级"""
        try:
            db_service = await get_supabase_service()
            result = (
                db_service.client.table("user_levels")
                .select("*")
                .eq("name", level_name)
                .eq("is_active", True)
                .execute()
            )

            if result.data:
                return result.data[0]
            return None
        except Exception as e:
            logger.error(f"根据名称获取用户等级失败: {e}")
            return None

    async def update_user_level(self, user_id: str, level_name: str) -> bool:
        """更新用户等级"""
        try:
            # 首先验证等级是否存在
            level_info = await self.get_user_level_by_name(level_name)
            if not level_info:
                logger.error(f"用户等级不存在: {level_name}")
                return False

            db_service = await get_supabase_service()

            # 先验证用户是否存在
            user_result = db_service.client.table("profiles").select("id").eq("id", user_id).execute()
            if not user_result.data:
                logger.error(f"用户 {user_id} 不存在")
                return False

            # 更新用户等级
            from datetime import datetime

            update_data = {
                "user_level_id": level_info["id"],
                "user_level_name": level_name,
                "updated_at": datetime.now().isoformat(),
            }

            result = db_service.client.table("profiles").update(update_data).eq("id", user_id).execute()

            if result.data and len(result.data) > 0:
                logger.info(f"用户 {user_id} 等级成功更新为 {level_name}")
                return True
            else:
                logger.warning(f"用户 {user_id} 等级更新失败：数据库更新返回空结果")
                return False

        except Exception as e:
            logger.error(f"更新用户等级失败: {e}")
            return False

    async def get_user_level_permissions(self, level_name: str) -> list[str]:
        """获取用户等级对应的权限列表"""
        from fastapi_app.dependencies.permissions import ROLE_PERMISSIONS, Role

        try:
            role = Role(level_name)
            permissions = ROLE_PERMISSIONS.get(role, [])
            return [perm.value for perm in permissions]
        except ValueError:
            logger.warning(f"未知的用户等级: {level_name}")
            return []

    async def get_user_level_benefits(self, level_name: str) -> dict[str, Any]:
        """获取用户等级对应的权益说明"""
        level_info = await self.get_user_level_by_name(level_name)
        if not level_info:
            return {}

        permissions = await self.get_user_level_permissions(level_name)

        # 权益映射
        benefits = {
            "guest": {
                "search_quota": 10,  # 每日搜索次数
                "ai_search": False,
                "price_monitoring": False,
                "export_data": False,
                "priority_support": False,
            },
            "user": {
                "search_quota": 50,
                "ai_search": False,
                "price_monitoring": False,
                "export_data": False,
                "priority_support": False,
            },
            "plus": {
                "search_quota": 200,
                "ai_search": True,
                "price_monitoring": True,
                "export_data": True,
                "priority_support": False,
            },
            "pro": {
                "search_quota": 500,
                "ai_search": True,
                "price_monitoring": True,
                "export_data": True,
                "priority_support": False,
            },
            "max": {
                "search_quota": -1,  # 无限制
                "ai_search": True,
                "price_monitoring": True,
                "export_data": True,
                "priority_support": False,
            },
            "vip": {
                "search_quota": -1,  # 无限制
                "ai_search": True,
                "price_monitoring": True,
                "export_data": True,
                "priority_support": True,
            },
        }

        return {"level": level_info, "permissions": permissions, "benefits": benefits.get(level_name, benefits["user"])}

    async def can_upgrade_user(self, current_level: str, target_level: str) -> bool:
        """检查是否可以升级到目标等级"""
        current_info = await self.get_user_level_by_name(current_level)
        target_info = await self.get_user_level_by_name(target_level)

        if not current_info or not target_info:
            return False

        # 只能升级到更高等级
        return target_info["sort_order"] > current_info["sort_order"]


# 全局服务实例
_user_level_service = None


async def get_user_level_service() -> UserLevelService:
    """获取用户等级服务实例"""
    global _user_level_service
    if _user_level_service is None:
        _user_level_service = UserLevelService()
    return _user_level_service
