"""
Redis缓存服务
提供异步Redis缓存操作的统一接口
"""
import json
import asyncio
from datetime import datetime, timedelta
from typing import Any, Optional, Dict, List, Union
from loguru import logger
try:
    import redis.asyncio as aioredis
    from redis.asyncio import Redis
    REDIS_AVAILABLE = True
except ImportError as e:
    logger.warning(f"redis.asyncio导入失败: {e}, 将使用内存缓存作为降级方案")
    REDIS_AVAILABLE = False
    Redis = None

from fastapi_app.config import settings


class CacheService:
    """Redis缓存服务，支持内存缓存降级"""

    def __init__(self):
        """初始化缓存服务"""
        self.redis: Optional[Any] = None
        self.settings = settings
        self._connection_pool = None
        # 内存缓存降级方案
        self._memory_cache: Dict[str, Dict] = {}
        self._memory_cache_lock = asyncio.Lock()
        logger.info("CacheService初始化成功")
    
    async def connect(self):
        """连接Redis"""
        if not REDIS_AVAILABLE:
            logger.warning("aioredis不可用，使用内存缓存作为降级方案")
            self.redis = None
            return

        try:
            redis_url = getattr(self.settings, 'REDIS_URL', 'redis://localhost:6379/0')
            self.redis = await aioredis.from_url(
                redis_url,
                encoding="utf-8",
                decode_responses=True,
                max_connections=20,
                retry_on_timeout=True
            )

            # 测试连接
            await self.redis.ping()
            logger.info(f"Redis连接成功: {redis_url}")

        except Exception as e:
            logger.error(f"Redis连接失败: {e}")
            # 如果Redis连接失败，使用内存缓存作为降级方案
            self.redis = None
    
    async def disconnect(self):
        """断开Redis连接"""
        if self.redis:
            await self.redis.close()
            logger.info("Redis连接已关闭")
    
    def _serialize_value(self, value: Any) -> str:
        """序列化值"""
        if isinstance(value, (dict, list)):
            return json.dumps(value, ensure_ascii=False, default=str)
        elif isinstance(value, datetime):
            return value.isoformat()
        else:
            return str(value)

    def _is_memory_cache_expired(self, cache_entry: Dict) -> bool:
        """检查内存缓存是否过期"""
        if 'expire_at' not in cache_entry:
            return False
        return datetime.now() > datetime.fromisoformat(cache_entry['expire_at'])

    async def _memory_cache_cleanup(self):
        """清理过期的内存缓存"""
        async with self._memory_cache_lock:
            expired_keys = []
            for key, entry in self._memory_cache.items():
                if self._is_memory_cache_expired(entry):
                    expired_keys.append(key)

            for key in expired_keys:
                del self._memory_cache[key]

            if expired_keys:
                logger.debug(f"清理了 {len(expired_keys)} 个过期的内存缓存项")

    def _deserialize_value(self, value: str, value_type: type = None) -> Any:
        """反序列化值"""
        if not value:
            return None
            
        try:
            if value_type == dict or value_type == list:
                return json.loads(value)
            elif value_type == datetime:
                return datetime.fromisoformat(value)
            elif value_type == int:
                return int(value)
            elif value_type == float:
                return float(value)
            elif value_type == bool:
                return value.lower() in ('true', '1', 'yes')
            else:
                # 尝试自动检测JSON
                if value.startswith(('{', '[')):
                    return json.loads(value)
                return value
        except (json.JSONDecodeError, ValueError):
            return value
    
    async def get(self, key: str, value_type: type = None) -> Any:
        """获取缓存值"""
        if self.redis:
            try:
                value = await self.redis.get(key)
                if value is None:
                    return None
                return self._deserialize_value(value, value_type)
            except Exception as e:
                logger.error(f"Redis获取缓存失败 {key}: {e}")
                # Redis失败时降级到内存缓存

        # 使用内存缓存（Redis不可用或失败时）
        async with self._memory_cache_lock:
            if key in self._memory_cache:
                entry = self._memory_cache[key]
                if not self._is_memory_cache_expired(entry):
                    return self._deserialize_value(entry['value'], value_type)
                else:
                    # 删除过期项
                    del self._memory_cache[key]
            return None
    
    async def set(
        self,
        key: str,
        value: Any,
        expire: Optional[int] = None,
        expire_timedelta: Optional[timedelta] = None
    ) -> bool:
        """设置缓存值"""
        if self.redis:
            try:
                serialized_value = self._serialize_value(value)

                if expire_timedelta:
                    expire = int(expire_timedelta.total_seconds())

                if expire:
                    await self.redis.setex(key, expire, serialized_value)
                else:
                    await self.redis.set(key, serialized_value)

                return True
            except Exception as e:
                logger.error(f"Redis设置缓存失败 {key}: {e}")
                # Redis失败时降级到内存缓存

        # 使用内存缓存（Redis不可用或失败时）
        try:
            serialized_value = self._serialize_value(value)

            if expire_timedelta:
                expire = int(expire_timedelta.total_seconds())

            cache_entry = {
                'value': serialized_value,
                'created_at': datetime.now().isoformat()
            }

            if expire:
                expire_at = datetime.now() + timedelta(seconds=expire)
                cache_entry['expire_at'] = expire_at.isoformat()

            async with self._memory_cache_lock:
                self._memory_cache[key] = cache_entry
                # 定期清理过期项（每100次写入清理一次）
                if len(self._memory_cache) % 100 == 0:
                    await self._memory_cache_cleanup()

            logger.debug(f"使用内存缓存保存: {key}")
            return True
        except Exception as e:
            logger.error(f"内存缓存设置失败 {key}: {e}")
            return False
    
    async def delete(self, key: str) -> bool:
        """删除缓存"""
        redis_success = False
        memory_success = False

        if self.redis:
            try:
                result = await self.redis.delete(key)
                redis_success = result > 0
            except Exception as e:
                logger.error(f"Redis删除缓存失败 {key}: {e}")

        # 同时删除内存缓存
        async with self._memory_cache_lock:
            if key in self._memory_cache:
                del self._memory_cache[key]
                memory_success = True

        return redis_success or memory_success
    
    async def delete_pattern(self, pattern: str) -> int:
        """删除匹配模式的缓存"""
        if not self.redis:
            return 0
            
        try:
            keys = await self.redis.keys(pattern)
            if keys:
                return await self.redis.delete(*keys)
            return 0
        except Exception as e:
            logger.error(f"删除模式缓存失败 {pattern}: {e}")
            return 0
    
    async def exists(self, key: str) -> bool:
        """检查缓存是否存在"""
        if not self.redis:
            return False
            
        try:
            return await self.redis.exists(key) > 0
        except Exception as e:
            logger.error(f"检查缓存存在失败 {key}: {e}")
            return False
    
    async def expire(self, key: str, seconds: int) -> bool:
        """设置缓存过期时间"""
        if not self.redis:
            return False
            
        try:
            return await self.redis.expire(key, seconds)
        except Exception as e:
            logger.error(f"设置缓存过期失败 {key}: {e}")
            return False
    
    async def ttl(self, key: str) -> int:
        """获取缓存剩余时间"""
        if not self.redis:
            return -1
            
        try:
            return await self.redis.ttl(key)
        except Exception as e:
            logger.error(f"获取缓存TTL失败 {key}: {e}")
            return -1
    
    # ---- 业务相关缓存方法 ----
    
    async def cache_user_info(self, user_id: int, user_data: Dict[str, Any]) -> bool:
        """缓存用户信息（5分钟过期）"""
        key = f"user:info:{user_id}"
        return await self.set(key, user_data, expire=300)  # 5分钟
    
    async def get_user_info(self, user_id: int) -> Optional[Dict[str, Any]]:
        """获取用户信息缓存"""
        key = f"user:info:{user_id}"
        return await self.get(key, dict)
    
    async def invalidate_user_cache(self, user_id: int) -> bool:
        """清除用户相关缓存"""
        pattern = f"user:*:{user_id}"
        count = await self.delete_pattern(pattern)
        logger.info(f"清除用户 {user_id} 相关缓存 {count} 个")
        return count > 0
    
    async def cache_monitor_tasks(self, user_id: int, tasks_data: Dict[str, Any]) -> bool:
        """缓存用户监控任务列表（2分钟过期）"""
        key = f"monitor:tasks:{user_id}"
        return await self.set(key, tasks_data, expire=120)  # 2分钟
    
    async def get_monitor_tasks(self, user_id: int) -> Optional[Dict[str, Any]]:
        """获取用户监控任务列表缓存"""
        key = f"monitor:tasks:{user_id}"
        return await self.get(key, dict)
    
    async def invalidate_monitor_tasks_cache(self, user_id: int) -> bool:
        """清除用户监控任务缓存"""
        key = f"monitor:tasks:{user_id}"
        return await self.delete(key)
    
    async def cache_flight_search_results(
        self, 
        search_params: Dict[str, Any], 
        results: List[Dict[str, Any]]
    ) -> bool:
        """缓存航班搜索结果（10分钟过期）"""
        # 生成缓存键
        params_str = json.dumps(search_params, sort_keys=True, ensure_ascii=False)
        import hashlib
        cache_key = hashlib.md5(params_str.encode()).hexdigest()
        key = f"flight:search:{cache_key}"
        
        cache_data = {
            'search_params': search_params,
            'results': results,
            'cached_at': datetime.now().isoformat()
        }
        
        return await self.set(key, cache_data, expire=600)  # 10分钟
    
    async def get_flight_search_results(self, search_params: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
        """获取航班搜索结果缓存"""
        params_str = json.dumps(search_params, sort_keys=True, ensure_ascii=False)
        import hashlib
        cache_key = hashlib.md5(params_str.encode()).hexdigest()
        key = f"flight:search:{cache_key}"
        
        cached_data = await self.get(key, dict)
        if cached_data:
            return cached_data.get('results')
        return None
    
    async def cache_airports_list(self, airports: List[Dict[str, Any]]) -> bool:
        """缓存机场列表（24小时过期）"""
        key = "airports:list"
        return await self.set(key, airports, expire=86400)  # 24小时
    
    async def get_airports_list(self) -> Optional[List[Dict[str, Any]]]:
        """获取机场列表缓存"""
        key = "airports:list"
        return await self.get(key, list)
    
    async def cache_monitor_stats(self, stats: Dict[str, Any]) -> bool:
        """缓存监控统计信息（1分钟过期）"""
        key = "monitor:stats"
        return await self.set(key, stats, expire=60)  # 1分钟
    
    async def get_monitor_stats(self) -> Optional[Dict[str, Any]]:
        """获取监控统计信息缓存"""
        key = "monitor:stats"
        return await self.get(key, dict)
    
    # ---- 缓存预热 ----
    
    async def warm_up_cache(self):
        """缓存预热"""
        logger.info("开始缓存预热...")
        
        try:
            # 这里可以预加载一些常用数据
            # 例如：机场列表、热门城市等
            logger.info("缓存预热完成")
        except Exception as e:
            logger.error(f"缓存预热失败: {e}")
    
    # ---- 缓存健康检查 ----
    
    async def health_check(self) -> Dict[str, Any]:
        """缓存健康检查"""
        if not self.redis:
            return {
                'status': 'disconnected',
                'message': 'Redis未连接'
            }
        
        try:
            # 测试基本操作
            test_key = "health_check_test"
            test_value = "test_value"
            
            await self.redis.set(test_key, test_value, ex=10)
            retrieved_value = await self.redis.get(test_key)
            await self.redis.delete(test_key)
            
            if retrieved_value == test_value:
                info = await self.redis.info()
                return {
                    'status': 'healthy',
                    'message': 'Redis连接正常',
                    'connected_clients': info.get('connected_clients', 0),
                    'used_memory_human': info.get('used_memory_human', 'unknown'),
                    'uptime_in_seconds': info.get('uptime_in_seconds', 0)
                }
            else:
                return {
                    'status': 'error',
                    'message': 'Redis读写测试失败'
                }
                
        except Exception as e:
            return {
                'status': 'error',
                'message': f'Redis健康检查失败: {str(e)}'
            }


# 全局缓存服务实例
_cache_service: Optional[CacheService] = None


async def get_cache_service() -> CacheService:
    """获取缓存服务实例（单例模式）"""
    global _cache_service
    if _cache_service is None:
        _cache_service = CacheService()
        await _cache_service.connect()
    return _cache_service


async def close_cache_service():
    """关闭缓存服务"""
    global _cache_service
    if _cache_service:
        await _cache_service.disconnect()
        _cache_service = None