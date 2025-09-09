#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
管理员API路由
提供系统管理、用户管理等功能
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
import uuid
import psutil
import time
from loguru import logger

from ..models.auth import UserInfo
from ..models.common import APIResponse
from ..dependencies.permissions import check_permission, Permission
from ..dependencies.auth import get_current_active_user
from ..services.supabase_auth_service import SupabaseAuthService, get_supabase_auth_service
from ..services.supabase_service import get_supabase_service
from ..services.supabase_service import SupabaseService
from ..services.subscription_service import get_subscription_service

router = APIRouter()

async def check_admin_permission(current_user: UserInfo) -> None:
    """检查管理员权限"""
    if not check_permission(current_user, Permission.SYSTEM_ADMIN):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="缺少系统管理权限"
        )

# 统一的管理员依赖：获取当前用户并校验管理员权限
async def require_admin(current_user: UserInfo = Depends(get_current_active_user)) -> UserInfo:
    await check_admin_permission(current_user)
    return current_user

# 系统启动时间
START_TIME = time.time()

@router.get("/stats", response_model=APIResponse)
async def get_system_stats(
    current_user: UserInfo = Depends(get_current_active_user),
    auth_service: SupabaseAuthService = Depends(get_supabase_auth_service)
):
    """
    获取系统统计信息
    """
    try:
        # 检查管理员权限
        await check_admin_permission(current_user)
        
        # 获取用户统计
        supabase_service = await get_supabase_service()
        
        # 使用 count 方法优化用户总数统计
        total_users_result = supabase_service.client.table('profiles').select('id', count='exact').execute()
        total_users = total_users_result.count if total_users_result.count is not None else 0
        
        # 使用 count 方法优化活跃用户数统计（最近30天登录的用户）
        thirty_days_ago = (datetime.now() - timedelta(days=30)).isoformat()
        try:
            active_users_result = supabase_service.client.table('profiles').select('id', count='exact').filter('last_login', 'gte', thirty_days_ago).execute()
            active_users = active_users_result.count if active_users_result.count is not None else 0
        except Exception:
            # 如果查询失败，使用is_active字段作为备选
            active_users_result = supabase_service.client.table('profiles').select('id', count='exact').eq('is_active', True).execute()
            active_users = active_users_result.count if active_users_result.count is not None else 0
        
        # 获取监控任务统计
        try:
            total_tasks_result = supabase_service.client.table('monitor_tasks').select('id', count='exact').execute()
            total_tasks = total_tasks_result.count if total_tasks_result.count is not None else 0

            active_tasks_result = supabase_service.client.table('monitor_tasks').select('id', count='exact').eq('is_active', True).execute()
            active_tasks = active_tasks_result.count if active_tasks_result.count is not None else 0
        except Exception as e:
            logger.warning(f"监控任务统计查询失败: {e}")
            total_tasks = 0
            active_tasks = 0

        # 获取搜索次数统计
        today = datetime.now().date().isoformat()
        try:
            # 尝试从搜索日志表获取今日搜索次数
            today_searches_result = supabase_service.client.table('search_logs').select('id', count='exact').filter('created_at', 'gte', today).execute()
            today_searches = today_searches_result.count if today_searches_result.count is not None else 0
            
            # 获取总搜索次数
            total_searches_result = supabase_service.client.table('search_logs').select('id', count='exact').execute()
            total_searches = total_searches_result.count if total_searches_result.count is not None else 0
        except Exception as e:
            logger.warning(f"搜索统计查询失败，可能搜索日志表不存在: {e}")
            today_searches = 0
            total_searches = 0

        # 获取系统资源使用情况
        memory_usage = psutil.virtual_memory().percent
        cpu_usage = psutil.cpu_percent(interval=1)

        # 计算运行时间
        uptime_seconds = time.time() - START_TIME
        uptime_days = int(uptime_seconds // 86400)
        uptime_hours = int((uptime_seconds % 86400) // 3600)
        uptime_str = f"{uptime_days} 天 {uptime_hours} 小时"

        # 系统健康状态
        system_health = "good"
        if memory_usage > 80 or cpu_usage > 80:
            system_health = "warning"
        if memory_usage > 90 or cpu_usage > 90:
            system_health = "error"

        stats = {
            "totalUsers": total_users,
            "activeUsers": active_users,
            "totalTasks": total_tasks,
            "activeTasks": active_tasks,
            "totalSearches": total_searches,
            "todaySearches": today_searches,
            "systemHealth": system_health,
            "uptime": uptime_str,
            "memoryUsage": round(memory_usage, 1),
            "cpuUsage": round(cpu_usage, 1)
        }

        return APIResponse(
            success=True,
            message="获取系统统计成功",
            data={"stats": stats}
        )

    except Exception as e:
        logger.error(f"获取系统统计失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取系统统计失败"
        )


@router.post("/users/{user_id}/subscription", response_model=APIResponse)
async def assign_user_subscription(
    user_id: str,
    body: dict,
    current_user: UserInfo = Depends(require_admin)
):
    """
    为指定用户分配/切换套餐（管理员）。
    body: {"plan_slug": "pro", "trial_days": 0, "period_days": 31, "cancel_at_period_end": false}
    """
    try:
        plan_slug = body.get("plan_slug")
        if not plan_slug:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="缺少 plan_slug")

        trial_days = int(body.get("trial_days") or 0)
        period_days = int(body.get("period_days") or 31)
        cancel_at_period_end = bool(body.get("cancel_at_period_end") or False)

        sub_service = await get_subscription_service()
        sub = await sub_service.assign_subscription(user_id, plan_slug, trial_days=trial_days, period_days=period_days, cancel_at_period_end=cancel_at_period_end)
        if not sub:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="分配订阅失败或套餐不存在")

        return APIResponse(success=True, message="分配订阅成功", data={"subscription": sub})
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"分配订阅失败: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="分配订阅失败")


