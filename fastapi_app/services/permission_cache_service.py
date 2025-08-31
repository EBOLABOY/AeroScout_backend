#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
权限缓存服务
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from loguru import logger

from fastapi_app.models.auth import UserInfo
from fastapi_app.dependencies.permissions import PermissionChecker, Role, Permission
from fastapi_app.services.cache_service import get_cache_service
from fastapi_app.services.user_level_service import get_user_level_service


class PermissionCacheService:
    """权限缓存服务"""
    
    def __init__(self):
        # 缓存TTL配置（秒）
        self.cache_ttl = {
            "user_permissions": 3600,    # 用户权限 - 1小时
            "level_info": 86400,         # 等级信息 - 24小时
            "user_level": 1800,          # 用户等级 - 30分钟
            "system_config": 7200        # 系统配置 - 2小时
        }

    async def get_cached_user_permissions(self, user: UserInfo) -> Optional[List[str]]:
        """获取缓存的用户权限列表"""
        try:
            cache_service = await get_cache_service()
            cache_key = f"user_permissions:{user.id}"
            
            cached_permissions = await cache_service.get(cache_key)
            if cached_permissions:
                logger.debug(f"从缓存获取用户权限: {user.username}")
                return cached_permissions.split(",") if isinstance(cached_permissions, str) else cached_permissions
            
            return None
            
        except Exception as e:
            logger.warning(f"获取缓存权限失败: {e}")
            return None

    async def cache_user_permissions(self, user: UserInfo, permissions: List[Permission]) -> bool:
        """缓存用户权限列表"""
        try:
            cache_service = await get_cache_service()
            cache_key = f"user_permissions:{user.id}"
            
            # 转换为字符串列表
            permission_strings = [perm.value for perm in permissions]
            
            await cache_service.set(
                cache_key, 
                ",".join(permission_strings),
                ttl=self.cache_ttl["user_permissions"]
            )
            
            logger.debug(f"缓存用户权限成功: {user.username}")
            return True
            
        except Exception as e:
            logger.warning(f"缓存用户权限失败: {e}")
            return False

    async def get_cached_user_level_info(self, level_name: str) -> Optional[Dict[str, Any]]:
        """获取缓存的用户等级信息"""
        try:
            cache_service = await get_cache_service()
            cache_key = f"level_info:{level_name}"
            
            cached_info = await cache_service.get(cache_key)
            if cached_info:
                logger.debug(f"从缓存获取等级信息: {level_name}")
                return cached_info
            
            return None
            
        except Exception as e:
            logger.warning(f"获取缓存等级信息失败: {e}")
            return None

    async def cache_user_level_info(self, level_name: str, level_info: Dict[str, Any]) -> bool:
        """缓存用户等级信息"""
        try:
            cache_service = await get_cache_service()
            cache_key = f"level_info:{level_name}"
            
            await cache_service.set(
                cache_key, 
                level_info,
                ttl=self.cache_ttl["level_info"]
            )
            
            logger.debug(f"缓存等级信息成功: {level_name}")
            return True
            
        except Exception as e:
            logger.warning(f"缓存等级信息失败: {e}")
            return False

    async def get_enhanced_user_permissions(self, user: UserInfo) -> List[Permission]:
        """获取增强的用户权限（带缓存）"""
        try:
            # 尝试从缓存获取
            cached_permissions = await self.get_cached_user_permissions(user)
            if cached_permissions:
                # 转换回Permission枚举
                permissions = []
                for perm_str in cached_permissions:
                    try:
                        permissions.append(Permission(perm_str))
                    except ValueError:
                        logger.warning(f"无效的权限字符串: {perm_str}")
                return permissions
            
            # 缓存未命中，重新计算
            permissions = PermissionChecker.get_user_permissions(user)
            
            # 缓存结果
            await self.cache_user_permissions(user, permissions)
            
            return permissions
            
        except Exception as e:
            logger.error(f"获取增强用户权限失败: {e}")
            # 降级到基础权限检查
            return PermissionChecker.get_user_permissions(user)

    async def get_enhanced_level_benefits(self, level_name: str) -> Optional[Dict[str, Any]]:
        """获取增强的等级权益信息（带缓存）"""
        try:
            # 尝试从缓存获取
            cached_benefits = await self.get_cached_user_level_info(level_name)
            if cached_benefits:
                return cached_benefits
            
            # 缓存未命中，从服务获取
            level_service = await get_user_level_service()
            benefits = await level_service.get_user_level_benefits(level_name)
            
            if benefits:
                # 缓存结果
                await self.cache_user_level_info(level_name, benefits)
            
            return benefits
            
        except Exception as e:
            logger.error(f"获取增强等级权益失败: {e}")
            return None

    async def invalidate_user_cache(self, user_id: str) -> bool:
        """失效用户相关缓存"""
        try:
            cache_service = await get_cache_service()
            
            # 删除用户权限缓存
            cache_keys = [
                f"user_permissions:{user_id}",
                f"quota:{user_id}:*",  # 用户配额相关缓存
            ]
            
            for key in cache_keys:
                try:
                    await cache_service.delete(key)
                except:
                    pass  # 忽略删除失败
            
            logger.info(f"用户缓存失效成功: {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"失效用户缓存失败: {e}")
            return False

    async def invalidate_level_cache(self, level_name: str) -> bool:
        """失效等级相关缓存"""
        try:
            cache_service = await get_cache_service()
            
            cache_key = f"level_info:{level_name}"
            await cache_service.delete(cache_key)
            
            logger.info(f"等级缓存失效成功: {level_name}")
            return True
            
        except Exception as e:
            logger.error(f"失效等级缓存失败: {e}")
            return False

    async def warm_up_cache(self) -> Dict[str, Any]:
        """预热缓存"""
        try:
            results = {
                "levels_cached": 0,
                "errors": []
            }
            
            # 预热所有等级信息
            level_service = await get_user_level_service()
            levels = await level_service.get_all_user_levels()
            
            for level in levels:
                try:
                    benefits = await level_service.get_user_level_benefits(level["name"])
                    if benefits:
                        await self.cache_user_level_info(level["name"], benefits)
                        results["levels_cached"] += 1
                except Exception as e:
                    results["errors"].append(f"预热等级 {level['name']} 失败: {e}")
            
            logger.info(f"缓存预热完成: {results}")
            return results
            
        except Exception as e:
            logger.error(f"缓存预热失败: {e}")
            return {"levels_cached": 0, "errors": [str(e)]}

    async def get_cache_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        try:
            cache_service = await get_cache_service()
            
            # 统计不同类型的缓存键数量
            stats = {
                "user_permissions": 0,
                "level_info": 0,
                "quota_cache": 0,
                "total_keys": 0,
                "cache_health": "healthy"
            }
            
            # 这里可以根据具体的缓存实现来获取统计信息
            # Redis实现可能需要使用SCAN命令来统计键数量
            
            return stats
            
        except Exception as e:
            logger.error(f"获取缓存统计失败: {e}")
            return {"cache_health": "error", "error": str(e)}


# 全局权限缓存服务实例
_permission_cache_service = None

async def get_permission_cache_service() -> PermissionCacheService:
    """获取权限缓存服务实例"""
    global _permission_cache_service
    if _permission_cache_service is None:
        _permission_cache_service = PermissionCacheService()
    return _permission_cache_service