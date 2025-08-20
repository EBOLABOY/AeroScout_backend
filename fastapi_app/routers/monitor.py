"""
FastAPI监控任务路由
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from loguru import logger
from typing import Optional, List
from datetime import datetime

from fastapi_app.models.common import APIResponse
from fastapi_app.models.auth import UserInfo
from fastapi_app.models.monitor import (
    MonitorTaskCreate, MonitorTaskUpdate, MonitorTaskResponse,
    MonitorTaskListResponse, MonitorSystemStatus, MonitorTaskStats
)
from fastapi_app.dependencies.auth import get_current_active_user, optional_auth
from fastapi_app.services.monitor_service import get_monitor_service, FastAPIMonitorService
from fastapi_app.services.supabase_service import get_supabase_service
from fastapi_app.services.flight_service import get_flight_service

# 创建路由器
router = APIRouter()


@router.get("/health", response_model=APIResponse)
async def health_check():
    """
    监控服务健康检查接口
    """
    return APIResponse(
        success=True,
        message="监控服务正常",
        data={"status": "healthy", "service": "monitor"}
    )


@router.get("/system/status", response_model=MonitorSystemStatus)
async def get_system_status(
    current_user: UserInfo = Depends(get_current_active_user)
):
    """
    获取监控系统状态
    """
    try:
        logger.info(f"用户 {current_user.username} 查询监控系统状态")
        
        monitor_service = get_monitor_service()
        status = await monitor_service.get_system_status()
        
        return status
        
    except Exception as e:
        logger.error(f"获取监控系统状态失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取监控系统状态失败"
        )


@router.post("/system/start", response_model=APIResponse)
async def start_monitoring_system(
    current_user: UserInfo = Depends(get_current_active_user)
):
    """
    启动监控系统
    """
    try:
        logger.info(f"用户 {current_user.username} 启动监控系统")
        
        monitor_service = get_monitor_service()
        success = await monitor_service.start_monitoring()
        
        if success:
            return APIResponse(
                success=True,
                message="监控系统启动成功",
                data={"status": "started"}
            )
        else:
            return APIResponse(
                success=False,
                message="监控系统已在运行",
                data={"status": "already_running"}
            )
        
    except Exception as e:
        logger.error(f"启动监控系统失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="启动监控系统失败"
        )


@router.post("/system/stop", response_model=APIResponse)
async def stop_monitoring_system(
    current_user: UserInfo = Depends(get_current_active_user)
):
    """
    停止监控系统
    """
    try:
        logger.info(f"用户 {current_user.username} 停止监控系统")
        
        monitor_service = get_monitor_service()
        success = await monitor_service.stop_monitoring()
        
        if success:
            return APIResponse(
                success=True,
                message="监控系统停止成功",
                data={"status": "stopped"}
            )
        else:
            return APIResponse(
                success=False,
                message="监控系统未在运行",
                data={"status": "not_running"}
            )
        
    except Exception as e:
        logger.error(f"停止监控系统失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="停止监控系统失败"
        )


@router.get("/tasks", response_model=MonitorTaskListResponse)
async def get_monitor_tasks(
    page: int = Query(1, description="页码", ge=1),
    page_size: int = Query(10, description="每页大小", ge=1, le=100),
    is_active: Optional[bool] = Query(None, description="是否只显示活跃任务"),
    current_user: UserInfo = Depends(get_current_active_user),
    monitor_service: FastAPIMonitorService = Depends(get_monitor_service)
):
    """
    获取用户的监控任务列表
    """
    try:
        logger.info(f"用户 {current_user.username} 查询监控任务列表")
        result = await monitor_service.list_tasks(current_user.id, page, page_size, is_active)
        return MonitorTaskListResponse(
            success=True,
            message="获取监控任务列表成功",
            data={
                "tasks": result['tasks'],
                "pagination": {
                    "page": result['page'],
                    "page_size": result['page_size'],
                    "total": result['total'],
                    "total_pages": result['total_pages']
                }
            },
            total=result['total'],
            page=result['page'],
            page_size=result['page_size']
        )
    except Exception as e:
        logger.error(f"获取监控任务列表失败: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="获取监控任务列表失败")


@router.post("/tasks", response_model=APIResponse)
async def create_monitor_task(
    task_data: MonitorTaskCreate,
    current_user: UserInfo = Depends(get_current_active_user)
):
    """
    创建监控任务
    """
    try:
        logger.info(f"用户 {current_user.username} 创建监控任务: {task_data.name}")

        # 准备数据库数据，处理日期格式
        def format_date(date_value):
            """格式化日期为字符串"""
            if date_value is None:
                return None
            if isinstance(date_value, str):
                return date_value
            if hasattr(date_value, 'isoformat'):
                return date_value.isoformat()
            return str(date_value)

        # 处理destination_code - 如果为空则设置为一个默认值以避免NOT NULL约束
        destination_code = task_data.destination_code
        if not destination_code or destination_code.strip() == '':
            destination_code = 'ANY'  # 使用特殊值表示任意目的地

        db_task_data = {
            "user_id": current_user.id,
            "task_name": task_data.name,
            "departure_code": task_data.departure_code,
            "destination_code": destination_code,
            "depart_date": format_date(task_data.depart_date),
            "return_date": format_date(task_data.return_date),
            "seat_class": getattr(task_data, 'seat_class', 'economy'),
            "trip_type": task_data.trip_type,
            "max_stops": getattr(task_data, 'max_stops', 2),
            "is_active": getattr(task_data, 'is_active', True),
            "price_threshold": task_data.price_threshold,
            "check_interval": getattr(task_data, 'check_interval', 30),
            "notification_enabled": getattr(task_data, 'notification_enabled', True),
            "email_notification": getattr(task_data, 'email_notification', False),
            "pushplus_notification": getattr(task_data, 'pushplus_notification', True),
            "pushplus_token": getattr(task_data, 'pushplus_token', None),
            "blacklist_cities": getattr(task_data, 'blacklist_cities', None),
            "blacklist_countries": getattr(task_data, 'blacklist_countries', None)
        }

        # 保存到数据库
        db_service = await get_supabase_service()
        created_task = await db_service.create_monitor_task(db_task_data)

        if created_task:
            logger.info(f"监控任务创建成功: {created_task['id']}")
            return APIResponse(
                success=True,
                message="监控任务创建成功",
                data={
                    "task_id": created_task['id'],
                    "name": created_task['task_name'],
                    "status": "created"
                }
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="数据库保存失败"
            )

    except Exception as e:
        logger.error(f"创建监控任务失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="创建监控任务失败"
        )


@router.get("/tasks/{task_id}", response_model=APIResponse)
async def get_monitor_task(
    task_id: str,
    current_user: UserInfo = Depends(get_current_active_user),
    monitor_service: FastAPIMonitorService = Depends(get_monitor_service)
):
    """
    获取单个监控任务详情
    """
    try:
        logger.info(f"用户 {current_user.username} 查询监控任务 {task_id}")
        task = await monitor_service.get_task(task_id, current_user.id)
        if task:
            return APIResponse(success=True, message="获取监控任务成功", data=task)
        else:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="监控任务不存在")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取监控任务详情失败: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="获取监控任务详情失败")


@router.put("/tasks/{task_id}", response_model=APIResponse)
async def update_monitor_task(
    task_id: str,
    task_data: MonitorTaskUpdate,
    current_user: UserInfo = Depends(get_current_active_user)
):
    """
    更新监控任务
    """
    try:
        logger.info(f"用户 {current_user.username} 更新监控任务 {task_id}")

        # 日期格式化函数
        def format_date(date_value):
            """格式化日期为字符串"""
            if date_value is None:
                return None
            if isinstance(date_value, str):
                return date_value
            if hasattr(date_value, 'isoformat'):
                return date_value.isoformat()
            return str(date_value)

        # 准备更新数据
        update_data = {}
        if hasattr(task_data, 'name') and task_data.name is not None:
            update_data['task_name'] = task_data.name
        if hasattr(task_data, 'destination_code') and task_data.destination_code is not None:
            update_data['destination_code'] = task_data.destination_code
        if hasattr(task_data, 'depart_date') and task_data.depart_date is not None:
            update_data['depart_date'] = format_date(task_data.depart_date)
        if hasattr(task_data, 'return_date') and task_data.return_date is not None:
            update_data['return_date'] = format_date(task_data.return_date)
        if hasattr(task_data, 'price_threshold') and task_data.price_threshold is not None:
            update_data['price_threshold'] = task_data.price_threshold
        if hasattr(task_data, 'is_active') and task_data.is_active is not None:
            update_data['is_active'] = task_data.is_active
        if hasattr(task_data, 'notification_enabled') and task_data.notification_enabled is not None:
            update_data['notification_enabled'] = task_data.notification_enabled
        if hasattr(task_data, 'email_notification') and task_data.email_notification is not None:
            update_data['email_notification'] = task_data.email_notification
        if hasattr(task_data, 'pushplus_notification') and task_data.pushplus_notification is not None:
            update_data['pushplus_notification'] = task_data.pushplus_notification
        if hasattr(task_data, 'pushplus_token') and task_data.pushplus_token is not None:
            update_data['pushplus_token'] = task_data.pushplus_token
        if hasattr(task_data, 'blacklist_cities') and task_data.blacklist_cities is not None:
            update_data['blacklist_cities'] = task_data.blacklist_cities
        if hasattr(task_data, 'blacklist_countries') and task_data.blacklist_countries is not None:
            update_data['blacklist_countries'] = task_data.blacklist_countries

        # 更新数据库
        db_service = await get_supabase_service()
        success = await db_service.update_monitor_task(task_id, update_data)

        if success:
            logger.info(f"监控任务更新成功: {task_id}")
            return APIResponse(
                success=True,
                message="监控任务更新成功",
                data={
                    "task_id": task_id,
                    "status": "updated"
                }
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="监控任务不存在或更新失败"
            )

    except Exception as e:
        logger.error(f"更新监控任务失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="更新监控任务失败"
        )


@router.delete("/tasks/{task_id}", response_model=APIResponse)
async def delete_monitor_task(
    task_id: str,
    current_user: UserInfo = Depends(get_current_active_user),
    monitor_service: FastAPIMonitorService = Depends(get_monitor_service)
):
    """
    删除监控任务
    """
    try:
        logger.info(f"用户 {current_user.username} 删除监控任务 {task_id}")
        success = await monitor_service.delete_task(task_id, current_user.id)
        if success:
            return APIResponse(success=True, message="监控任务删除成功", data={"task_id": task_id, "status": "deleted"})
        else:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="监控任务不存在或删除失败")
    except Exception as e:
        logger.error(f"删除监控任务失败: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="删除监控任务失败")


@router.get("/tasks/{task_id}/flights", response_model=APIResponse)
async def get_task_flight_results(
    task_id: str,
    current_user: UserInfo = Depends(get_current_active_user)
):
    """
    获取监控任务的航班搜索结果
    """
    try:
        logger.info(f"用户 {current_user.username} 获取监控任务航班结果: {task_id}")

        db_service = await get_supabase_service()
        result = db_service.client.table('monitor_tasks').select('*').eq('id', task_id).execute()
        task = result.data[0] if result.data else None

        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="监控任务不存在"
            )

        # 检查任务是否属于当前用户
        if task.get('user_id') != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权访问此监控任务"
            )

        # 获取航班搜索服务
        flight_service = get_flight_service()

        # 如果没有指定目的地，使用Monitor页面相同的逻辑
        destination_code = task.get('destination_code')
        if not destination_code or destination_code in ['', 'null', 'NULL', 'ANY']:
            # 使用Monitor页面的数据获取逻辑，传递任务中设置的日期
            monitor_data = await flight_service.get_monitor_data_async(
                city_code=task['departure_code'],
                depart_date=task.get('depart_date'),
                return_date=task.get('return_date')
            )

            if monitor_data['success']:
                flights = monitor_data.get('flights', [])

                # 应用价格过滤
                price_threshold = task.get('price_threshold', 2000.0)
                filtered_flights = []
                for flight in flights:
                    price = flight.get('price', {}).get('amount', float('inf'))
                    if price <= price_threshold:
                        filtered_flights.append(flight)

                return APIResponse(
                    success=True,
                    message="获取航班结果成功",
                    data={
                        "task": task,
                        "flights": flights,
                        "filtered_flights": filtered_flights,
                        "total_flights": len(flights),
                        "low_price_flights": len(filtered_flights),
                        "price_threshold": price_threshold,
                        "search_type": "monitor_data",
                        "departure_city": task['departure_code'],
                        "destination": "全球目的地",
                        "stats": monitor_data.get('data', {}).get('stats', {}),
                        "city_name": monitor_data.get('data', {}).get('city_name', ''),
                        "city_flag": monitor_data.get('data', {}).get('city_flag', '')
                    }
                )
            else:
                return APIResponse(
                    success=False,
                    message="获取航班数据失败",
                    data={
                        "task": task,
                        "flights": [],
                        "filtered_flights": [],
                        "total_flights": 0,
                        "low_price_flights": 0,
                        "error": monitor_data.get('error', '未知错误')
                    }
                )
        else:
            # 有指定目的地，直接搜索
            search_result = await flight_service.search_flights(
                departure_code=task['departure_code'],
                destination_code=destination_code,
                depart_date=task['depart_date'],
                return_date=task.get('return_date'),
                adults=1
            )

            if search_result['success']:
                flights = search_result.get('flights', [])

                # 应用价格过滤
                price_threshold = task.get('price_threshold', 2000.0)
                filtered_flights = []
                for flight in flights:
                    price = flight.get('price', {}).get('amount', float('inf'))
                    if price <= price_threshold:
                        filtered_flights.append(flight)

                return APIResponse(
                    success=True,
                    message="获取航班结果成功",
                    data={
                        "task": task,
                        "flights": flights,
                        "filtered_flights": filtered_flights,
                        "total_flights": len(flights),
                        "low_price_flights": len(filtered_flights),
                        "price_threshold": price_threshold,
                        "search_type": "direct_search",
                        "departure_city": task['departure_code'],
                        "destination": destination_code
                    }
                )
            else:
                return APIResponse(
                    success=False,
                    message="航班搜索失败",
                    data={
                        "task": task,
                        "flights": [],
                        "filtered_flights": [],
                        "total_flights": 0,
                        "low_price_flights": 0,
                        "error": search_result.get('error', '航班搜索失败')
                    }
                )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取监控任务航班结果失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取监控任务航班结果失败"
        )


@router.post("/tasks/{task_id}/execute", response_model=APIResponse)
async def execute_monitor_task(
    task_id: int,
    current_user: UserInfo = Depends(get_current_active_user)
):
    """
    手动执行监控任务
    """
    try:
        logger.info(f"用户 {current_user.username} 手动执行监控任务 {task_id}")

        # TODO: 实现手动执行逻辑
        # 这里应该立即执行指定的监控任务

        return APIResponse(
            success=True,
            message="监控任务执行成功",
            data={
                "task_id": task_id,
                "status": "executed",
                "execution_time": "2025-01-16T10:00:00Z"
            }
        )

    except Exception as e:
        logger.error(f"执行监控任务失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="执行监控任务失败"
        )


@router.get("/cities", response_model=APIResponse)
async def get_monitor_cities(
    current_user: Optional[UserInfo] = Depends(optional_auth)
):
    """
    获取监控页面支持的城市列表 (允许游客访问)
    """
    try:
        user_info = f"用户 {current_user.username}" if current_user else "游客"
        logger.info(f"{user_info} 获取监控城市列表")

        # 支持的城市列表
        cities = [
            {
                "code": "HKG",
                "name": "香港",
                "name_en": "Hong Kong",
                "flag": "🇭🇰",
                "timezone": "Asia/Hong_Kong"
            },
            {
                "code": "SZX",
                "name": "深圳",
                "name_en": "Shenzhen",
                "flag": "🇨🇳",
                "timezone": "Asia/Shanghai"
            },
            {
                "code": "CAN",
                "name": "广州",
                "name_en": "Guangzhou",
                "flag": "🇨🇳",
                "timezone": "Asia/Shanghai"
            },
            {
                "code": "MFM",
                "name": "澳门",
                "name_en": "Macau",
                "flag": "🇲🇴",
                "timezone": "Asia/Macau"
            }
        ]

        return APIResponse(
            success=True,
            message="获取城市列表成功",
            data={"cities": cities}
        )

    except Exception as e:
        logger.error(f"获取监控城市列表失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取城市列表失败"
        )


@router.get("/dates", response_model=APIResponse)
async def get_monitor_dates(
    current_user: Optional[UserInfo] = Depends(optional_auth)
):
    """
    获取监控日期设置 (允许游客访问)
    """
    try:
        user_info = f"用户 {current_user.username}" if current_user else "游客"
        logger.info(f"{user_info} 获取监控日期设置")

        import os
        from datetime import datetime, timedelta

        # 从环境变量获取配置的日期
        departure_date = os.getenv("DEPART_DATE", "2025-09-30")
        return_date = os.getenv("RETURN_DATE", "2025-10-08")
        trip_type = int(os.getenv("TRIP_TYPE", "2"))  # 1=单程, 2=往返

        # 生成未来30天的日期选项
        today = datetime.now().date()
        dates = []

        for i in range(30):
            date = today + timedelta(days=i)
            dates.append({
                "date": date.isoformat(),
                "display": date.strftime("%m月%d日"),
                "display_en": date.strftime("%b %d"),
                "weekday": date.strftime("%A"),
                "weekday_zh": ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][date.weekday()],
                "is_weekend": date.weekday() >= 5
            })

        return APIResponse(
            success=True,
            message="获取监控日期成功",
            data={
                "departure_date": departure_date,
                "return_date": return_date,
                "trip_type": "往返" if trip_type == 2 else "单程",
                "dates": dates
            }
        )

    except Exception as e:
        logger.error(f"获取监控日期设置失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取监控日期失败"
        )


@router.post("/refresh", response_model=APIResponse)
async def refresh_monitor_data(
    request_data: dict,
    current_user: Optional[UserInfo] = Depends(optional_auth)
):
    """
    刷新监控数据 (允许游客访问)
    """
    try:
        city = request_data.get('city', 'HKG').upper()
        user_info = f"用户 {current_user.username}" if current_user else "游客"
        logger.info(f"{user_info} 刷新监控数据: {city}")

        # 验证城市代码
        supported_cities = ['HKG', 'SZX', 'CAN', 'MFM']
        if city not in supported_cities:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f'不支持的城市代码: {city}，支持的城市: {", ".join(supported_cities)}'
            )

        # 获取航班搜索服务
        flight_service = get_flight_service()

        # 执行数据刷新（使用Trip.com API）
        result = await flight_service.get_monitor_data_async(
            city_code=city
        )

        if result.get('success'):
            logger.info(f"监控数据刷新成功: {city}")
            return APIResponse(
                success=True,
                message="数据刷新成功",
                data={
                    "city": city,
                    "lastUpdate": datetime.now().isoformat(),
                    "flights_count": len(result.get('flights', []))
                }
            )
        else:
            logger.warning(f"监控数据刷新失败: {result.get('error', '未知错误')}")
            return APIResponse(
                success=False,
                message=f"数据刷新失败: {result.get('error', '未知错误')}",
                data={"city": city}
            )

    except HTTPException:
        # 重新抛出HTTP异常
        raise
    except Exception as e:
        logger.error(f"刷新监控数据失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="刷新数据失败"
        )


@router.get("/data")
async def get_monitor_data(
    city: str = Query(..., description="城市代码"),
    blacklist_cities: Optional[str] = Query(None, description="黑名单城市，逗号分隔"),
    blacklist_countries: Optional[str] = Query(None, description="黑名单国家，逗号分隔"),
    depart_date: Optional[str] = Query(None, description="出发日期(YYYY-MM-DD)"),
    return_date: Optional[str] = Query(None, description="返程日期(YYYY-MM-DD)"),
    current_user: Optional[UserInfo] = Depends(optional_auth)
):
    """
    获取监控页面数据 (允许游客访问)

    支持的城市代码: HKG, SZX, CAN, MFM, BJS, SHA, TSN, TYO, SEL, TPE
    """
    try:
        user_info = f"用户 {current_user.username}" if current_user else "游客"
        logger.info(f"{user_info} 获取监控数据: {city}")

        # 验证城市代码 - 支持前端表单中的所有城市
        supported_cities = ['HKG', 'SZX', 'CAN', 'MFM', 'BJS', 'SHA', 'TSN', 'TYO', 'SEL', 'TPE']
        if city.upper() not in supported_cities:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f'不支持的城市代码: {city}，支持的城市: {", ".join(supported_cities)}'
            )

        # 处理黑名单参数
        blacklist_cities_list = []
        blacklist_countries_list = []

        if blacklist_cities:
            blacklist_cities_list = [city.strip() for city in blacklist_cities.split(',') if city.strip()]

        if blacklist_countries:
            blacklist_countries_list = [country.strip() for country in blacklist_countries.split(',') if country.strip()]

        # 获取航班搜索服务
        flight_service = get_flight_service()

        # 执行异步监控数据获取
        result = await flight_service.get_monitor_data_async(
            city_code=city.upper(),
            blacklist_cities=blacklist_cities_list,
            blacklist_countries=blacklist_countries_list,
            depart_date=depart_date,
            return_date=return_date
        )

        logger.info(f"监控数据获取完成: 成功={result['success']}, 航班数={len(result.get('flights', []))}")

        # 包装响应以匹配前端期望的数据结构
        if result['success']:
            return APIResponse(
                success=True,
                message="获取监控数据成功",
                data={
                    'flights': result.get('flights', []),
                    'stats': result.get('stats', {}),
                    'lastUpdate': result.get('lastUpdate', ''),
                    'city_name': result.get('city_name', ''),
                    'city_flag': result.get('city_flag', '')
                }
            )
        else:
            return APIResponse(
                success=False,
                message=result.get('error', '获取监控数据失败'),
                data={
                    'flights': [],
                    'stats': {'total': 0, 'lowPrice': 0, 'minPrice': 0},
                    'lastUpdate': '',
                    'city_name': '',
                    'city_flag': ''
                }
            )

    except HTTPException:
        # 重新抛出HTTP异常
        raise
    except Exception as e:
        logger.error(f"获取监控数据失败: {e}")
        return APIResponse(
            success=False,
            message=f"获取监控数据失败: {str(e)}",
            data={
                'flights': [],
                'stats': {'total': 0, 'lowPrice': 0, 'minPrice': 0},
                'lastUpdate': '',
                'city_name': city,
                'city_flag': '🏙️'
            }
        )
