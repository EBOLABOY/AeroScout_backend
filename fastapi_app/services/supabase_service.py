#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Supabase 数据库服务
完全基于 Supabase 的数据操作服务，不再使用 SQLAlchemy
"""

import uuid
from datetime import datetime, date, timezone
from typing import List, Dict, Any, Optional
from loguru import logger

from fastapi_app.config.supabase_config import get_supabase_client


class SupabaseService:
    """Supabase 数据库服务"""
    
    def __init__(self):
        """初始化 Supabase 服务"""
        # 使用 service role key 以绕过 RLS 策略
        self.client = get_supabase_client(use_service_key=True)
        logger.info("SupabaseService 初始化完成（使用 service role key）")

    # ==================== 通用辅助方法 ====================

    async def _get_record_by_field(self, table_name: str, field_name: str, field_value: Any) -> Optional[Dict[str, Any]]:
        """通用方法：根据单个字段获取记录"""
        try:
            result = self.client.table(table_name).select("*").eq(field_name, field_value).execute()
            if result.data:
                return result.data[0]
            return None
        except Exception as e:
            logger.error(f"从表 {table_name} 获取记录失败: {e}")
            return None

    async def _create_record(self, table_name: str, data: Dict[str, Any], pk_field: str = "id") -> Optional[Dict[str, Any]]:
        """通用方法：创建新记录"""
        try:
            if pk_field not in data:
                data[pk_field] = str(uuid.uuid4())
            
            result = self.client.table(table_name).insert(data).execute()
            if result.data:
                logger.info(f"在表 {table_name} 中创建记录成功")
                return result.data[0]
            return None
        except Exception as e:
            logger.error(f"在表 {table_name} 中创建记录失败: {e}")
            return None

    async def _update_record(self, table_name: str, record_id: str, data: Dict[str, Any], pk_field: str = "id") -> bool:
        """通用方法：更新记录"""
        try:
            result = self.client.table(table_name).update(data).eq(pk_field, record_id).execute()
            return bool(result.data)
        except Exception as e:
            logger.error(f"在表 {table_name} 中更新记录失败: {e}")
            return False
    
    # ==================== 用户管理 ====================
    
    async def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        """根据ID获取用户"""
        return await self._get_record_by_field("users", "id", user_id)
    
    async def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """根据邮箱获取用户"""
        return await self._get_record_by_field("users", "email", email)
    
    async def get_user_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        """根据用户名获取用户"""
        return await self._get_record_by_field("users", "username", username)
    
    async def create_user(self, user_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """创建用户"""
        return await self._create_record("users", user_data)
    
    async def update_user(self, user_id: str, user_data: Dict[str, Any]) -> bool:
        """更新用户信息"""
        return await self._update_record("users", user_id, user_data)

    # ==================== 密码重置Token管理 ====================

    async def create_password_reset_token(self, token_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """创建密码重置token"""
        return await self._create_record("password_reset_tokens", token_data)

    async def get_password_reset_token(self, token: str) -> Optional[Dict[str, Any]]:
        """根据token获取密码重置记录"""
        try:
            result = self.client.table("password_reset_tokens").select("*").eq("token", token).eq("is_used", False).execute()
            if result.data:
                return result.data[0]
            return None
        except Exception as e:
            logger.error(f"获取密码重置token失败: {e}")
            return None

    async def mark_token_as_used(self, token_id: str) -> bool:
        """标记token为已使用"""
        update_data = {
            "is_used": True,
            "used_at": datetime.now().isoformat()
        }
        return await self._update_record("password_reset_tokens", token_id, update_data)

    async def invalidate_user_tokens(self, user_id: str) -> bool:
        """使用户的所有未使用token失效"""
        try:
            result = self.client.table("password_reset_tokens").update({
                "is_used": True
            }).eq("user_id", user_id).eq("is_used", False).execute()
            return True
        except Exception as e:
            logger.error(f"使token失效失败: {e}")
            return False
    
    # ==================== 监控任务管理 ====================
    
    async def get_user_monitor_tasks(self, user_id: Optional[str] = None, is_active: Optional[bool] = None) -> List[Dict[str, Any]]:
        """获取用户的监控任务（如果user_id为None，则获取所有用户的任务）"""
        try:
            query = self.client.table("monitor_tasks").select("*")

            # 如果指定了用户ID，则过滤特定用户的任务
            if user_id is not None:
                query = query.eq("user_id", user_id)

            if is_active is not None:
                query = query.eq("is_active", is_active)

            result = query.order("created_at", desc=True).execute()
            return result.data or []
        except Exception as e:
            logger.error(f"获取监控任务失败: {e}")
            return []
    
    async def create_monitor_task(self, task_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """创建监控任务"""
        return await self._create_record("monitor_tasks", task_data)
    
    async def update_monitor_task(self, task_id: str, task_data: Dict[str, Any]) -> bool:
        """更新监控任务"""
        return await self._update_record("monitor_tasks", task_id, task_data)
    
    async def delete_monitor_task(self, task_id: str) -> bool:
        """删除监控任务"""
        try:
            result = self.client.table("monitor_tasks").delete().eq("id", task_id).execute()
            return bool(result.data)
        except Exception as e:
            logger.error(f"删除监控任务失败: {e}")
            return False

    async def get_monitor_task_by_id(self, task_id: str) -> Optional[Dict[str, Any]]:
        """根据ID获取监控任务"""
        return await self._get_record_by_field("monitor_tasks", "id", task_id)

    async def update_task_stats(
        self,
        task_id: str,
        last_check: datetime,
        total_checks: int,
        last_notification: Optional[datetime] = None,
        total_notifications: int = 0
    ) -> bool:
        """更新监控任务统计信息"""
        try:
            update_data = {
                'last_check': last_check.isoformat(),
                'total_checks': total_checks,
                'total_notifications': total_notifications,
                'updated_at': datetime.now(timezone.utc).isoformat()
            }

            if last_notification:
                update_data['last_notification'] = last_notification.isoformat()

            result = self.client.table("monitor_tasks").update(update_data).eq("id", task_id).execute()

            if result.data:
                logger.debug(f"更新任务 {task_id} 统计信息成功")
                return True
            else:
                logger.warning(f"更新任务 {task_id} 统计信息失败：未找到任务")
                return False

        except Exception as e:
            logger.error(f"更新任务统计信息失败: {e}")
            return False
    
    # ==================== 旅行计划管理 ====================
    
    async def get_user_travel_plans(self, user_id: str, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """获取用户的旅行计划"""
        try:
            query = self.client.table("travel_plans").select("*").eq("user_id", user_id)
            
            if status:
                query = query.eq("status", status)
            
            result = query.order("created_at", desc=True).execute()
            return result.data or []
        except Exception as e:
            logger.error(f"获取旅行计划失败: {e}")
            return []
    
    async def create_travel_plan(self, plan_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """创建旅行计划"""
        return await self._create_record("travel_plans", plan_data)
    
    async def update_travel_plan(self, plan_id: str, plan_data: Dict[str, Any]) -> bool:
        """更新旅行计划"""
        return await self._update_record("travel_plans", plan_id, plan_data)
    
    async def get_travel_plan_by_id(self, plan_id: str) -> Optional[Dict[str, Any]]:
        """根据ID获取旅行计划"""
        return await self._get_record_by_field("travel_plans", "id", plan_id)
    
    # ==================== 健康检查 ====================
    
    async def health_check(self) -> bool:
        """健康检查"""
        try:
            # 简单查询测试连接
            self.client.table("users").select("count", count="exact").limit(1).execute()
            return True
        except Exception as e:
            logger.error(f"健康检查失败: {e}")
            return False


# 全局服务实例
_supabase_service = None


async def get_supabase_service() -> SupabaseService:
    """获取 Supabase 服务实例"""
    global _supabase_service
    if _supabase_service is None:
        _supabase_service = SupabaseService()
    return _supabase_service
