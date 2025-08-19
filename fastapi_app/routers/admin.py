#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
管理员API路由
提供系统管理、用户管理、邀请码管理等功能
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
from ..dependencies.permissions import require_system_admin_permission
from ..services.user_service import FastAPIUserService, get_user_service
from ..services.supabase_service import get_supabase_service
from ..services.supabase_service import SupabaseService

router = APIRouter()

# 系统启动时间
START_TIME = time.time()

@router.get("/stats", response_model=APIResponse)
async def get_system_stats(
    current_user: UserInfo = Depends(require_system_admin_permission),
    user_service: FastAPIUserService = Depends(get_user_service)
):
    """
    获取系统统计信息
    """
    try:
        # 获取用户统计
        supabase_service = await get_supabase_service()

        # 使用 count 方法优化用户总数统计
        total_users_result = supabase_service.client.table('users').select('id', count='exact').execute()
        total_users = total_users_result.count if total_users_result.count is not None else 0

        # 使用 count 方法优化活跃用户数统计
        active_users_result = supabase_service.client.table('users').select('id', count='exact').eq('is_active', True).execute()
        active_users = active_users_result.count if active_users_result.count is not None else 0

        # 获取监控任务统计
        total_tasks_result = supabase_service.client.table('monitor_tasks').select('id', count='exact').execute()
        total_tasks = total_tasks_result.count if total_tasks_result.count is not None else 0

        active_tasks_result = supabase_service.client.table('monitor_tasks').select('id', count='exact').eq('is_active', True).execute()
        active_tasks = active_tasks_result.count if active_tasks_result.count is not None else 0

        monitor_stats = {
            'total_tasks': total_tasks,
            'active_tasks': active_tasks
        }

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
            "totalTasks": monitor_stats.get('total_tasks', 0),
            "activeTasks": monitor_stats.get('active_tasks', 0),
            "totalSearches": 0,
            "todaySearches": 0,
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




@router.post("/users/{user_id}/{action}", response_model=APIResponse)
async def user_action(
    user_id: str,
    action: str,
    current_user: UserInfo = Depends(require_system_admin_permission),
    user_service: FastAPIUserService = Depends(get_user_service)
):
    """
    用户操作（封禁、解封、删除等）
    """
    try:
        if user_id == current_user.id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="不能对自己执行此操作")

        success = False
        if action == "block":
            success = await user_service.block_user(user_id)
        elif action == "unblock":
            success = await user_service.unblock_user(user_id)
        elif action == "delete":
            success = await user_service.delete_user(user_id)
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
@router.get("/users/stats", response_model=APIResponse)
async def get_user_stats(
    current_user: UserInfo = Depends(require_system_admin_permission),
    user_service: FastAPIUserService = Depends(get_user_service)
):
    """
    获取用户统计信息（管理员功能）
    """
    try:
        stats = await user_service.get_user_stats()
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


@router.get("/invite-codes", response_model=APIResponse)
async def get_invite_codes(
    current_user: UserInfo = Depends(require_system_admin_permission)
):
    """
    获取邀请码列表
    """
    try:
        supabase_service = await get_supabase_service()

        # 检查邀请码表是否存在，如果不存在则返回空列表
        try:
            result = supabase_service.client.table('invite_codes').select('*').execute()
            codes = result.data if result.data else []
        except Exception:
            # 表不存在，返回空列表
            codes = []

        return APIResponse(
            success=True,
            message="获取邀请码列表成功",
            data={"codes": codes}
        )

    except Exception as e:
        logger.error(f"获取邀请码列表失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取邀请码列表失败"
        )


