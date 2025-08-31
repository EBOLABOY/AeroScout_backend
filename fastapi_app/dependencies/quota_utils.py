#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简化的配额验证装饰器
避免循环导入
"""

from typing import Optional
from fastapi import Depends, HTTPException, status
from functools import wraps
from loguru import logger

from fastapi_app.models.auth import UserInfo
from fastapi_app.dependencies.auth import get_current_active_user


async def check_user_quota(user: UserInfo, quota_type: str, amount: int = 1) -> bool:
    """检查用户配额（独立函数）"""
    try:
        from fastapi_app.services.quota_service import get_quota_service
        quota_service = await get_quota_service()
        return await quota_service.check_quota(user, quota_type, amount)
    except Exception as e:
        logger.error(f"配额检查失败: {e}")
        return False


async def consume_user_quota(user: UserInfo, quota_type: str, amount: int = 1) -> bool:
    """消费用户配额（独立函数）"""
    try:
        from fastapi_app.services.quota_service import get_quota_service
        quota_service = await get_quota_service()
        return await quota_service.consume_quota(user, quota_type, amount)
    except Exception as e:
        logger.error(f"配额消费失败: {e}")
        return False


async def get_quota_status(user: UserInfo, quota_type: str) -> dict:
    """获取配额状态（独立函数）"""
    try:
        from fastapi_app.services.quota_service import get_quota_service
        quota_service = await get_quota_service()
        return await quota_service.get_user_quota_status(user, quota_type)
    except Exception as e:
        logger.error(f"获取配额状态失败: {e}")
        return {"quota_type": quota_type, "error": str(e)}


# 快捷权限检查函数
async def require_search_quota(current_user: UserInfo = Depends(get_current_active_user)) -> UserInfo:
    """需要搜索配额"""
    from fastapi_app.services.quota_service import QuotaType
    from fastapi_app.utils.errors import QuotaError
    
    has_quota = await check_user_quota(current_user, QuotaType.SEARCH)
    if not has_quota:
        quota_status = await get_quota_status(current_user, QuotaType.SEARCH)
        raise QuotaError.quota_exceeded(
            quota_type="搜索",
            used=quota_status.get('used_today', 0),
            limit=quota_status.get('daily_limit', 0)
        )
    return current_user


async def require_ai_search_quota(current_user: UserInfo = Depends(get_current_active_user)) -> UserInfo:
    """需要AI搜索配额"""
    from fastapi_app.services.quota_service import QuotaType
    from fastapi_app.utils.errors import QuotaError
    
    has_quota = await check_user_quota(current_user, QuotaType.AI_SEARCH)
    if not has_quota:
        quota_status = await get_quota_status(current_user, QuotaType.AI_SEARCH)
        raise QuotaError.quota_exceeded(
            quota_type="AI搜索",
            used=quota_status.get('used_today', 0),
            limit=quota_status.get('daily_limit', 0)
        )
    return current_user