@router.post("/users/{user_id}/subscription/cancel", response_model=APIResponse)
async def cancel_user_subscription(
    user_id: str,
    body: dict = None,
    current_user: UserInfo = Depends(require_admin)
):
    """
    取消用户订阅（管理员）。body: {"immediate": false}
    """
    try:
        immediate = bool((body or {}).get("immediate") or False)
        sub_service = await get_subscription_service()
        ok = await sub_service.cancel_subscription(user_id, immediate=immediate)
        if not ok:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="取消订阅失败")
        return APIResponse(success=True, message="操作成功", data={"immediate": immediate})
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"取消订阅失败: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="取消订阅失败")




@router.post("/users/{user_id}/{action}", response_model=APIResponse)
async def user_action(
    user_id: str,
    action: str,
    current_user: UserInfo = Depends(get_current_active_user),
    auth_service: SupabaseAuthService = Depends(get_supabase_auth_service)
):
    """
    用户操作（封禁、解封、删除等）
    """
    try:
        if user_id == current_user.id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="不能对自己执行此操作")

        success = False
        if action == "block":
            success = await auth_service.block_user(user_id)
        elif action == "unblock":
            success = await auth_service.unblock_user(user_id)
        elif action == "delete":
            success = await auth_service.delete_user(user_id)
        else:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="不支持的操作")

        if success:
            return APIResponse(success=True, message=f"用户{action}操作成功", data={"user_id": user_id, "action": action})
        else:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在或操作失败")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"用户操作失败: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="用户操作失败")
