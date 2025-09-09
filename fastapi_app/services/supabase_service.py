#!/usr/bin/env python3
"""
Supabase 数据库服务
完全基于 Supabase 的数据操作服务，不再使用 SQLAlchemy
"""

import uuid
from datetime import UTC, datetime
from typing import Any

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

    async def _get_record_by_field(self, table_name: str, field_name: str, field_value: Any) -> dict[str, Any] | None:
        """通用方法：根据单个字段获取记录"""
        try:
            result = self.client.table(table_name).select("*").eq(field_name, field_value).execute()
            if result.data:
                return result.data[0]
            return None
        except Exception as e:
            logger.error(f"从表 {table_name} 获取记录失败: {e}")
            return None

    async def _create_record(
        self, table_name: str, data: dict[str, Any], pk_field: str = "id"
    ) -> dict[str, Any] | None:
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

    async def _update_record(self, table_name: str, record_id: str, data: dict[str, Any], pk_field: str = "id") -> bool:
        """通用方法：更新记录"""
        try:
            result = self.client.table(table_name).update(data).eq(pk_field, record_id).execute()
            return bool(result.data)
        except Exception as e:
            logger.error(f"在表 {table_name} 中更新记录失败: {e}")
            return False

    # ==================== 用户管理 ====================

    async def get_user_by_id(self, user_id: str) -> dict[str, Any] | None:
        """根据ID获取用户"""
        return await self._get_record_by_field("profiles", "id", user_id)

    async def get_user_by_email(self, email: str) -> dict[str, Any] | None:
        """根据邮箱获取用户"""
        return await self._get_record_by_field("profiles", "email", email)

    async def get_user_by_username(self, username: str) -> dict[str, Any] | None:
        """根据用户名获取用户"""
        return await self._get_record_by_field("profiles", "username", username)

    async def create_user(self, user_data: dict[str, Any]) -> dict[str, Any] | None:
        """创建用户"""
        return await self._create_record("profiles", user_data)

    async def update_user(self, user_id: str, user_data: dict[str, Any]) -> bool:
        """更新用户信息"""
        return await self._update_record("profiles", user_id, user_data)

    async def sync_user_from_supabase_auth(self, supabase_user) -> dict[str, Any] | None:
        """
        从Supabase Auth用户同步到业务用户表
        确保认证用户数据与业务数据保持一致
        """
        try:
            user_id = supabase_user.id

            # 检查用户是否已存在
            existing_user = await self.get_user_by_id(user_id)

            # 构建同步数据 - 只使用数据库中实际存在的字段
            sync_data = {
                "email": supabase_user.email,
                "email_verified": supabase_user.email_confirmed_at is not None,
                "is_active": True,
                "updated_at": datetime.now(UTC).isoformat(),
            }

            # 映射 last_sign_in_at 到数据库的 last_login 字段
            if hasattr(supabase_user, 'last_sign_in_at') and supabase_user.last_sign_in_at:
                # 确保日期格式正确
                if isinstance(supabase_user.last_sign_in_at, str):
                    sync_data["last_login"] = supabase_user.last_sign_in_at
                else:
                    sync_data["last_login"] = (
                        supabase_user.last_sign_in_at.isoformat()
                        if hasattr(supabase_user.last_sign_in_at, 'isoformat')
                        else str(supabase_user.last_sign_in_at)
                    )
            else:
                # 如果没有登录时间，使用当前时间
                sync_data["last_login"] = datetime.now(UTC).isoformat()

            # 处理用户名
            if supabase_user.user_metadata and supabase_user.user_metadata.get("username"):
                sync_data["username"] = supabase_user.user_metadata["username"]
            elif not existing_user or not existing_user.get("username"):
                # 如果没有用户名，从邮箱生成一个
                sync_data["username"] = supabase_user.email.split("@")[0]

            # 从user_metadata中提取必要的业务字段（而不是直接同步整个metadata）
            if supabase_user.user_metadata:
                # 仅提取业务相关的字段，而不是存储整个metadata对象
                if 'pushplus_token' in supabase_user.user_metadata:
                    # 这里可以添加特定业务字段的处理逻辑
                    # 例如：sync_data["pushplus_token"] = supabase_user.user_metadata["pushplus_token"]
                    pass

            # 处理应用元数据（权限等）
            # 注意：对于现有用户，is_admin 字段应该保留现有值，而不是从 app_metadata 覆盖
            if supabase_user.app_metadata and supabase_user.app_metadata.get("is_admin") is True:
                # 只有当 app_metadata 中明确设置为 True 时才更新
                sync_data["is_admin"] = True

            # 优先通过email匹配用户（符合业务逻辑最佳实践）
            existing_by_email = await self.get_user_by_email(supabase_user.email)

            if existing_by_email:
                # 用户已存在，合并数据，保留现有的重要业务字段
                merged_data = dict(sync_data)  # 创建副本

                # 保留现有用户的重要业务字段（如果同步数据中没有明确设置）
                important_fields = ["is_admin", "user_level_name", "user_level_id"]
                for field in important_fields:
                    if field not in merged_data and existing_by_email.get(field) is not None:
                        merged_data[field] = existing_by_email[field]

                success = await self.update_user(existing_by_email["id"], merged_data)
                if success:
                    logger.info(f"用户数据同步成功（邮箱匹配更新）: {supabase_user.email}")
                    return await self.get_user_by_id(existing_by_email["id"])
                else:
                    logger.error(f"更新用户数据失败: {existing_by_email['id']}")
                    return existing_by_email  # 返回原有数据

            elif existing_user:
                # 通过ID找到用户但邮箱不匹配的情况，也需要保留重要业务字段
                merged_data = dict(sync_data)  # 创建副本

                # 保留现有用户的重要业务字段
                important_fields = ["is_admin", "user_level_name", "user_level_id"]
                for field in important_fields:
                    if field not in merged_data and existing_user.get(field) is not None:
                        merged_data[field] = existing_user[field]

                success = await self.update_user(user_id, merged_data)
                if success:
                    logger.info(f"用户数据同步成功（ID匹配更新）: {supabase_user.email}")
                    return await self.get_user_by_id(user_id)
                else:
                    logger.error(f"更新用户数据失败: {user_id}")
                    return existing_user

            else:
                # 全新用户，创建记录
                create_data = {
                    "id": user_id,  # 使用Supabase用户ID
                    "created_at": supabase_user.created_at,
                    **sync_data,
                }

                new_user = await self.create_user(create_data)
                if new_user:
                    logger.info(f"用户数据同步成功（新建）: {supabase_user.email}")
                    return new_user
                else:
                    logger.error(f"创建新用户失败: {user_id}")
                    return None

        except Exception as e:
            logger.error(f"同步Supabase用户失败: {e}")
            # 返回现有用户数据（如果存在）
            return await self.get_user_by_id(supabase_user.id) if hasattr(supabase_user, 'id') else None

    # 兼容新增：profiles 支持（向后兼容旧 users 表）
    async def get_profile_by_id(self, user_id: str) -> dict[str, Any] | None:
        try:
            prof = self.client.table("profiles").select("*").eq("id", user_id).limit(1).execute()
            if prof.data:
                return prof.data[0]
        except Exception as e:
            logger.warning(f"查询profiles失败，回退users: {e}")
        return await self.get_user_by_id(user_id)

    async def get_profile_by_username(self, username: str) -> dict[str, Any] | None:
        try:
            prof = self.client.table("profiles").select("*").eq("username", username).limit(1).execute()
            if prof.data:
                return prof.data[0]
        except Exception as e:
            logger.warning(f"查询profiles失败，回退users: {e}")
        return await self.get_user_by_username(username)

    # ==================== 密码重置Token管理 ====================

    async def create_password_reset_token(self, token_data: dict[str, Any]) -> dict[str, Any] | None:
        """创建密码重置token"""
        return await self._create_record("password_reset_tokens", token_data)

    async def get_password_reset_token(self, token: str) -> dict[str, Any] | None:
        """根据token获取密码重置记录"""
        try:
            result = (
                self.client.table("password_reset_tokens").select("*").eq("token", token).eq("is_used", False).execute()
            )
            if result.data:
                return result.data[0]
            return None
        except Exception as e:
            logger.error(f"获取密码重置token失败: {e}")
            return None

    async def mark_token_as_used(self, token_id: str) -> bool:
        """标记token为已使用"""
        update_data = {"is_used": True, "used_at": datetime.now().isoformat()}
        return await self._update_record("password_reset_tokens", token_id, update_data)

    async def invalidate_user_tokens(self, user_id: str) -> bool:
        """使用户的所有未使用token失效"""
        try:
            (
                self.client.table("password_reset_tokens")
                .update({"is_used": True})
                .eq("user_id", user_id)
                .eq("is_used", False)
                .execute()
            )
            return True
        except Exception as e:
            logger.error(f"使token失效失败: {e}")
            return False

    # ==================== 监控任务管理 ====================

    async def get_user_monitor_tasks(
        self, user_id: str | None = None, is_active: bool | None = None
    ) -> list[dict[str, Any]]:
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

    async def create_monitor_task(self, task_data: dict[str, Any]) -> dict[str, Any] | None:
        """创建监控任务"""
        return await self._create_record("monitor_tasks", task_data)

    async def update_monitor_task(self, task_id: str, task_data: dict[str, Any]) -> bool:
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

    async def get_monitor_task_by_id(self, task_id: str) -> dict[str, Any] | None:
        """根据ID获取监控任务"""
        return await self._get_record_by_field("monitor_tasks", "id", task_id)

    async def update_task_stats(
        self,
        task_id: str,
        last_check: datetime,
        total_checks: int,
        last_notification: datetime | None = None,
        total_notifications: int = 0,
    ) -> bool:
        """更新监控任务统计信息"""
        try:
            update_data = {
                'last_check': last_check.isoformat(),
                'total_checks': total_checks,
                'total_notifications': total_notifications,
                'updated_at': datetime.now(UTC).isoformat(),
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

    async def get_user_travel_plans(self, user_id: str, status: str | None = None) -> list[dict[str, Any]]:
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

    async def create_travel_plan(self, plan_data: dict[str, Any]) -> dict[str, Any] | None:
        """创建旅行计划"""
        return await self._create_record("travel_plans", plan_data)

    async def update_travel_plan(self, plan_id: str, plan_data: dict[str, Any]) -> bool:
        """更新旅行计划"""
        return await self._update_record("travel_plans", plan_id, plan_data)

    async def get_travel_plan_by_id(self, plan_id: str) -> dict[str, Any] | None:
        """根据ID获取旅行计划"""
        return await self._get_record_by_field("travel_plans", "id", plan_id)

    # ==================== 健康检查 ====================

    async def health_check(self) -> bool:
        """健康检查"""
        try:
            # 简单查询测试连接
            self.client.table("profiles").select("count", count="exact").limit(1).execute()
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
