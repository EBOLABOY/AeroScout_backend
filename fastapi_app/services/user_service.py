"""
FastAPI用户管理服务
"""
from typing import Optional, List, Dict, Any
from datetime import datetime
from loguru import logger
from fastapi_app.utils.password import get_password_hash, verify_password
from fastapi_app.models.auth import UserInfo
from fastapi_app.services.supabase_service import get_supabase_service


class FastAPIUserService:
    """FastAPI用户管理服务"""
    
    def __init__(self):
        """初始化用户服务"""
        self.db_service = None  # 将在异步方法中初始化
        logger.info("FastAPI用户服务初始化")

    async def get_db_service(self):
        """获取数据库服务"""
        if self.db_service is None:
            self.db_service = await get_supabase_service()
        return self.db_service
    
    async def create_user(self, username: str, email: str, password: str, is_admin: bool = False) -> Optional[Dict[str, Any]]:
        """创建新用户"""
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
            
            # 创建新用户
            user_data = {
                'username': username,
                'email': email,
                'password_hash': get_password_hash(password),
                'is_active': True,
                'is_verified': False,
                'email_verified': False,
                'created_at': datetime.now()
            }
            
            new_user = await db_service.create_user(user_data)
            logger.info(f"新用户创建成功: {username}")
            return new_user
            
        except Exception as e:
            logger.error(f"用户创建失败: {e}")
            return None
    
    async def authenticate_user(self, username_or_email: str, password: str) -> Optional[Dict[str, Any]]:
        """验证用户登录"""
        try:
            # 查找用户（支持用户名或邮箱登录）
            user_data = await self.db_service.get_user_by_username(username_or_email)
            if not user_data:
                user_data = await self.db_service.get_user_by_email(username_or_email)
            
            if not user_data:
                logger.warning(f"用户不存在: {username_or_email}")
                return None
            
            # 验证密码
            if not verify_password(password, user_data['password_hash']):
                logger.warning(f"密码错误: {username_or_email}")
                return None
            
            logger.info(f"用户认证成功: {user_data['username']}")
            return user_data
            
        except Exception as e:
            logger.error(f"用户认证失败: {e}")
            return None
    
    async def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        """根据ID获取用户"""
        try:
            user_data = await self.db_service.get_user_by_id(user_id)
            if user_data:
                logger.debug(f"获取用户成功: {user_data['username']}")
            else:
                logger.warning(f"用户不存在: user_id={user_id}")
            return user_data
        except Exception as e:
            logger.error(f"获取用户失败: {e}")
            return None
    
    async def get_user_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        """根据用户名获取用户"""
        try:
            user_data = await self.db_service.get_user_by_username(username)
            if user_data:
                logger.debug(f"获取用户成功: {username}")
            else:
                logger.warning(f"用户不存在: {username}")
            return user_data
        except Exception as e:
            logger.error(f"获取用户失败: {e}")
            return None
    
    async def update_user_password(self, user_id: str, new_password: str) -> bool:
        """更新用户密码"""
        try:
            user_data = await self.db_service.get_user_by_id(user_id)
            if not user_data:
                logger.warning(f"用户不存在: user_id={user_id}")
                return False
            
            update_data = {
                'password_hash': get_password_hash(new_password)
            }
            
            updated_user = await self.db_service.update_user(user_id, update_data)
            if updated_user:
                logger.info(f"用户密码更新成功: {user_data['username']}")
                return True
            return False
            
        except Exception as e:
            logger.error(f"更新用户密码失败: {e}")
            return False
    
    async def update_user_info(self, user_id: str, **kwargs) -> Optional[Dict[str, Any]]:
        """更新用户信息"""
        try:
            user_data = await self.db_service.get_user_by_id(user_id)
            if not user_data:
                logger.warning(f"用户不存在: user_id={user_id}")
                return None
            
            # 更新允许的字段
            allowed_fields = ['email', 'full_name', 'phone', 'avatar_url', 'notification_enabled', 'email_notifications_enabled', 'pushplus_token']
            update_data = {}
            for field, value in kwargs.items():
                if field in allowed_fields:
                    update_data[field] = value
            
            if not update_data:
                logger.warning("没有有效的更新字段")
                return user_data
            
            updated_user = await self.db_service.update_user(user_id, update_data)
            if updated_user:
                logger.info(f"用户信息更新成功: {user_data['username']}")
            return updated_user
            
        except Exception as e:
            logger.error(f"更新用户信息失败: {e}")
            return None
    
    async def delete_user(self, user_id: str) -> bool:
        """删除用户"""
        try:
            db_service = await self.get_db_service()
            result = db_service.client.table('users').delete().eq('id', user_id).execute()
            return bool(result.data)
        except Exception as e:
            logger.error(f"删除用户失败: {e}")
            return False

    async def block_user(self, user_id: str) -> bool:
        """封禁用户"""
        return await self._update_record("users", user_id, {'is_active': False})

    async def unblock_user(self, user_id: str) -> bool:
        """解封用户"""
        return await self._update_record("users", user_id, {'is_active': True})

    async def search_users(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """搜索用户"""
        try:
            db_service = await self.get_db_service()
            result = db_service.client.table('users').select('*').or_(
                f'username.ilike.%{query}%,email.ilike.%{query}%'
            ).limit(limit).execute()
            return result.data or []
        except Exception as e:
            logger.error(f"搜索用户失败: {e}")
            return []
    
    async def list_users(self, page: int = 1, per_page: int = 20) -> Dict[str, Any]:
        """获取用户列表"""
        try:
            db_service = await self.get_db_service()
            offset = (page - 1) * per_page
            
            users_result = db_service.client.table('users').select('*').range(offset, offset + per_page - 1).execute()
            users = users_result.data or []
            
            total_result = db_service.client.table('users').select('id', count='exact').execute()
            total = total_result.count or 0
            
            return {
                "users": users,
                "total": total,
                "page": page,
                "per_page": per_page,
                "total_pages": (total + per_page - 1) // per_page
            }
        except Exception as e:
            logger.error(f"获取用户列表失败: {e}")
            return {"users": [], "total": 0, "page": page, "per_page": per_page, "total_pages": 0}
    
    async def get_user_stats(self) -> Dict[str, Any]:
        """获取用户统计信息"""
        try:
            db_service = await self.get_db_service()
            
            total_users_result = db_service.client.table('users').select('id', count='exact').execute()
            total_users = total_users_result.count or 0
            
            admin_users_result = db_service.client.table('users').select('id', count='exact').eq('is_admin', True).execute()
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
