#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
使用统计和配额统计服务
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, date, timedelta
from loguru import logger

from fastapi_app.services.supabase_service import get_supabase_service
from fastapi_app.services.cache_service import get_cache_service
from fastapi_app.dependencies.permissions import Role


class UsageStatsService:
    """使用统计服务"""
    
    def __init__(self):
        pass

    async def record_usage(self, user_id: str, action_type: str, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """记录用户使用行为"""
        try:
            db_service = await get_supabase_service()
            
            usage_record = {
                "user_id": user_id,
                "action_type": action_type,
                "metadata": metadata or {},
                "timestamp": datetime.now().isoformat(),
                "date": date.today().isoformat()
            }
            
            # 尝试插入到usage_logs表（如果不存在则跳过）
            try:
                result = db_service.client.table("usage_logs").insert(usage_record).execute()
                logger.debug(f"记录用户使用统计成功: {user_id} - {action_type}")
                return bool(result.data)
            except Exception as e:
                # 如果表不存在，可以考虑只记录到缓存
                logger.warning(f"usage_logs表不存在，跳过数据库记录: {e}")
                return True
                
        except Exception as e:
            logger.error(f"记录用户使用统计失败: {e}")
            return False

    async def get_user_daily_stats(self, user_id: str, target_date: date = None) -> Dict[str, Any]:
        """获取用户某日使用统计"""
        if target_date is None:
            target_date = date.today()
        
        try:
            cache_service = await get_cache_service()
            
            # 从缓存获取配额使用情况
            stats = {}
            quota_types = ["search", "ai_search", "monitor", "export"]
            
            for quota_type in quota_types:
                cache_key = f"quota:{user_id}:{quota_type}:{target_date.isoformat()}"
                usage = await cache_service.get(cache_key) or 0
                stats[quota_type] = int(usage)
            
            return {
                "user_id": user_id,
                "date": target_date.isoformat(),
                "quotas": stats,
                "total_requests": sum(stats.values())
            }
            
        except Exception as e:
            logger.error(f"获取用户日统计失败: {e}")
            return {"user_id": user_id, "date": target_date.isoformat(), "quotas": {}, "total_requests": 0}

    async def get_user_weekly_stats(self, user_id: str) -> Dict[str, Any]:
        """获取用户近7天统计"""
        try:
            weekly_stats = []
            total_usage = {"search": 0, "ai_search": 0, "monitor": 0, "export": 0}
            
            for i in range(7):
                target_date = date.today() - timedelta(days=i)
                day_stats = await self.get_user_daily_stats(user_id, target_date)
                weekly_stats.append(day_stats)
                
                # 累加总使用量
                for quota_type, usage in day_stats["quotas"].items():
                    if quota_type in total_usage:
                        total_usage[quota_type] += usage
            
            return {
                "user_id": user_id,
                "period": "7_days",
                "daily_stats": weekly_stats,
                "total_usage": total_usage,
                "peak_day": max(weekly_stats, key=lambda x: x["total_requests"]) if weekly_stats else None
            }
            
        except Exception as e:
            logger.error(f"获取用户周统计失败: {e}")
            return {"user_id": user_id, "period": "7_days", "daily_stats": [], "total_usage": {}}

    async def get_user_monthly_stats(self, user_id: str, year: int = None, month: int = None) -> Dict[str, Any]:
        """获取用户月度统计"""
        if year is None:
            year = datetime.now().year
        if month is None:
            month = datetime.now().month
        
        try:
            # 获取该月的所有日期
            start_date = date(year, month, 1)
            if month == 12:
                end_date = date(year + 1, 1, 1) - timedelta(days=1)
            else:
                end_date = date(year, month + 1, 1) - timedelta(days=1)
            
            monthly_stats = []
            total_usage = {"search": 0, "ai_search": 0, "monitor": 0, "export": 0}
            
            current_date = start_date
            while current_date <= end_date:
                day_stats = await self.get_user_daily_stats(user_id, current_date)
                monthly_stats.append(day_stats)
                
                # 累加总使用量
                for quota_type, usage in day_stats["quotas"].items():
                    if quota_type in total_usage:
                        total_usage[quota_type] += usage
                
                current_date += timedelta(days=1)
            
            return {
                "user_id": user_id,
                "period": f"{year}-{month:02d}",
                "daily_stats": monthly_stats,
                "total_usage": total_usage,
                "average_daily": {k: v / len(monthly_stats) if monthly_stats else 0 for k, v in total_usage.items()},
                "peak_day": max(monthly_stats, key=lambda x: x["total_requests"]) if monthly_stats else None
            }
            
        except Exception as e:
            logger.error(f"获取用户月统计失败: {e}")
            return {"user_id": user_id, "period": f"{year}-{month}", "daily_stats": [], "total_usage": {}}

    async def get_system_stats_summary(self) -> Dict[str, Any]:
        """获取系统整体统计摘要"""
        try:
            db_service = await get_supabase_service()
            
            # 获取用户总数和等级分布
            users_result = db_service.client.table("profiles").select("user_level_name").execute()
            
            level_distribution = {}
            total_users = len(users_result.data) if users_result.data else 0
            
            for user in users_result.data or []:
                level = user.get('user_level_name', 'user')
                level_distribution[level] = level_distribution.get(level, 0) + 1
            
            # 获取等级信息
            levels_result = db_service.client.table("user_levels").select("*").execute()
            levels_info = {level['name']: level for level in levels_result.data or []}
            
            return {
                "total_users": total_users,
                "level_distribution": level_distribution,
                "levels_info": levels_info,
                "active_users_today": 0,  # 可以从缓存或日志中获取
                "total_searches_today": 0,  # 可以从缓存中获取
                "generated_at": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"获取系统统计摘要失败: {e}")
            return {"total_users": 0, "level_distribution": {}, "error": str(e)}

    async def cleanup_old_cache(self, days_to_keep: int = 7) -> bool:
        """清理过期缓存数据"""
        try:
            cache_service = await get_cache_service()
            
            # 计算过期日期
            cutoff_date = date.today() - timedelta(days=days_to_keep)
            
            # 这里可以实现具体的清理逻辑
            # Redis通常会自动处理TTL过期，但可以手动清理特定模式的key
            logger.info(f"清理{cutoff_date}之前的缓存数据")
            return True
            
        except Exception as e:
            logger.error(f"清理旧缓存失败: {e}")
            return False


# 全局统计服务实例
_usage_stats_service = None

async def get_usage_stats_service() -> UsageStatsService:
    """获取使用统计服务实例"""
    global _usage_stats_service
    if _usage_stats_service is None:
        _usage_stats_service = UsageStatsService()
    return _usage_stats_service