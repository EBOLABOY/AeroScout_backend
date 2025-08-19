"""
异步任务管理服务
用于管理长时间运行的AI搜索任务
"""
import uuid
import json
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from enum import Enum
from loguru import logger

from fastapi_app.services.cache_service import CacheService


class TaskStatus(str, Enum):
    """任务状态枚举"""
    PENDING = "PENDING"      # 等待处理
    PROCESSING = "PROCESSING"  # 正在处理
    COMPLETED = "COMPLETED"   # 已完成
    FAILED = "FAILED"        # 失败


class AsyncTaskService:
    """异步任务管理服务"""
    
    def __init__(self):
        self.cache_service = CacheService()
        self.task_prefix = "async_task"
        self.default_ttl = 3600  # 1小时过期
        
    async def initialize(self):
        """初始化服务"""
        await self.cache_service.connect()
        logger.info("AsyncTaskService初始化完成")
    
    def generate_task_id(self) -> str:
        """生成唯一任务ID"""
        return str(uuid.uuid4())
    
    def _get_task_key(self, task_id: str, suffix: str = "") -> str:
        """获取任务在Redis中的键名"""
        if suffix:
            return f"{self.task_prefix}:{task_id}:{suffix}"
        return f"{self.task_prefix}:{task_id}"
    
    async def create_task(
        self, 
        task_type: str,
        search_params: Dict[str, Any],
        user_id: Optional[int] = None
    ) -> str:
        """
        创建新任务
        
        Args:
            task_type: 任务类型 (如: 'ai_flight_search')
            search_params: 搜索参数
            user_id: 用户ID
            
        Returns:
            task_id: 任务ID
        """
        task_id = self.generate_task_id()
        
        # 任务基本信息
        task_info = {
            "task_id": task_id,
            "task_type": task_type,
            "status": TaskStatus.PENDING,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "user_id": user_id,
            "search_params": search_params,
            "progress": 0,
            "message": "任务已创建，等待处理...",
            "estimated_duration": 120  # 预估2分钟
        }
        
        # 存储任务信息
        await self.cache_service.set(
            self._get_task_key(task_id, "info"),
            task_info,
            expire=self.default_ttl
        )
        
        # 存储任务状态
        await self.cache_service.set(
            self._get_task_key(task_id, "status"),
            TaskStatus.PENDING,
            expire=self.default_ttl
        )
        
        logger.info(f"创建异步任务: {task_id}, 类型: {task_type}")
        return task_id
    
    async def update_task_status(
        self,
        task_id: str,
        status: TaskStatus,
        progress: Optional[float] = None,
        message: Optional[str] = None,
        error: Optional[str] = None
    ) -> bool:
        """
        更新任务状态
        
        Args:
            task_id: 任务ID
            status: 新状态
            progress: 进度 (0.0-1.0)
            message: 状态消息
            error: 错误信息
        """
        try:
            # 获取当前任务信息
            task_info = await self.cache_service.get(
                self._get_task_key(task_id, "info"),
                dict
            )
            
            if not task_info:
                logger.error(f"任务不存在: {task_id}")
                return False
            
            # 更新任务信息
            task_info["status"] = status
            task_info["updated_at"] = datetime.now().isoformat()
            
            if progress is not None:
                task_info["progress"] = progress
            
            if message is not None:
                task_info["message"] = message
            
            if error is not None:
                task_info["error"] = error
            
            # 保存更新后的信息
            await self.cache_service.set(
                self._get_task_key(task_id, "info"),
                task_info,
                expire=self.default_ttl
            )
            
            # 更新状态
            await self.cache_service.set(
                self._get_task_key(task_id, "status"),
                status,
                expire=self.default_ttl
            )
            
            logger.info(f"任务状态更新: {task_id} -> {status}")
            return True
            
        except Exception as e:
            logger.error(f"更新任务状态失败 {task_id}: {e}")
            return False
    
    async def get_task_info(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取任务信息"""
        try:
            task_info = await self.cache_service.get(
                self._get_task_key(task_id, "info"),
                dict
            )
            return task_info
        except Exception as e:
            logger.error(f"获取任务信息失败 {task_id}: {e}")
            return None
    
    async def get_task_status(self, task_id: str) -> Optional[TaskStatus]:
        """获取任务状态"""
        try:
            status = await self.cache_service.get(
                self._get_task_key(task_id, "status"),
                str
            )
            return TaskStatus(status) if status else None
        except Exception as e:
            logger.error(f"获取任务状态失败 {task_id}: {e}")
            return None
    
    async def save_task_result(
        self,
        task_id: str,
        result: Dict[str, Any]
    ) -> bool:
        """保存任务结果"""
        try:
            await self.cache_service.set(
                self._get_task_key(task_id, "result"),
                result,
                expire=self.default_ttl
            )
            
            logger.info(f"任务结果已保存: {task_id}")
            return True
            
        except Exception as e:
            logger.error(f"保存任务结果失败 {task_id}: {e}")
            return False
    
    async def get_task_result(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取任务结果"""
        try:
            result = await self.cache_service.get(
                self._get_task_key(task_id, "result"),
                dict
            )
            return result
        except Exception as e:
            logger.error(f"获取任务结果失败 {task_id}: {e}")
            return None
    
    async def delete_task(self, task_id: str) -> bool:
        """删除任务（清理资源）"""
        try:
            keys_to_delete = [
                self._get_task_key(task_id, "info"),
                self._get_task_key(task_id, "status"),
                self._get_task_key(task_id, "result")
            ]
            
            for key in keys_to_delete:
                await self.cache_service.delete(key)
            
            logger.info(f"任务已删除: {task_id}")
            return True
            
        except Exception as e:
            logger.error(f"删除任务失败 {task_id}: {e}")
            return False
    
    async def cleanup_expired_tasks(self) -> int:
        """清理过期任务"""
        # 这个方法可以通过定时任务调用
        # 由于Redis会自动过期，这里主要用于统计
        logger.info("执行过期任务清理")
        return 0


# 全局实例
async_task_service = AsyncTaskService()
