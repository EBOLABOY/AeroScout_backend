"""
FastAPI版本的监控任务服务
基于原有MonitorTaskManager，优化为纯异步实现
"""
import asyncio
import os
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional, Any
from loguru import logger

from fastapi_app.models.monitor import (
    MonitorTaskCreate, MonitorTaskUpdate, MonitorTaskResponse,
    MonitorTaskExecutionResult, MonitorSystemStatus
)
from fastapi_app.services.flight_service import get_flight_service
from fastapi_app.services.notification_service import get_notification_service
from fastapi_app.services.supabase_service import get_supabase_service


class FastAPIMonitorService:
    """FastAPI版本的监控任务服务"""
    
    def __init__(self):
        """初始化监控服务"""
        self.flight_service = get_flight_service()
        self.notification_service = get_notification_service()
        self.db_service = None  # 将在异步方法中初始化
        self.running = False
        self.monitor_task = None
        self.fixed_crawl_task = None  # 新增：固定爬取任务
        self.fixed_crawl_running = False  # 新增：固定爬取运行状态
        self.stats = {
            'total_executions': 0,
            'successful_executions': 0,
            'failed_executions': 0,
            'start_time': None,
            'last_execution': None
        }
        # 固定爬取的城市列表
        self.fixed_cities = ['HKG', 'SZX', 'CAN', 'MFM']
        logger.info("FastAPIMonitorService初始化成功")

    async def get_db_service(self):
        """获取数据库服务"""
        if self.db_service is None:
            self.db_service = await get_supabase_service()
        return self.db_service

    async def start_monitoring(self) -> bool:
        """启动监控系统"""
        if self.running:
            logger.warning("监控系统已在运行")
            return False

        self.running = True
        self.stats['start_time'] = datetime.now(timezone.utc)

        # 启动异步监控任务
        self.monitor_task = asyncio.create_task(self._monitoring_loop())

        # 启动固定城市爬取任务
        self.fixed_crawl_running = True
        self.fixed_crawl_task = asyncio.create_task(self._fixed_crawl_loop())

        logger.info("异步监控系统和固定城市爬取已启动")
        return True
    
    async def stop_monitoring(self) -> bool:
        """停止监控系统"""
        if not self.running:
            logger.warning("监控系统未在运行")
            return False

        self.running = False
        self.fixed_crawl_running = False

        if self.monitor_task:
            self.monitor_task.cancel()
            try:
                await self.monitor_task
            except asyncio.CancelledError:
                pass

        if self.fixed_crawl_task:
            self.fixed_crawl_task.cancel()
            try:
                await self.fixed_crawl_task
            except asyncio.CancelledError:
                pass

        logger.info("异步监控系统和固定城市爬取已停止")
        return True
    
    async def _monitoring_loop(self):
        """异步监控循环"""
        while self.running:
            try:
                await self._run_monitoring_cycle()
                # 等待下一个监控周期（默认30分钟）
                await asyncio.sleep(30 * 60)
            except asyncio.CancelledError:
                logger.info("监控循环被取消")
                break
            except Exception as e:
                logger.error(f"监控循环出错: {e}")
                await asyncio.sleep(60)  # 出错后等待1分钟再重试
    
    async def _run_monitoring_cycle(self):
        """运行一个监控周期"""
        try:
            logger.info("开始监控周期...")
            self.stats['total_executions'] += 1
            self.stats['last_execution'] = datetime.now(timezone.utc)
            
            # 获取所有活跃的监控任务
            active_tasks = await self._get_active_monitor_tasks()
            logger.info(f"找到 {len(active_tasks)} 个活跃监控任务")
            
            # 并发执行监控任务
            tasks = []
            for task in active_tasks:
                tasks.append(self._execute_monitor_task(task))
            
            if tasks:
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # 统计执行结果
                successful = sum(1 for r in results if isinstance(r, dict) and r.get('success', False))
                failed = len(results) - successful
                
                self.stats['successful_executions'] += successful
                self.stats['failed_executions'] += failed
                
                logger.info(f"监控周期完成: 成功={successful}, 失败={failed}")
            else:
                logger.info("没有活跃的监控任务")
                
        except Exception as e:
            logger.error(f"监控周期执行失败: {e}")
            self.stats['failed_executions'] += 1
    
    async def _get_active_monitor_tasks(self) -> List[Dict[str, Any]]:
        """获取所有活跃的监控任务"""
        try:
            # 使用异步数据库服务获取活跃的监控任务
            db_service = await self.get_db_service()
            tasks = await db_service.get_user_monitor_tasks(user_id=None, is_active=True)
            logger.info(f"获取到 {len(tasks)} 个活跃监控任务")
            return tasks

        except Exception as e:
            logger.error(f"获取活跃监控任务失败: {e}")
            return []
    
    async def _execute_monitor_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """执行单个监控任务"""
        start_time = datetime.now(timezone.utc)
        task_id = task.get('id', 0)
        
        try:
            logger.info(f"执行监控任务 {task_id}: {task.get('name', 'Unknown')}")
            
            # 检查是否需要发送通知（避免重复通知）
            if task.get('last_notification'):
                last_notification = datetime.fromisoformat(task['last_notification'])
                cooldown = timedelta(hours=int(os.environ.get('NOTIFICATION_COOLDOWN', '24')))
                if (start_time - last_notification) < cooldown:
                    logger.info(f"任务 {task_id} 在冷却期内，跳过通知")
                    return {'success': True, 'skipped': True, 'reason': 'cooldown'}
            
            # 执行航班搜索
            # 如果没有指定目的地，搜索热门目的地
            destination_code = task.get('destination_code')
            logger.info(f"任务目的地代码: '{destination_code}' (类型: {type(destination_code)})")

            # 在监控任务执行时，清除相关城市的缓存以获取最新数据
            departure_code = task['departure_code']
            await self.flight_service.clear_flight_cache(departure_code)
            logger.info(f"已清除城市 {departure_code} 的缓存，确保获取最新数据")

            if not destination_code or destination_code in ['', 'null', 'NULL', 'ANY']:
                logger.info(f"任务 {task_id} 没有指定目的地，使用监控数据API获取所有航班")
                # 无指定目的地，使用监控数据API获取所有可用航班
                monitor_result = await self.flight_service.get_monitor_data_async(
                    city_code=task['departure_code']
                )

                if monitor_result['success']:
                    # 修复数据格式问题：直接使用 flights 键
                    all_flights = monitor_result.get('flights', [])
                    logger.info(f"任务 {task_id} 从监控数据获取到 {len(all_flights)} 个航班")
                    search_result = {
                        'success': True,
                        'flights': all_flights
                    }
                else:
                    logger.warning(f"获取监控数据失败: {monitor_result.get('error', 'Unknown error')}")
                    search_result = {
                        'success': False,
                        'flights': []
                    }
            else:
                logger.info(f"任务 {task_id} 有指定目的地 {destination_code}，使用监控数据API搜索")
                # 有指定目的地，使用监控数据API（类似仪表板）
                monitor_result = await self.flight_service.get_monitor_data_async(
                    city_code=task['departure_code']
                )

                if monitor_result['success']:
                    # 修复数据格式问题：直接使用 flights 键
                    all_flights = monitor_result.get('flights', [])
                    filtered_flights = [
                        flight for flight in all_flights
                        if (flight.get('代码') == destination_code or
                            flight.get('destination_code') == destination_code or
                            flight.get('code') == destination_code)
                    ]

                    logger.info(f"从 {len(all_flights)} 个航班中过滤出 {len(filtered_flights)} 个目标航班")
                    search_result = {
                        'success': True,
                        'flights': filtered_flights
                    }
                else:
                    logger.warning(f"获取监控数据失败: {monitor_result.get('error', 'Unknown error')}")
                    search_result = {
                        'success': False,
                        'flights': []
                    }
            
            if not search_result['success']:
                logger.warning(f"任务 {task_id} 航班搜索失败: {search_result.get('error', 'Unknown error')}")
                return {
                    'success': False,
                    'task_id': task_id,
                    'error': search_result.get('error', 'Flight search failed'),
                    'execution_duration': (datetime.now(timezone.utc) - start_time).total_seconds()
                }
            
            # 过滤低于阈值的机票
            flights = search_result.get('flights', [])
            price_threshold = task.get('price_threshold', 1000.0)

            low_price_flights = []
            for flight in flights:
                # Trip.com API返回的价格格式处理
                price = self._extract_flight_price(flight)
                if price <= price_threshold:
                    low_price_flights.append(flight)
            
            logger.info(f"任务 {task_id} 找到 {len(flights)} 个航班，其中 {len(low_price_flights)} 个低价航班")
            
            # 如果有低价航班且启用通知，发送通知
            notification_sent = False
            if low_price_flights and task.get('notification_enabled', True):
                notification_sent = await self._send_notification(task, low_price_flights)
            
            # 更新任务统计信息
            await self._update_task_stats(task_id, True, len(flights), len(low_price_flights), notification_sent)
            
            execution_duration = (datetime.now(timezone.utc) - start_time).total_seconds()
            
            return {
                'success': True,
                'task_id': task_id,
                'flights_found': len(flights),
                'low_price_flights': len(low_price_flights),
                'notification_sent': notification_sent,
                'execution_duration': execution_duration
            }
            
        except Exception as e:
            logger.error(f"执行监控任务 {task_id} 失败: {e}")
            execution_duration = (datetime.now(timezone.utc) - start_time).total_seconds()
            
            # 更新任务统计信息
            await self._update_task_stats(task_id, False, 0, 0, False)
            
            return {
                'success': False,
                'task_id': task_id,
                'error': str(e),
                'execution_duration': execution_duration
            }
    
    async def _send_notification(self, task: Dict[str, Any], low_price_flights: List[Dict[str, Any]]) -> bool:
        """发送通知"""
        try:
            logger.info(f"发送通知给任务 {task.get('id', 0)}: {len(low_price_flights)} 个低价航班")

            # 构建用户数据
            user_data = {
                'username': task.get('user_name', 'Unknown'),
                'email': task.get('user_email'),
                'email_notifications_enabled': task.get('email_notification', False),
                'email_verified': task.get('user_email_verified', False),
                'pushplus_token': task.get('pushplus_token'),
                'notification_enabled': task.get('notification_enabled', True)
            }

            # 构建航班数据
            flight_data = {
                'route': f"{task.get('departure_city', '')}→{task.get('destination_city', '所有目的地')}",
                'departure_city': task.get('departure_city', ''),
                'trip_type': '往返' if task.get('return_date') else '单程',
                'depart_date': task.get('depart_date', ''),
                'return_date': task.get('return_date', ''),
                'flights': low_price_flights
            }

            # 发送通知
            result = await self.notification_service.send_flight_notification(user_data, flight_data)

            success = result.get('total_sent', 0) > 0
            if success:
                logger.info(f"通知发送成功: {result}")
            else:
                logger.warning(f"通知发送失败: {result}")

            return success

        except Exception as e:
            logger.error(f"发送通知失败: {e}")
            return False

    def _extract_flight_price(self, flight: Dict[str, Any]) -> float:
        """从航班数据中提取价格
        TODO: 抽取到统一的工具函数（例如 utils/price.py），与 AI 服务中的价格过滤逻辑共用，减少重复。
        """
        try:
            # 1. Trip.com格式 - 中文字段
            if '价格' in flight and flight['价格'] is not None:
                return float(flight['价格'])

            # 2. Trip.com格式 - 英文字段
            if 'price' in flight and flight['price'] is not None:
                if isinstance(flight['price'], dict):
                    # smart-flights格式
                    return float(flight['price'].get('amount', float('inf')))
                else:
                    # 直接数值
                    return float(flight['price'])

            # 3. 其他可能的价格字段
            for price_field in ['Price', 'amount', 'cost']:
                if price_field in flight and flight[price_field] is not None:
                    try:
                        price_value = flight[price_field]
                        if isinstance(price_value, str):
                            # 提取数字部分
                            import re
                            numbers = re.findall(r'\d+\.?\d*', price_value)
                            if numbers:
                                return float(numbers[0])
                        elif isinstance(price_value, (int, float)):
                            return float(price_value)
                    except (ValueError, TypeError):
                        continue

            logger.warning(f"无法提取航班价格，可用字段: {list(flight.keys())}")
            return float('inf')

        except Exception as e:
            logger.error(f"提取航班价格失败: {e}")
            return float('inf')
    
    async def _update_task_stats(
        self,
        task_id: int,
        success: bool,
        flights_found: int,
        low_price_flights: int,
        notification_sent: bool
    ):
        """更新任务统计信息"""
        try:
            # 更新数据库中的任务统计信息
            current_time = datetime.now(timezone.utc)

            # 获取当前任务信息以更新计数器
            task = await self.db_service.get_monitor_task_by_id(task_id)
            if task:
                new_total_checks = task.get('total_checks', 0) + 1
                new_total_notifications = task.get('total_notifications', 0)

                if notification_sent:
                    new_total_notifications += 1

                # 更新统计信息
                await self.db_service.update_task_stats(
                    task_id=task_id,
                    last_check=current_time,
                    total_checks=new_total_checks,
                    last_notification=current_time if notification_sent else None,
                    total_notifications=new_total_notifications
                )

                logger.debug(f"更新任务 {task_id} 统计信息: 成功={success}, 航班={flights_found}, 低价={low_price_flights}, 通知={notification_sent}")

        except Exception as e:
            logger.error(f"更新任务统计信息失败: {e}")
    
    async def get_system_status(self) -> MonitorSystemStatus:
        """获取监控系统状态"""
        try:
            db_service = await self.get_db_service()
            stats = await db_service.get_monitor_stats()
            total_tasks = stats.get('total_tasks', 0)
            active_tasks = stats.get('active_tasks', 0)

            next_execution = None
            if self.running and self.stats['last_execution']:
                next_execution = self.stats['last_execution'] + timedelta(minutes=30)

            return MonitorSystemStatus(
                is_running=self.running,
                start_time=self.stats['start_time'],
                total_tasks=total_tasks,
                active_tasks=active_tasks,
                last_execution=self.stats['last_execution'],
                next_execution=next_execution,
                execution_interval=30,
                total_executions=self.stats['total_executions'],
                successful_executions=self.stats['successful_executions'],
                failed_executions=self.stats['failed_executions']
            )
        except Exception as e:
            logger.error(f"获取系统状态失败: {e}")
            raise

    async def list_tasks(self, user_id: str, page: int, page_size: int, is_active: Optional[bool]) -> Dict[str, Any]:
        """获取用户的监控任务列表"""
        db_service = await self.get_db_service()

        # 获取所有任务
        all_tasks = await db_service.get_user_monitor_tasks(user_id, is_active)

        # 手动实现分页
        total = len(all_tasks)
        start_index = (page - 1) * page_size
        end_index = start_index + page_size
        tasks = all_tasks[start_index:end_index]

        total_pages = (total + page_size - 1) // page_size

        return {
            'tasks': tasks,
            'total': total,
            'page': page,
            'page_size': page_size,
            'total_pages': total_pages
        }

    async def get_task(self, task_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """获取单个监控任务"""
        db_service = await self.get_db_service()
        task = await db_service.get_monitor_task_by_id(task_id)
        if task and task.get('user_id') == user_id:
            return task
        return None

    async def delete_task(self, task_id: str, user_id: str) -> bool:
        """删除监控任务"""
        db_service = await self.get_db_service()
        task = await db_service.get_monitor_task_by_id(task_id)
        if task and task.get('user_id') == user_id:
            return await db_service.delete_monitor_task(task_id)
        return False

    async def _fixed_crawl_loop(self):
        """固定城市爬取循环"""
        logger.info("固定城市爬取循环已启动")

        while self.fixed_crawl_running:
            try:
                await self._run_fixed_crawl_cycle()
                # 等待下一个爬取周期（默认30分钟）
                await asyncio.sleep(30 * 60)
            except asyncio.CancelledError:
                logger.info("固定城市爬取循环被取消")
                break
            except Exception as e:
                logger.error(f"固定城市爬取循环出错: {e}")
                await asyncio.sleep(60)  # 出错后等待1分钟再重试

    async def _run_fixed_crawl_cycle(self):
        """运行一个固定城市爬取周期"""
        try:
            logger.info("开始固定城市爬取周期...")

            # 分阶段爬取4个城市的数据
            for i, city_code in enumerate(self.fixed_cities):
                try:
                    logger.info(f"正在爬取城市 {city_code} ({i+1}/{len(self.fixed_cities)})")

                    # 调用航班服务获取监控数据
                    result = await self.flight_service.get_monitor_data_async(
                        city_code=city_code
                    )

                    if result.get('success'):
                        flights_count = len(result.get('flights', []))
                        logger.info(f"城市 {city_code} 爬取成功，获得 {flights_count} 个航班")
                    else:
                        logger.warning(f"城市 {city_code} 爬取失败: {result.get('error', '未知错误')}")

                    # 城市间间隔5秒，避免请求过于频繁
                    if i < len(self.fixed_cities) - 1:
                        await asyncio.sleep(5)

                except Exception as e:
                    logger.error(f"爬取城市 {city_code} 时出错: {e}")
                    continue

            logger.info("固定城市爬取周期完成")

        except Exception as e:
            logger.error(f"固定城市爬取周期执行失败: {e}")


# 全局服务实例
_monitor_service: Optional[FastAPIMonitorService] = None


def get_monitor_service() -> FastAPIMonitorService:
    """获取监控服务实例（单例模式）"""
    global _monitor_service
    if _monitor_service is None:
        _monitor_service = FastAPIMonitorService()
    return _monitor_service
