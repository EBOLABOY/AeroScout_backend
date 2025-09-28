"""
异步任务管理服务
用于管理长时间运行的AI搜索任务
"""

import uuid
from datetime import datetime
from enum import Enum
from typing import Any

from fastapi import Request
from loguru import logger

from fastapi_app.services.cache_service import CacheService


class TaskStatus(str, Enum):
    """任务状态枚举"""

    PENDING = "PENDING"  # 等待处理
    PROCESSING = "PROCESSING"  # 正在处理
    COMPLETED = "COMPLETED"  # 已完成
    FAILED = "FAILED"  # 失败


class ProcessingStage(str, Enum):
    """处理阶段枚举"""

    INITIALIZATION = "initialization"  # 初始化阶段 (0-25%)
    SEARCHING = "searching"  # 搜索阶段 (25-50%)
    AI_ANALYSIS = "ai_analysis"  # AI分析阶段 (50-75%)
    FINALIZING = "finalizing"  # 生成推荐阶段 (75-100%)


class StageInfo:
    """阶段信息类"""

    STAGES = {
        ProcessingStage.INITIALIZATION: {
            "id": 0,
            "title": "连接数据库",
            "description": "连接到航班数据系统...",
            "icon": "search",  # 前端期望的图标
            "min_progress": 0,
            "max_progress": 25,
        },
        ProcessingStage.SEARCHING: {
            "id": 1,
            "title": "搜索航班",
            "description": "在各大航空公司中查找最优选择...",
            "icon": "flight",  # 前端期望的图标
            "min_progress": 25,
            "max_progress": 50,
        },
        ProcessingStage.AI_ANALYSIS: {
            "id": 2,
            "title": "分析数据",
            "description": "AI智能分析价格和时间...",
            "icon": "analytics",  # 前端期望的图标
            "min_progress": 50,
            "max_progress": 75,
        },
        ProcessingStage.FINALIZING: {
            "id": 3,
            "title": "生成推荐",
            "description": "为您个性化定制最佳方案...",
            "icon": "check",  # 前端期望的图标
            "min_progress": 75,
            "max_progress": 100,
        },
    }

    @classmethod
    def get_stage_info(cls, stage: ProcessingStage) -> dict[str, Any]:
        """获取阶段信息"""
        return cls.STAGES.get(stage, {})

    @classmethod
    def get_stage_by_progress(cls, progress: float) -> ProcessingStage:
        """根据进度获取当前阶段"""
        if progress < 25:
            return ProcessingStage.INITIALIZATION
        elif progress < 50:
            return ProcessingStage.SEARCHING
        elif progress < 75:
            return ProcessingStage.AI_ANALYSIS
        else:
            return ProcessingStage.FINALIZING