@router.get("/users", response_model=APIResponse)
async def get_users_list(
    page: int = Query(1, ge=1, description="页码"),
    limit: int = Query(20, ge=1, le=100, description="每页数量"),
    current_user: UserInfo = Depends(get_current_active_user),
    auth_service: SupabaseAuthService = Depends(get_supabase_auth_service)
):
    """
    获取用户列表（管理员功能）
    """
    try:
        # 检查管理员权限
        await check_admin_permission(current_user)
        
        supabase_service = await get_supabase_service()
        
        # 计算偏移量
        offset = (page - 1) * limit
        
        # 获取用户总数
        total_result = supabase_service.client.table('profiles').select('id', count='exact').execute()
        total = total_result.count if total_result.count is not None else 0
        
        # 获取用户列表
        users_result = supabase_service.client.table('profiles').select(
            'id, username, email, full_name, is_admin, user_level_name, is_active, created_at, last_login'
        ).range(offset, offset + limit - 1).order('created_at', desc=True).execute()
        
        users = users_result.data if users_result.data else []
        
        return APIResponse(
            success=True,
            message="获取用户列表成功",
            data={
                "users": users,
                "total": total,
                "page": page,
                "limit": limit,
                "pages": (total + limit - 1) // limit
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取用户列表失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取用户列表失败"
        )


@router.get("/users/stats", response_model=APIResponse)
async def get_user_stats(
    current_user: UserInfo = Depends(get_current_active_user),
    auth_service: SupabaseAuthService = Depends(get_supabase_auth_service)
):
    """
    获取用户统计信息（管理员功能）
    """
    try:
        stats = await auth_service.get_user_stats()
        return APIResponse(
            success=True,
            message="获取用户统计成功",
            data=stats
        )
    except Exception as e:
        logger.error(f"获取用户统计失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取用户统计失败"
        )


@router.get("/monitor-settings", response_model=APIResponse)
async def get_monitor_settings(
    current_user: UserInfo = Depends(get_current_active_user)
):
    """
    获取监控设置
    """
    try:
        # 返回前端期望的监控设置格式
        settings = {
            "monitor_interval": 7,
            "user_monitor_interval": 7,
            "price_threshold": 1000,
            "notification_cooldown": 24,
            "departure_date": "2025-09-30",
            "return_date": "2025-10-08",
            "check_interval_options": [5, 10, 15, 30, 60],
            "price_threshold_options": [500, 800, 1000, 1500, 2000, 3000]
        }

        return APIResponse(
            success=True,
            message="获取监控设置成功",
            data=settings
        )

    except Exception as e:
        logger.error(f"获取监控设置失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取监控设置失败"
        )


@router.put("/monitor-settings", response_model=APIResponse)
async def update_monitor_settings(
    settings: Dict[str, Any],
    current_user: UserInfo = Depends(get_current_active_user)
):
    """
    更新监控设置
    """
    try:
        logger.info(f"管理员 {current_user.username} 更新监控设置: {settings}")

        return APIResponse(
            success=True,
            message="监控设置更新成功",
            data={"settings": settings}
        )

    except Exception as e:
        logger.error(f"更新监控设置失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="更新监控设置失败"
        )


@router.get("/monitor-status", response_model=APIResponse)
async def get_monitor_status(
    current_user: UserInfo = Depends(get_current_active_user)
):
    """
    获取监控系统状态
    """
    try:
        from datetime import datetime, timedelta

        # 获取数据库服务
        supabase_service = await get_supabase_service()

        # 获取用户统计
        total_users_result = supabase_service.client.table('profiles').select('id', count='exact').execute()
        total_users = total_users_result.count if total_users_result.count is not None else 0

        # 获取管理员用户数量
        admin_users_result = supabase_service.client.table('profiles').select('id', count='exact').eq('is_admin', True).execute()
        admin_users = admin_users_result.count if admin_users_result.count is not None else 0

        # 获取活跃用户（最近30天有登录记录的用户）
        thirty_days_ago = (datetime.now() - timedelta(days=30)).isoformat()
        active_users_result = supabase_service.client.table('profiles').select('id', count='exact').gte('last_login', thirty_days_ago).execute()
        active_users = active_users_result.count if active_users_result.count is not None else 0

        # 获取监控任务统计
        total_tasks_result = supabase_service.client.table('monitor_tasks').select('id', count='exact').execute()
        total_tasks = total_tasks_result.count if total_tasks_result.count is not None else 0

        # 获取活跃任务（is_active=true）
        active_tasks_result = supabase_service.client.table('monitor_tasks').select('id', count='exact').eq('is_active', True).execute()
        active_tasks = active_tasks_result.count if active_tasks_result.count is not None else 0

        # 获取24小时内有检查记录的任务
        twenty_four_hours_ago = (datetime.now() - timedelta(hours=24)).isoformat()
        recent_active_tasks_result = supabase_service.client.table('monitor_tasks').select('id', count='exact').gte('last_check', twenty_four_hours_ago).execute()
        recent_active_tasks = recent_active_tasks_result.count if recent_active_tasks_result.count is not None else 0

        # 构建状态数据
        status_data = {
            "system_status": "running",
            "users": {
                "total": total_users,
                "active": active_users,
                "admin": admin_users
            },
            "tasks": {
                "total": total_tasks,
                "active": active_tasks,
                "recent_active": recent_active_tasks
            },
            "last_update": datetime.now().isoformat()
        }

        return APIResponse(
            success=True,
            message="获取监控状态成功",
            data=status_data
        )

    except Exception as e:
        logger.error(f"获取监控状态失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取监控状态失败"
        )


@router.post("/users/batch-action", response_model=APIResponse)
async def batch_user_action(
    action_data: Dict[str, Any],
    current_user: UserInfo = Depends(get_current_active_user),
    auth_service: SupabaseAuthService = Depends(get_supabase_auth_service)
):
    """
    批量用户操作
    """
    try:
        user_ids = action_data.get('user_ids', [])
        action = action_data.get('action')

        if not user_ids or not action:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="用户ID列表和操作类型不能为空")
        if current_user.id in user_ids:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="不能对自己执行批量操作")

        results = []
        for user_id in user_ids:
            success = False
            if action == "block":
                success = await auth_service.block_user(user_id)
            elif action == "unblock":
                success = await auth_service.unblock_user(user_id)
            elif action == "delete":
                success = await auth_service.delete_user(user_id)
            results.append({"user_id": user_id, "success": success})

        success_count = len([r for r in results if r["success"]])
        return APIResponse(
            success=True,
            message=f"批量操作完成，成功: {success_count}/{len(user_ids)}",
            data={"results": results, "action": action}
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"批量用户操作失败: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="批量用户操作失败")


@router.get("/users/search", response_model=APIResponse)
async def search_users(
    q: str = Query(..., description="搜索关键词"),
    limit: int = Query(10, ge=1, le=50),
    current_user: UserInfo = Depends(get_current_active_user),
    auth_service: SupabaseAuthService = Depends(get_supabase_auth_service)
):
    """
    搜索用户
    """
    try:
        users = await auth_service.search_users(q, limit)
        return APIResponse(success=True, message=f"找到 {len(users)} 个用户", data={"users": users, "query": q})
    except Exception as e:
        logger.error(f"搜索用户失败: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="搜索用户失败")
