"""
订阅相关路由：查看套餐、查看自己的订阅与配额/用量
"""

from fastapi import APIRouter, Depends, HTTPException, status
from loguru import logger

from fastapi_app.dependencies.auth import get_current_active_user
from fastapi_app.models.auth import UserInfo
from fastapi_app.models.common import APIResponse
from fastapi_app.services.subscription_service import get_subscription_service

router = APIRouter()


@router.get("/plans", response_model=APIResponse)
async def list_plans():
    try:
        service = await get_subscription_service()
        plans = await service.list_plans(only_active=True)
        return APIResponse(success=True, message="获取套餐成功", data={"plans": plans})
    except Exception as e:
        logger.error(f"获取套餐失败: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="获取套餐失败")


@router.get("/me", response_model=APIResponse)
async def get_my_subscription(current_user: UserInfo = Depends(get_current_active_user)):
    try:
        service = await get_subscription_service()
        sub = await service.get_active_subscription(current_user.id)
        quotas = await service.get_user_quotas(current_user.id)

        # Example usage snapshot (extend as needed)
        usage = {}
        used_flight_daily = await service.get_usage(current_user.id, metric="flight_searches", window="daily")
        usage["flight_searches_daily"] = {
            "metric": "flight_searches",
            "window": "daily",
            "period_start": "today",
            "count": used_flight_daily,
        }

        overview = {
            "plan": sub.get("plan") if sub else None,
            "subscription": sub,
            "quotas": quotas,
            "usage": usage,
        }
        return APIResponse(success=True, message="获取订阅信息成功", data=overview)
    except Exception as e:
        logger.error(f"获取订阅信息失败: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="获取订阅信息失败")
