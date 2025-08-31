#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
独立配额服务模块
避免循环导入问题
"""

from typing import Dict, Any, Optional
from datetime import datetime, date
from loguru import logger

from fastapi_app.dependencies.permissions import Role


class QuotaType:
    """配额类型常量"""
    SEARCH = "search"
    AI_SEARCH = "ai_search"
    MONITOR = "monitor"
    EXPORT = "export"


class UserQuotaService:
    """用户配额管理服务（独立版本）"""
    
    def __init__(self):
        self.quota_limits = {
            Role.GUEST: {QuotaType.SEARCH: 10, QuotaType.AI_SEARCH: 0},
            Role.USER: {QuotaType.SEARCH: 50, QuotaType.AI_SEARCH: 0},
            Role.PLUS: {QuotaType.SEARCH: 200, QuotaType.AI_SEARCH: 50, QuotaType.MONITOR: 10, QuotaType.EXPORT: 20},
            Role.PRO: {QuotaType.SEARCH: 500, QuotaType.AI_SEARCH: 200, QuotaType.MONITOR: 50, QuotaType.EXPORT: 100},
            Role.MAX: {QuotaType.SEARCH: -1, QuotaType.AI_SEARCH: -1, QuotaType.MONITOR: -1, QuotaType.EXPORT: -1},  # 无限制
            Role.VIP: {QuotaType.SEARCH: -1, QuotaType.AI_SEARCH: -1, QuotaType.MONITOR: -1, QuotaType.EXPORT: -1},  # 无限制
        }

    async def get_user_quota_status(self, user, quota_type: str) -> Dict[str, Any]:
        """获取用户配额状态"""
        try:
            # 动态导入避免循环依赖
            from fastapi_app.dependencies.permissions import PermissionChecker
            from fastapi_app.services.cache_service import get_cache_service
            
            # 管理员拥有无限制配额
            if user and user.is_admin:
                return {
                    "quota_type": quota_type,
                    "daily_limit": -1,
                    "used_today": 0,
                    "remaining": -1,
                    "is_unlimited": True,
                    "reset_time": "00:00:00"
                }
            
            # 处理None用户（游客）
            if user is None:
                return {
                    "quota_type": quota_type,
                    "daily_limit": 10,  # 游客固定配额
                    "used_today": 0,
                    "remaining": 10,
                    "is_unlimited": False,
                    "reset_time": "00:00:00"
                }
            
            user_role = PermissionChecker.get_user_role(user)
            daily_limit = self.quota_limits.get(user_role, {}).get(quota_type, 0)
            
            if daily_limit == -1:  # 无限制
                return {
                    "quota_type": quota_type,
                    "daily_limit": -1,
                    "used_today": 0,
                    "remaining": -1,
                    "is_unlimited": True,
                    "reset_time": "00:00:00"
                }
            
            # 从缓存获取今日使用量
            cache_key = f"quota:{user.id}:{quota_type}:{date.today().isoformat()}"
            cache_service = await get_cache_service()
            used_today = await cache_service.get(cache_key) or 0
            used_today = int(used_today) if used_today else 0
            
            remaining = max(0, daily_limit - used_today)
            
            return {
                "quota_type": quota_type,
                "daily_limit": daily_limit,
                "used_today": used_today,
                "remaining": remaining,
                "is_unlimited": False,
                "reset_time": "00:00:00"
            }
            
        except Exception as e:
            logger.error(f"获取用户配额状态失败: {e}")
            return {
                "quota_type": quota_type,
                "daily_limit": 0,
                "used_today": 0,
                "remaining": 0,
                "is_unlimited": False,
                "reset_time": "00:00:00",
                "error": str(e)
            }

    async def consume_quota(self, user, quota_type: str, amount: int = 1) -> bool:
        """消费配额"""
        try:
            # 管理员拥有无限制配额
            if user and user.is_admin:
                return True
            
            from fastapi_app.dependencies.permissions import PermissionChecker
            from fastapi_app.services.cache_service import get_cache_service
            
            user_role = PermissionChecker.get_user_role(user)
            daily_limit = self.quota_limits.get(user_role, {}).get(quota_type, 0)
            
            if daily_limit == -1:  # 无限制
                return True
            
            # 检查剩余配额
            quota_status = await self.get_user_quota_status(user, quota_type)
            if quota_status["remaining"] < amount:
                return False
            
            # 更新使用量
            cache_key = f"quota:{user.id}:{quota_type}:{date.today().isoformat()}"
            cache_service = await get_cache_service()
            new_usage = quota_status["used_today"] + amount
            
            # 缓存24小时（使用expire参数）
            await cache_service.set(cache_key, new_usage, expire=86400)
            
            logger.info(f"用户 {user.username} 消费配额: {quota_type} +{amount}, 剩余: {quota_status['remaining'] - amount}")
            return True
            
        except Exception as e:
            logger.error(f"消费配额失败: {e}")
            return False

    async def check_quota(self, user, quota_type: str, required_amount: int = 1) -> bool:
        """检查配额是否充足"""
        # 管理员拥有无限制配额
        if user and user.is_admin:
            return True
            
        quota_status = await self.get_user_quota_status(user, quota_type)
        if quota_status.get("is_unlimited"):
            return True
        return quota_status.get("remaining", 0) >= required_amount


# 全局配额服务实例
_quota_service = None

async def get_quota_service() -> UserQuotaService:
    """获取配额服务实例"""
    global _quota_service
    if _quota_service is None:
        _quota_service = UserQuotaService()
    return _quota_service