class AsyncTaskService:
    """异步任务管理服务"""

    def __init__(self, cache_service: CacheService | None = None):
        self.cache_service = cache_service or CacheService()
        self.task_prefix = "async_task"
        self.default_ttl = 3600  # 1小时过期

    async def initialize(self):
        """初始化服务"""
        if not self.cache_service.is_connected():
            await self.cache_service.connect()

        if not self.cache_service.is_connected():
            logger.error("Redis连接不可用，异步任务服务无法启动")
            raise RuntimeError("AsyncTaskService initialization failed: Redis unavailable")

        logger.info("AsyncTaskService初始化完成")

    def generate_task_id(self) -> str:
        """生成唯一任务ID"""
        return str(uuid.uuid4())

    def _get_task_key(self, task_id: str, suffix: str = "") -> str:
        """获取任务在Redis中的键名"""
        if suffix:
            return f"{self.task_prefix}:{task_id}:{suffix}"
        return f"{self.task_prefix}:{task_id}"

    async def create_task(self, task_type: str, search_params: dict[str, Any], user_id: int | None = None) -> str:
        """
        创建新任务

        Args:
            task_type: 任务类型 (如: 'ai_flight_search')
            search_params: 搜索参数
            user_id: 用户ID

        Returns:
            task_id: 任务ID
        """
        if not self.cache_service.is_connected():
            logger.error("Redis连接不可用，无法创建异步任务")
            raise RuntimeError("Async task cache unavailable")

        task_id = self.generate_task_id()

        # 任务基本信息
        task_info = {
            "task_id": task_id,
            "task_type": task_type,
            "status": TaskStatus.PENDING.value,  # 确保保存为字符串
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "user_id": user_id,
            "search_params": search_params,
            "progress": 0,
            "message": "任务已创建，等待处理...",
            "estimated_duration": 120,  # 预估2分钟
            "stage": ProcessingStage.INITIALIZATION.value,  # 添加阶段信息
            "stage_info": StageInfo.get_stage_info(ProcessingStage.INITIALIZATION),
        }

        cache_backend = "redis"
        info_key = self._get_task_key(task_id, "info")
        status_key = self._get_task_key(task_id, "status")

        logger.debug(
            f"准备向{cache_backend}写入异步任务信息: task_id={task_id}, key={info_key}, type={task_type}"
        )
        logger.debug(f"任务元数据: {task_info}")

        info_saved = await self.cache_service.set(
            info_key, task_info, expire=self.default_ttl, require_redis=True
        )
        if not info_saved:
            logger.error(f"任务信息 {task_id} 写入缓存失败 (key={info_key})")
            raise RuntimeError("Failed to persist async task metadata")

        retrieved_info = await self.cache_service.get(info_key, dict, require_redis=True)
        if not retrieved_info:
            logger.error(f"严重错误: 刚写入的任务 {task_id} 无法从缓存读取 (key={info_key})")
            await self.cache_service.delete(info_key, require_redis=True)
            raise RuntimeError("Async task metadata verification failed")

        logger.debug(f"已确认任务信息写入成功: {task_id}")

        status_saved = await self.cache_service.set(
            status_key,
            TaskStatus.PENDING.value,  # 确保保存为字符串
            expire=self.default_ttl,
            require_redis=True,
        )
        if not status_saved:
            logger.error(f"任务状态 {task_id} 写入缓存失败 (key={status_key})")
            await self.cache_service.delete(info_key, require_redis=True)
            await self.cache_service.delete(status_key, require_redis=True)
            raise RuntimeError("Failed to persist async task status")

        logger.info(f"创建异步任务: {task_id}, 类型: {task_type}, 缓存后端: {cache_backend}")
        return task_id

    async def update_task_status(
        self,
        task_id: str,
        status: TaskStatus,
        progress: float | None = None,
        message: str | None = None,
        error: str | None = None,
        stage: ProcessingStage | None = None,
    ) -> bool:
        """
        更新任务状态

        Args:
            task_id: 任务ID
            status: 新状态
            progress: 进度 (0.0-1.0)
            message: 状态消息
            error: 错误信息
            stage: 处理阶段
        """
        try:
            # 获取当前任务信息
            task_info = await self.cache_service.get(
                self._get_task_key(task_id, "info"),
                dict,
                require_redis=True,
            )

            if not task_info:
                logger.error(f"任务不存在: {task_id}")
                return False

            # 更新任务信息
            task_info["status"] = status.value  # 确保保存为字符串
            task_info["updated_at"] = datetime.now().isoformat()

            if progress is not None:
                task_info["progress"] = progress
                # 如果进度更新了，自动更新阶段
                if stage is None:
                    stage = StageInfo.get_stage_by_progress(progress)

            if message is not None:
                task_info["message"] = message

            if error is not None:
                task_info["error"] = error

            # 更新阶段信息
            if stage is not None:
                task_info["stage"] = stage.value
                task_info["stage_info"] = StageInfo.get_stage_info(stage)

            info_updated = await self.cache_service.set(
                self._get_task_key(task_id, "info"),
                task_info,
                expire=self.default_ttl,
                require_redis=True,
            )

            status_updated = await self.cache_service.set(
                self._get_task_key(task_id, "status"),
                status.value,  # 确保保存为字符串
                expire=self.default_ttl,
                require_redis=True,
            )

            if not info_updated or not status_updated:
                logger.error(f"任务状态 {task_id} 写入缓存失败")
                return False

            logger.info(
                f"任务状态更新: {task_id} -> {status} (进度: {progress}%, 阶段: {stage.value if stage else 'auto'})"
            )
            return True

        except Exception as e:
            logger.error(f"更新任务状态失败 {task_id}: {e}")
            return False


    async def get_task_info(self, task_id: str) -> dict[str, Any] | None:
        """获取任务信息"""
        try:
            task_info = await self.cache_service.get(self._get_task_key(task_id, "info"), dict, require_redis=True)
            return task_info
        except Exception as e:
            logger.error(f"获取任务信息失败 {task_id}: {e}")
            return None

    async def get_task_status(self, task_id: str) -> TaskStatus | None:
        """获取任务状态"""
        try:
            status = await self.cache_service.get(self._get_task_key(task_id, "status"), str, require_redis=True)
            return TaskStatus(status) if status else None
        except Exception as e:
            logger.error(f"获取任务状态失败 {task_id}: {e}")
            return None

    async def save_task_result(self, task_id: str, result: dict[str, Any]) -> bool:
        """保存任务结果"""
        try:
            saved = await self.cache_service.set(
                self._get_task_key(task_id, "result"),
                result,
                expire=self.default_ttl,
                require_redis=True,
            )

            if not saved:
                logger.error(f"任务结果 {task_id} 写入缓存失败")
                return False

            logger.info(f"任务结果已保存: {task_id}")
            return True

        except Exception as e:
            logger.error(f"保存任务结果失败 {task_id}: {e}")
            return False


    async def get_task_result(self, task_id: str) -> dict[str, Any] | None:
        """获取任务结果"""
        try:
            result = await self.cache_service.get(self._get_task_key(task_id, "result"), dict, require_redis=True)
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
                self._get_task_key(task_id, "result"),
            ]

            failures: list[str] = []
            for key in keys_to_delete:
                if not await self.cache_service.delete(key, require_redis=True):
                    failures.append(key)

            if failures:
                logger.error(f"任务删除失败: {task_id}, 未能删除的键: {failures}")
                return False

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


# 全局实例（用于脚本或缺少应用上下文时的后备）
async_task_service = AsyncTaskService()


def set_async_task_service(service: AsyncTaskService) -> None:
    """注册应用范围内的异步任务服务实例"""
    global async_task_service
    async_task_service = service


async def get_async_task_service(request: Request) -> AsyncTaskService:
    """FastAPI依赖：优先返回应用状态中的任务服务"""
    service = getattr(request.app.state, "async_task_service", None)
    if service is not None:
        return service
    return async_task_service
