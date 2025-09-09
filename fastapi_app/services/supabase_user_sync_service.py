"""
Supabase最佳实践：优化现有用户同步服务
遵循官方推荐的触发器机制和数据完整性方案
"""

from datetime import UTC, datetime
from typing import Any

from loguru import logger

from fastapi_app.config.supabase_config import get_supabase_client


class SupabaseUserSyncService:
    """
    Supabase最佳实践的用户同步服务

    核心原则：
    1. 以邮箱为主键进行匹配（business logic first）
    2. 保持数据完整性和一致性
    3. 幂等操作，支持重复执行
    4. 详细的日志记录和错误处理
    """

    def __init__(self):
        """初始化同步服务"""
        self.client = get_supabase_client(use_service_key=True)
        logger.info("Supabase用户同步服务初始化完成（最佳实践版本）")

    async def sync_auth_user_to_business_table(
        self, supabase_user, table_name: str = "profiles"
    ) -> dict[str, Any] | None:
        """
        同步Supabase Auth用户到业务表

        遵循Supabase最佳实践：
        1. 邮箱优先匹配原则
        2. 幂等操作设计
        3. 数据完整性保证
        """
        try:
            user_id = supabase_user.id
            email = supabase_user.email

            logger.info(f"开始同步用户: {email} (Auth ID: {user_id})")

            # 1. 构建同步数据 - 只同步必要的业务字段
            sync_data = self._build_sync_data(supabase_user)

            # 2. 邮箱优先匹配策略（最佳实践）
            existing_user = await self._find_user_by_email(email, table_name)

            if existing_user:
                # 用户存在：更新现有记录
                return await self._update_existing_user(existing_user, sync_data, table_name)
            else:
                # 新用户：创建记录
                return await self._create_new_user(user_id, sync_data, table_name)

        except Exception as e:
            logger.error(f"用户同步失败 {supabase_user.email}: {e}")
            # 最佳实践：失败时尝试返回现有数据
            return await self._fallback_get_user(supabase_user.email, table_name)

    def _build_sync_data(self, supabase_user) -> dict[str, Any]:
        """构建同步数据 - 遵循数据最小化原则"""

        sync_data = {
            "email": supabase_user.email,
            "email_verified": supabase_user.email_confirmed_at is not None,
            "is_active": True,
            "updated_at": datetime.now(UTC).isoformat(),
        }

        # 处理登录时间映射
        if hasattr(supabase_user, 'last_sign_in_at') and supabase_user.last_sign_in_at:
            sync_data["last_login"] = supabase_user.last_sign_in_at
        else:
            sync_data["last_login"] = datetime.now(UTC).isoformat()

        # 处理用户名（从metadata或邮箱生成）
        if supabase_user.user_metadata and supabase_user.user_metadata.get("username"):
            sync_data["username"] = supabase_user.user_metadata["username"]
        else:
            # 从邮箱生成默认用户名
            sync_data["username"] = supabase_user.email.split("@")[0]

        # 处理管理员权限（从app_metadata）
        if supabase_user.app_metadata:
            sync_data["is_admin"] = supabase_user.app_metadata.get("is_admin", False)

        # 提取特定业务字段（而非整个metadata）
        if supabase_user.user_metadata:
            # 只提取我们需要的特定字段
            if "user_level_id" in supabase_user.user_metadata:
                sync_data["user_level_id"] = supabase_user.user_metadata["user_level_id"]
            if "user_level_name" in supabase_user.user_metadata:
                sync_data["user_level_name"] = supabase_user.user_metadata["user_level_name"]
            if "pushplus_token" in supabase_user.user_metadata:
                sync_data["pushplus_token"] = supabase_user.user_metadata["pushplus_token"]

        return sync_data

    async def _find_user_by_email(self, email: str, table_name: str) -> dict[str, Any] | None:
        """通过邮箱查找用户 - 最佳实践的查找策略"""
        try:
            result = self.client.table(table_name).select("*").eq("email", email).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            logger.error(f"查找用户失败 {email}: {e}")
            return None

    async def _update_existing_user(
        self, existing_user: dict[str, Any], sync_data: dict[str, Any], table_name: str
    ) -> dict[str, Any] | None:
        """更新现有用户 - 保持数据完整性"""
        try:
            user_id = existing_user["id"]

            # 合并数据：保留现有重要字段
            merged_data = {**sync_data}

            # 保留现有的业务字段（如果同步数据中没有）
            preserve_fields = ["user_level_id", "user_level_name", "pushplus_token", "is_admin"]
            for field in preserve_fields:
                if field not in merged_data and existing_user.get(field) is not None:
                    merged_data[field] = existing_user[field]

            result = self.client.table(table_name).update(merged_data).eq("id", user_id).execute()

            if result.data:
                logger.info(f"用户更新成功（邮箱匹配）: {sync_data['email']}")
                return result.data[0]
            else:
                logger.warning(f"用户更新无数据返回: {user_id}")
                return existing_user

        except Exception as e:
            logger.error(f"更新用户失败: {e}")
            return existing_user  # 返回原数据作为fallback

    async def _create_new_user(self, user_id: str, sync_data: dict[str, Any], table_name: str) -> dict[str, Any] | None:
        """创建新用户 - 确保数据完整性"""
        try:
            create_data = {"id": user_id, "created_at": datetime.now(UTC).isoformat(), **sync_data}

            # 设置默认值
            create_data.setdefault("user_level_id", 1)
            create_data.setdefault("user_level_name", "user")
            create_data.setdefault("notification_enabled", True)
            create_data.setdefault("email_notifications_enabled", True)

            result = self.client.table(table_name).insert(create_data).execute()

            if result.data:
                logger.info(f"用户创建成功: {sync_data['email']}")
                return result.data[0]
            else:
                logger.error("用户创建失败，无返回数据")
                return None

        except Exception as e:
            logger.error(f"创建用户失败: {e}")
            return None

    async def _fallback_get_user(self, email: str, table_name: str) -> dict[str, Any] | None:
        """故障恢复：尝试获取现有用户数据"""
        try:
            return await self._find_user_by_email(email, table_name)
        except Exception:
            logger.error(f"故障恢复失败: {email}")
            return None

    async def batch_sync_auth_users(self, auth_users: list[Any], table_name: str = "profiles") -> dict[str, int]:
        """
        批量同步用户 - 支持大量用户处理

        Returns:
            Dict containing success and failure counts
        """
        stats = {"success": 0, "failed": 0, "skipped": 0}

        logger.info(f"开始批量同步 {len(auth_users)} 个用户")

        for auth_user in auth_users:
            try:
                result = await self.sync_auth_user_to_business_table(auth_user, table_name)

                if result:
                    stats["success"] += 1
                else:
                    stats["failed"] += 1

            except Exception as e:
                logger.error(f"批量同步用户失败 {auth_user.email}: {e}")
                stats["failed"] += 1

        logger.info(f"批量同步完成: 成功={stats['success']}, 失败={stats['failed']}")
        return stats

    async def health_check(self) -> bool:
        """健康检查 - 验证服务可用性"""
        try:
            # 简单查询测试连接
            self.client.table("profiles").select("count", count="exact").limit(1).execute()
            return True
        except Exception as e:
            logger.error(f"同步服务健康检查失败: {e}")
            return False


# 全局服务实例
_sync_service = None


async def get_user_sync_service() -> SupabaseUserSyncService:
    """获取用户同步服务实例"""
    global _sync_service
    if _sync_service is None:
        _sync_service = SupabaseUserSyncService()
    return _sync_service
