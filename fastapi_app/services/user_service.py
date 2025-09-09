"""
FastAPI 用户管理服务（与 Supabase Auth 协同）
说明：密码相关能力已交由 Supabase Auth 负责，此处仅管理业务侧 profiles 数据。
"""

from datetime import datetime
from typing import Any

from loguru import logger

from fastapi_app.services.supabase_service import get_supabase_service


class FastAPIUserService:
    """FastAPI 用户管理服务（业务表）"""

    def __init__(self):
        self.db_service = None  # 将在异步方法中初始化
        logger.info("FastAPI 用户服务初始化")

    async def get_db_service(self):
        if self.db_service is None:
            self.db_service = await get_supabase_service()
        return self.db_service

    async def create_user(
        self, username: str, email: str, password: str, is_admin: bool = False
    ) -> dict[str, Any] | None:
        """创建新用户档案（密码由 Supabase Auth 管理）。"""
        try:
            db_service = await self.get_db_service()

            # 检查用户名是否已存在
            existing_user = await db_service.get_user_by_username(username)
            if existing_user:
                logger.warning(f"用户名已存在: {username}")
                return None

            # 检查邮箱是否已存在
            existing_email = await db_service.get_user_by_email(email)
            if existing_email:
                logger.warning(f"邮箱已被注册: {email}")
                return None

            # 仅创建业务档案记录
            user_data = {
                'username': username,
                'email': email,
                'is_active': True,
                'is_verified': False,
                'email_verified': False,
                'created_at': datetime.now(),
            }

            new_user = await db_service.create_user(user_data)
            logger.info(f"新用户创建成功: {username}")
            return new_user

        except Exception as e:
            logger.error(f"用户创建失败: {e}")
            return None

    async def authenticate_user(self, username_or_email: str, password: str) -> dict[str, Any] | None:
        """验证用户登录（已由 Supabase Auth 负责）。"""
        logger.info("authenticate_user 已弃用：请使用 Supabase Auth")
        return None

    async def get_user_by_id(self, user_id: str) -> dict[str, Any] | None:
        try:
            db_service = await self.get_db_service()
            user_data = await db_service.get_profile_by_id(user_id)
            if user_data:
                logger.debug(f"获取用户成功: {user_data.get('username')}")
            else:
                logger.warning(f"用户不存在 user_id={user_id}")
            return user_data
        except Exception as e:
            logger.error(f"获取用户失败: {e}")
            return None

    async def get_user_by_username(self, username: str) -> dict[str, Any] | None:
        try:
            db_service = await self.get_db_service()
            user_data = await db_service.get_profile_by_username(username)
            if user_data:
                logger.debug(f"获取用户成功: {username}")
            else:
                logger.warning(f"用户不存在 {username}")
            return user_data
        except Exception as e:
            logger.error(f"获取用户失败: {e}")
            return None

    async def update_user_password(self, user_id: str, new_password: str) -> bool:
        """更新用户密码（由 Supabase Auth 管理，此处不再处理）。"""
        logger.info("update_user_password 已弃用：请使用 Supabase Auth 管理密码")
        return False

    async def update_user_info(self, user_id: str, **kwargs) -> dict[str, Any] | None:
        try:
            db_service = await self.get_db_service()
            user_data = await db_service.get_user_by_id(user_id)
            if not user_data:
                logger.warning(f"用户不存在 user_id={user_id}")
                return None

            # 允许更新的字段
            allowed_fields = [
                'email',
                'full_name',
                'phone',
                'avatar_url',
                'notification_enabled',
                'email_notifications_enabled',
                'pushplus_token',
            ]
            update_data: dict[str, Any] = {}
            for field, value in kwargs.items():
                if field in allowed_fields:
                    update_data[field] = value

            if not update_data:
                logger.warning("没有有效的更新字段")
                return user_data

            updated = await db_service.update_user(user_id, update_data)
            if updated:
                logger.info(f"用户信息更新成功: {user_id}")
                return await db_service.get_user_by_id(user_id)
            return user_data

        except Exception as e:
            logger.error(f"更新用户信息失败: {e}")
            return None

    async def delete_user(self, user_id: str) -> bool:
        try:
            db_service = await self.get_db_service()
            result = db_service.client.table('profiles').delete().eq('id', user_id).execute()
            return bool(result.data)
        except Exception as e:
            logger.error(f"删除用户失败: {e}")
            return False

    async def block_user(self, user_id: str) -> bool:
        """封禁用户（业务档案 is_active=False）。"""
        db_service = await self.get_db_service()
        return await db_service.update_user(user_id, {'is_active': False})

    async def unblock_user(self, user_id: str) -> bool:
        """解封用户（业务档案 is_active=True）。"""
        db_service = await self.get_db_service()
        return await db_service.update_user(user_id, {'is_active': True})

    async def search_users(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        try:
            db_service = await self.get_db_service()
            result = (
                db_service.client.table('profiles')
                .select('*')
                .or_(f"username.ilike.%{query}%,email.ilike.%{query}%")
                .limit(limit)
                .execute()
            )
            return result.data or []
        except Exception as e:
            logger.error(f"搜索用户失败: {e}")
            return []

    async def list_users(self, page: int = 1, per_page: int = 20) -> dict[str, Any]:
        try:
            db_service = await self.get_db_service()
            offset = (page - 1) * per_page

            users_result = (
                db_service.client.table('profiles').select('*').range(offset, offset + per_page - 1).execute()
            )
            users = users_result.data or []

            total_result = db_service.client.table('profiles').select('id', count='exact').execute()
            total = total_result.count or 0

            return {
                "users": users,
                "total": total,
                "page": page,
                "per_page": per_page,
                "total_pages": (total + per_page - 1) // per_page,
            }
        except Exception as e:
            logger.error(f"获取用户列表失败: {e}")
            return {"users": [], "total": 0, "page": page, "per_page": per_page, "total_pages": 0}

    async def get_user_stats(self) -> dict[str, Any]:
        try:
            db_service = await self.get_db_service()

            total_users_result = db_service.client.table('profiles').select('id', count='exact').execute()
            total_users = total_users_result.count or 0

            admin_users_result = (
                db_service.client.table('profiles').select('id', count='exact').eq('is_admin', True).execute()
            )
            admin_users = admin_users_result.count or 0

            return {
                "total_users": total_users,
                "admin_users": admin_users,
                "regular_users": total_users - admin_users,
            }
        except Exception as e:
            logger.error(f"获取用户统计失败: {e}")
            return {"total_users": 0, "admin_users": 0, "regular_users": 0}


# 创建全局服务实例
fastapi_user_service = FastAPIUserService()


# 依赖注入函数
async def get_user_service() -> FastAPIUserService:
    """获取用户服务实例"""
    return fastapi_user_service