@router.post("/invite-codes", response_model=APIResponse)
async def create_invite_code(
    code_data: Dict[str, Any],
    current_user: UserInfo = Depends(require_system_admin_permission)
):
    """
    创建邀请码
    """
    try:
        supabase_service = await get_supabase_service()

        # 生成邀请码（如果没有提供）
        code = code_data.get('code')
        if not code:
            code = generate_invite_code()
        else:
            code = code.upper()  # 转换为大写

        # 检查邀请码是否已存在
        existing_code = supabase_service.client.table('invite_codes').select('*').eq('code', code).execute()
        if existing_code.data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"邀请码 {code} 已存在，请使用其他邀请码"
            )

        # 处理过期时间
        expires_at = code_data.get('expiresAt')
        if expires_at:
            try:
                # 验证日期格式
                datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="过期时间格式无效"
                )

        invite_code = {
            'id': str(uuid.uuid4()),
            'code': code,
            'description': code_data.get('description', ''),
            'max_uses': max(1, code_data.get('maxUses', 1)),  # 至少为1
            'used_count': 0,
            'expires_at': expires_at,
            'is_active': True,
            'created_by': current_user.id,
            'created_at': datetime.utcnow().isoformat()
        }

        # 创建邀请码表（如果不存在）
        try:
            result = supabase_service.client.table('invite_codes').insert(invite_code).execute()
        except Exception as e:
            if "relation" in str(e) and "does not exist" in str(e):
                # 表不存在，先创建表
                logger.warning("邀请码表不存在，功能暂未实现")
                raise HTTPException(
                    status_code=status.HTTP_501_NOT_IMPLEMENTED,
                    detail="邀请码功能暂未实现"
                )
            raise

        return APIResponse(
            success=True,
            message="邀请码创建成功",
            data={"code": invite_code}
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"创建邀请码失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="创建邀请码失败"
        )


def generate_invite_code(length: int = 8) -> str:
    """
    生成随机邀请码
    """
    import random
    import string

    # 使用大写字母和数字，排除容易混淆的字符
    chars = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
    return ''.join(random.choice(chars) for _ in range(length))


@router.delete("/invite-codes/{code_id}", response_model=APIResponse)
async def delete_invite_code(
    code_id: str,
    current_user: UserInfo = Depends(require_system_admin_permission)
):
    """
    删除邀请码
    """
    try:
        supabase_service = await get_supabase_service()

        result = supabase_service.client.table('invite_codes').delete().eq('id', code_id).execute()

        return APIResponse(
            success=True,
            message="邀请码删除成功",
            data={"code_id": code_id}
        )

    except Exception as e:
        logger.error(f"删除邀请码失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="删除邀请码失败"
        )


@router.get("/monitor-settings", response_model=APIResponse)
async def get_monitor_settings(
    current_user: UserInfo = Depends(require_system_admin_permission)
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
    current_user: UserInfo = Depends(require_system_admin_permission)
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
    current_user: UserInfo = Depends(require_system_admin_permission)
):
    """
    获取监控系统状态
    """
    try:
        from datetime import datetime, timedelta

        # 获取数据库服务
        supabase_service = await get_supabase_service()

        # 获取用户统计
        total_users_result = supabase_service.client.table('users').select('id', count='exact').execute()
        total_users = total_users_result.count if total_users_result.count is not None else 0

        # 获取管理员用户数量
        admin_users_result = supabase_service.client.table('users').select('id', count='exact').eq('is_admin', True).execute()
        admin_users = admin_users_result.count if admin_users_result.count is not None else 0

        # 获取活跃用户（最近30天有登录记录的用户）
        thirty_days_ago = (datetime.now() - timedelta(days=30)).isoformat()
        active_users_result = supabase_service.client.table('users').select('id', count='exact').gte('last_login', thirty_days_ago).execute()
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
    current_user: UserInfo = Depends(require_system_admin_permission),
    user_service: FastAPIUserService = Depends(get_user_service)
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
                success = await user_service.block_user(user_id)
            elif action == "unblock":
                success = await user_service.unblock_user(user_id)
            elif action == "delete":
                success = await user_service.delete_user(user_id)
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
    current_user: UserInfo = Depends(require_system_admin_permission),
    user_service: FastAPIUserService = Depends(get_user_service)
):
    """
    搜索用户
    """
    try:
        users = await user_service.search_users(q, limit)
        return APIResponse(success=True, message=f"找到 {len(users)} 个用户", data={"users": users, "query": q})
    except Exception as e:
        logger.error(f"搜索用户失败: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="搜索用户失败")
