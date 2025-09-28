"""
FastAPI航班路由
"""

import asyncio
import json
import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from loguru import logger
from pydantic import BaseModel

from fastapi_app.dependencies.auth import get_current_active_user, get_current_user_optional
from fastapi_app.dependencies.quota_utils import (
    check_user_quota,
    consume_user_quota,
    require_search_quota,
)
from fastapi_app.models.auth import UserInfo
from fastapi_app.models.common import APIResponse
from fastapi_app.models.flights import (
    MaxStops,
    SeatClass,
    SortBy,
)
from fastapi_app.services.ai_flight_service import AIFlightService
from fastapi_app.services.async_task_service import (
    AsyncTaskService,
    ProcessingStage,
    StageInfo,
    TaskStatus,
    get_async_task_service,
)
from fastapi_app.services.flight_service import get_flight_service
from fastapi_app.services.quota_service import QuotaType
from fastapi_app.services.search_log_service import get_search_log_service
from fastapi_app.services.subscription_service import get_subscription_service
from fastapi_app.utils.errors import QuotaError, SearchError, UserLevelError, create_upgrade_prompt

# 创建路由器
router = APIRouter()


@router.get("/health", response_model=APIResponse)
async def health_check():
    """
    健康检查接口
    """
    return APIResponse(success=True, message="航班服务正常", data={"status": "healthy", "service": "flights"})


@router.get("/airports", response_model=APIResponse)
async def get_airports(
    query: str = Query("", description="搜索关键词"), current_user: UserInfo = Depends(get_current_active_user)
):
    """
    获取机场信息 (旧版API，保持兼容性)
    """
    return await search_airports_internal(query)


@router.get("/airports/search", response_model=APIResponse)
async def search_airports(
    q: str = Query("", description="搜索关键词"), language: str = Query("zh", description="语言设置")
):
    """
    机场搜索API (公开接口，无需认证)

    集成smart-flights的机场搜索API
    """
    try:
        logger.info(f"机场搜索: {q}, 语言: {language}")
        return await search_airports_internal(q, language)

    except Exception as e:
        logger.error(f"机场搜索失败: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="机场搜索服务异常")


@router.get("/airports/search/auth", response_model=APIResponse)
async def search_airports_authenticated(
    q: str = Query("", description="搜索关键词"),
    language: str = Query("zh", description="语言设置"),
    current_user: UserInfo = Depends(get_current_active_user),
):
    """
    机场搜索API (需要认证的版本)

    集成smart-flights的机场搜索API
    """
    try:
        logger.info(f"用户 {current_user.username} 机场搜索: {q}, 语言: {language}")
        return await search_airports_internal(q, language)

    except Exception as e:
        logger.error(f"机场搜索失败: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="机场搜索服务异常")


async def search_airports_internal(query: str, language: str = "zh"):
    """
    内部机场搜索函数
    """
    try:
        # 导入smart-flights的机场搜索API
        try:
            from fli.api.airport_search import airport_search_api
            from fli.models.google_flights.base import Language

            # 根据语言设置选择语言
            lang = Language.CHINESE if language.startswith('zh') else Language.ENGLISH

            # 使用smart-flights搜索机场
            if query:
                results = airport_search_api.search_airports(query, language=lang)
                airports = []

                for result in results:
                    # 处理字典或对象两种情况
                    if isinstance(result, dict):
                        code = result.get('code', '')
                        name = result.get('name', '')
                        city = result.get('city', result.get('name', ''))
                        country = result.get('country', '')

                        # 构建前端期望的格式
                        airport_data = {
                            "code": code,
                            "name": name,
                            "city": city,
                            "country": country,
                            "type": result.get('type', 'airport'),
                            "skyId": code,  # 添加skyId字段供航班搜索使用
                            "presentation": {"suggestionTitle": f"{name} ({code}) - {city}, {country}"},
                        }
                        airports.append(airport_data)
                    else:
                        code = getattr(result, 'code', '')
                        name = getattr(result, 'name', '')
                        city = getattr(result, 'city', '') or getattr(result, 'name', '')
                        country = getattr(result, 'country', '')

                        # 构建前端期望的格式
                        airport_data = {
                            "code": code,
                            "name": name,
                            "city": city,
                            "country": country,
                            "type": getattr(result, 'type', 'airport'),
                            "skyId": code,  # 添加skyId字段供航班搜索使用
                            "presentation": {"suggestionTitle": f"{name} ({code}) - {city}, {country}"},
                        }
                        airports.append(airport_data)

                logger.info(f"smart-flights返回 {len(airports)} 个机场")
            else:
                # 返回常用机场
                airports = [
                    {"code": "PEK", "name": "北京首都国际机场", "city": "北京", "country": "中国", "type": "airport"},
                    {"code": "PVG", "name": "上海浦东国际机场", "city": "上海", "country": "中国", "type": "airport"},
                    {"code": "CAN", "name": "广州白云国际机场", "city": "广州", "country": "中国", "type": "airport"},
                    {"code": "SZX", "name": "深圳宝安国际机场", "city": "深圳", "country": "中国", "type": "airport"},
                    {"code": "HGH", "name": "杭州萧山国际机场", "city": "杭州", "country": "中国", "type": "airport"},
                    {"code": "HKG", "name": "香港国际机场", "city": "香港", "country": "中国", "type": "airport"},
                    {
                        "code": "TPE",
                        "name": "台北桃园国际机场",
                        "city": "台北",
                        "country": "中国台湾",
                        "type": "airport",
                    },
                    {"code": "NRT", "name": "东京成田国际机场", "city": "东京", "country": "日本", "type": "airport"},
                    {"code": "ICN", "name": "首尔仁川国际机场", "city": "首尔", "country": "韩国", "type": "airport"},
                    {"code": "SIN", "name": "新加坡樟宜机场", "city": "新加坡", "country": "新加坡", "type": "airport"},
                ]

        except ImportError as e:
            logger.warning(f"smart-flights机场搜索API不可用: {e}")
            # 降级到静态数据
            static_airports = [
                {"code": "PEK", "name": "北京首都国际机场", "city": "北京", "country": "中国", "type": "airport"},
                {"code": "PVG", "name": "上海浦东国际机场", "city": "上海", "country": "中国", "type": "airport"},
                {"code": "CAN", "name": "广州白云国际机场", "city": "广州", "country": "中国", "type": "airport"},
                {"code": "SZX", "name": "深圳宝安国际机场", "city": "深圳", "country": "中国", "type": "airport"},
                {"code": "HGH", "name": "杭州萧山国际机场", "city": "杭州", "country": "中国", "type": "airport"},
            ]

            # 如果有查询参数，进行过滤
            if query:
                query_lower = query.lower()
                static_airports = [
                    airport
                    for airport in static_airports
                    if query_lower in airport["name"].lower()
                    or query_lower in airport["city"].lower()
                    or query_lower in airport["code"].lower()
                ]

            # 转换为前端期望的格式
            airports = []
            for airport in static_airports:
                code = airport["code"]
                name = airport["name"]
                city = airport["city"]
                country = airport["country"]

                airport_data = {
                    "code": code,
                    "name": name,
                    "city": city,
                    "country": country,
                    "type": airport["type"],
                    "skyId": code,  # 添加skyId字段供航班搜索使用
                    "presentation": {"suggestionTitle": f"{name} ({code}) - {city}, {country}"},
                }
                airports.append(airport_data)

        return APIResponse(success=True, message="机场搜索成功", data={"airports": airports, "total": len(airports)})

    except Exception as e:
        logger.error(f"机场搜索内部错误: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="机场搜索服务异常")


@router.get("/airports/popular", response_model=APIResponse)
async def get_popular_airports(
    language: str = Query("zh", description="语言设置"), current_user: UserInfo = Depends(get_current_active_user)
):
    """
    获取热门机场列表
    """
    try:
        logger.info(f"用户 {current_user.username} 获取热门机场列表")

        popular_airports = [
            {"code": "PEK", "name": "北京首都国际机场", "city": "北京", "country": "中国", "popular": True},
            {"code": "PVG", "name": "上海浦东国际机场", "city": "上海", "country": "中国", "popular": True},
            {"code": "CAN", "name": "广州白云国际机场", "city": "广州", "country": "中国", "popular": True},
            {"code": "SZX", "name": "深圳宝安国际机场", "city": "深圳", "country": "中国", "popular": True},
            {"code": "HKG", "name": "香港国际机场", "city": "香港", "country": "中国", "popular": True},
            {"code": "NRT", "name": "东京成田国际机场", "city": "东京", "country": "日本", "popular": True},
            {"code": "ICN", "name": "首尔仁川国际机场", "city": "首尔", "country": "韩国", "popular": True},
            {"code": "SIN", "name": "新加坡樟宜机场", "city": "新加坡", "country": "新加坡", "popular": True},
            {"code": "BKK", "name": "曼谷素万那普国际机场", "city": "曼谷", "country": "泰国", "popular": True},
            {"code": "KUL", "name": "吉隆坡国际机场", "city": "吉隆坡", "country": "马来西亚", "popular": True},
        ]

        return APIResponse(
            success=True,
            message=f"获取到 {len(popular_airports)} 个热门机场",
            data={"airports": popular_airports, "total": len(popular_airports), "language": language},
        )

    except Exception as e:
        logger.error(f"获取热门机场失败: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="获取热门机场失败")


@router.get("/search")
async def search_flights(
    departure_code: str = Query(..., description="出发机场代码", min_length=3, max_length=3),
    destination_code: str = Query(..., description="目的地机场代码", min_length=3, max_length=3),
    depart_date: str = Query(..., description="出发日期(YYYY-MM-DD)"),
    return_date: str | None = Query(None, description="返程日期(YYYY-MM-DD)"),
    adults: int = Query(1, description="成人数量", ge=1, le=9),
    children: int = Query(0, description="儿童数量", ge=0, le=8),
    infants_in_seat: int = Query(0, description="婴儿占座数量", ge=0, le=8),
    infants_on_lap: int = Query(0, description="婴儿怀抱数量", ge=0, le=8),
    seat_class: SeatClass = Query(SeatClass.ECONOMY, description="座位等级"),
    max_stops: MaxStops = Query(MaxStops.ANY, description="最大中转次数"),
    sort_by: SortBy = Query(SortBy.CHEAPEST, description="排序方式"),
    language: str = Query("zh", description="语言设置 (zh/en)"),
    currency: str = Query("CNY", description="货币设置 (CNY/USD)"),
    current_user: UserInfo = Depends(require_search_quota),  # 使用配额验证
):
    """
    基础航班搜索 - 需要消费搜索配额

    集成smart-flights库进行真实的航班搜索
    """
    search_start_time = datetime.now()
    search_log_service = await get_search_log_service()

    try:
        # 消费搜索配额并获取剩余配额信息
        await consume_user_quota(current_user, QuotaType.SEARCH, 1)

        # 获取更新后的配额状态
        from fastapi_app.dependencies.quota_utils import get_quota_status

        quota_status = await get_quota_status(current_user, QuotaType.SEARCH)

        logger.info(
            f"用户 {current_user.username} (等级: {current_user.user_level_name}) 基础搜索: {departure_code} -> {destination_code}, 剩余配额: {quota_status.get('remaining', 0)}"
        )

        # 验证必需参数
        if not all([departure_code, destination_code, depart_date]):
            raise SearchError.invalid_params({"missing_params": "缺少必需参数：出发机场代码、目的地机场代码、出发日期"})

        # 验证机场代码格式
        if len(departure_code) != 3 or len(destination_code) != 3:
            raise SearchError.invalid_params({"airport_code": "机场代码必须是3位字母"})

        # 验证出发地和目的地不能相同
        if departure_code.upper() == destination_code.upper():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='出发地和目的地不能相同')

        # 订阅与配额：限制每日搜索次数
        sub_service = await get_subscription_service()
        allowed, info = await sub_service.enforce_quota(
            current_user.id, metric="flight_searches", window="daily", increment=1
        )
        if not allowed:
            limit = info.get('limit')
            used = info.get('used')
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"今日航班搜索次数已达上限（{used}/{limit}）。请明日再试或升级套餐。",
            )

        # 获取航班搜索服务
        flight_service = get_flight_service()

        # 执行异步搜索
        result = await flight_service.search_flights(
            departure_code=departure_code.upper(),
            destination_code=destination_code.upper(),
            depart_date=depart_date,
            return_date=return_date,
            adults=adults,
            seat_class=seat_class.value,
            children=children,
            infants_in_seat=infants_in_seat,
            infants_on_lap=infants_on_lap,
            max_stops=max_stops.value,
            sort_by=sort_by.value,
            language=language,
            currency=currency,
        )

        # 计算搜索耗时
        search_duration = (datetime.now() - search_start_time).total_seconds()
        results_count = result.get('total_count', 0) if isinstance(result, dict) else 0

        logger.info(f"航班搜索完成: 成功={result['success']}, 结果数={results_count}, 耗时={search_duration:.2f}s")

        # 记录搜索日志
        await search_log_service.log_search(
            user_id=current_user.id,
            search_type="basic",
            departure_city=departure_code.upper(),
            arrival_city=destination_code.upper(),
            departure_date=depart_date,
            return_date=return_date,
            passenger_count=adults + children + infants_in_seat + infants_on_lap,
            results_count=results_count,
            search_duration=search_duration,
            success=result.get('success', False),
            search_params={
                'seat_class': seat_class.value,
                'max_stops': max_stops.value,
                'sort_by': sort_by.value,
                'language': language,
                'currency': currency,
            },
        )

        # 在返回结果中添加配额信息
        if isinstance(result, dict):
            result['quota_info'] = {
                'search_quota': quota_status,
                'user_level': current_user.user_level_name,
                'remaining_searches': quota_status.get('remaining', 0),
            }

        return result

    except HTTPException:
        # 记录失败的搜索日志
        search_duration = (datetime.now() - search_start_time).total_seconds()
        await search_log_service.log_search(
            user_id=current_user.id,
            search_type="basic",
            departure_city=departure_code.upper(),
            arrival_city=destination_code.upper(),
            departure_date=depart_date,
            return_date=return_date,
            passenger_count=adults + children + infants_in_seat + infants_on_lap,
            results_count=0,
            search_duration=search_duration,
            success=False,
            error_message="参数验证失败或其他HTTP错误",
        )
        # 重新抛出HTTP异常
        raise
    except Exception as e:
        # 记录失败的搜索日志
        search_duration = (datetime.now() - search_start_time).total_seconds()
        await search_log_service.log_search(
            user_id=current_user.id,
            search_type="basic",
            departure_city=departure_code.upper(),
            arrival_city=destination_code.upper(),
            departure_date=depart_date,
            return_date=return_date,
            passenger_count=adults + children + infants_in_seat + infants_on_lap,
            results_count=0,
            search_duration=search_duration,
            success=False,
            error_message=str(e),
        )

        logger.error(f"搜索航班失败: {e}")
        return {
            'success': False,
            'error': str(e),
            'data': {'itineraries': []},
            'flights': [],
            'message': str(e),
            'search_info': {
                'source': 'smart-flights',
                'search_time': '',
                'total_count': 0,
                'departure_code': departure_code if 'departure_code' in locals() else 'N/A',
                'destination_code': destination_code if 'destination_code' in locals() else 'N/A',
                'depart_date': depart_date if 'depart_date' in locals() else 'N/A',
            },
            'search_time': '',
            'total_count': 0,
        }


@router.get("/search/comprehensive")
async def search_flights_comprehensive(
    departure_code: str = Query(..., description="出发机场代码", min_length=3, max_length=3),
    destination_code: str = Query(..., description="目的地机场代码", min_length=3, max_length=3),
    depart_date: str = Query(..., description="出发日期(YYYY-MM-DD)"),
    return_date: str | None = Query(None, description="返程日期(YYYY-MM-DD)"),
    adults: int = Query(1, description="成人数量", ge=1, le=9),
    children: int = Query(0, description="儿童数量", ge=0, le=8),
    infants_in_seat: int = Query(0, description="婴儿占座数量", ge=0, le=8),
    infants_on_lap: int = Query(0, description="婴儿怀抱数量", ge=0, le=8),
    seat_class: SeatClass = Query(SeatClass.ECONOMY, description="座位等级"),
    max_stops: MaxStops = Query(MaxStops.ANY, description="最大中转次数"),
    sort_by: SortBy = Query(SortBy.CHEAPEST, description="排序方式"),
    language: str = Query("zh", description="语言设置 (zh/en)"),
    currency: str = Query("CNY", description="货币设置 (CNY/USD)"),
    current_user: UserInfo = Depends(get_current_active_user),
):
    """
    三阶段综合航班搜索

    阶段1: Google Flights 常规搜索
    阶段2: Kiwi 隐藏城市搜索
    阶段3: AI 分析隐藏城市机会
    """
    try:
        logger.info(
            f"用户 {current_user.username} 开始三阶段航班搜索: {departure_code} -> {destination_code}, {depart_date}"
        )

        # 验证必需参数
        if not all([departure_code, destination_code, depart_date]):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail='缺少必需参数：出发机场代码、目的地机场代码、出发日期'
            )

        # 验证机场代码格式
        if len(departure_code) != 3 or len(destination_code) != 3:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='机场代码必须是3位字母')

        # 验证出发地和目的地不能相同
        if departure_code.upper() == destination_code.upper():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='出发地和目的地不能相同')

        # 获取航班搜索服务
        flight_service = get_flight_service()

        # 执行三阶段综合搜索
        result = await flight_service.search_flights_comprehensive(
            departure_code=departure_code.upper(),
            destination_code=destination_code.upper(),
            depart_date=depart_date,
            return_date=return_date,
            adults=adults,
            seat_class=seat_class.value,
            children=children,
            infants_in_seat=infants_in_seat,
            infants_on_lap=infants_on_lap,
            max_stops=max_stops.value,
            sort_by=sort_by.value,
            language=language,
            currency=currency,
        )

        logger.info(f"三阶段航班搜索完成: 成功={result['success']}, 总结果数={result['total_count']}")

        # 添加搜索阶段统计信息
        if 'search_stages' in result:
            stages_info = []
            for stage_key, stage_data in result['search_stages'].items():
                stages_info.append(
                    {
                        'stage': stage_key,
                        'name': stage_data['name'],
                        'status': stage_data['status'],
                        'flight_count': len(stage_data.get('flights', [])),
                    }
                )
            logger.info(f"搜索阶段详情: {stages_info}")

        return result

    except HTTPException:
        # 重新抛出HTTP异常
        raise
    except Exception as e:
        logger.error(f"三阶段航班搜索失败: {e}")
        return {
            'success': False,
            'error': str(e),
            'flights': [],
            'search_stages': {},
            'message': str(e),
            'total_count': 0,
            'search_info': {
                'source': 'comprehensive_search',
                'search_time': '',
                'departure_code': departure_code if 'departure_code' in locals() else 'N/A',
                'destination_code': destination_code if 'destination_code' in locals() else 'N/A',
                'depart_date': depart_date if 'depart_date' in locals() else 'N/A',
                'stages_completed': 0,
            },
        }


@router.get("/monitor/{city_code}")
async def get_monitor_data_legacy(
    city_code: str,
    blacklist_cities: str | None = Query(None, description="黑名单城市，逗号分隔"),
    blacklist_countries: str | None = Query(None, description="黑名单国家，逗号分隔"),
    current_user: UserInfo = Depends(get_current_active_user),
):
    """
    获取监控页面数据 (旧版API，保持兼容性，现在返回所有航班)
    """
    return await get_monitor_data_internal(city_code, blacklist_cities, blacklist_countries, current_user)


async def get_monitor_data_internal(
    city_code: str, blacklist_cities: str | None, blacklist_countries: str | None, current_user: UserInfo
):
    """
    获取监控页面数据

    支持的城市代码: HKG, SZX, CAN, MFM
    """
    try:
        logger.info(f"用户 {current_user.username} 获取监控数据: {city_code}")

        # 验证城市代码
        supported_cities = ['HKG', 'SZX', 'CAN', 'MFM']
        if city_code.upper() not in supported_cities:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f'不支持的城市代码: {city_code}，支持的城市: {", ".join(supported_cities)}',
            )

        # 处理黑名单参数
        blacklist_cities_list = []
        blacklist_countries_list = []

        if blacklist_cities:
            blacklist_cities_list = [city.strip() for city in blacklist_cities.split(',') if city.strip()]

        if blacklist_countries:
            blacklist_countries_list = [
                country.strip() for country in blacklist_countries.split(',') if country.strip()
            ]

        # 获取航班搜索服务
        flight_service = get_flight_service()

        # 执行异步监控数据获取
        result = await flight_service.get_monitor_data_async(
            city_code=city_code.upper(),
            blacklist_cities=blacklist_cities_list,
            blacklist_countries=blacklist_countries_list,
        )

        logger.info(f"监控数据获取完成: 成功={result['success']}, 航班数={len(result.get('flights', []))}")
        return result

    except HTTPException:
        # 重新抛出HTTP异常
        raise
    except Exception as e:
        logger.error(f"获取监控数据失败: {e}")
        return {
            'success': False,
            'error': str(e),
            'flights': [],
            'stats': {'total': 0, 'lowPrice': 0, 'minPrice': 0},
            'city_name': city_code,
            'city_flag': '🏙️',
        }


@router.get("/search/ai-enhanced")
async def search_flights_ai_enhanced(
    departure_code: str = Query(..., description="出发机场代码", min_length=3, max_length=3),
    destination_code: str = Query(..., description="目的地机场代码", min_length=3, max_length=3),
    depart_date: str = Query(..., description="出发日期(YYYY-MM-DD)"),
    return_date: str | None = Query(None, description="返程日期(YYYY-MM-DD)"),
    adults: int = Query(1, description="成人数量", ge=1, le=9),
    children: int = Query(0, description="儿童数量", ge=0, le=8),
    infants_in_seat: int = Query(0, description="婴儿占座数量", ge=0, le=8),
    infants_on_lap: int = Query(0, description="婴儿怀抱数量", ge=0, le=8),
    seat_class: SeatClass = Query(SeatClass.ECONOMY, description="座位等级"),
    max_stops: MaxStops = Query(MaxStops.ANY, description="最大中转次数"),
    sort_by: SortBy = Query(SortBy.CHEAPEST, description="排序方式"),
    user_preferences: str = Query("", description="用户偏好描述"),
    language: str = Query("zh", description="语言设置 (zh/en)"),
    currency: str = Query("CNY", description="货币设置 (CNY/USD)"),
    current_user: UserInfo | None = Depends(get_current_user_optional),
):
    """
    AI增强航班搜索 - 根据用户等级提供不同级别的服务

    - guest/user: 基础AI搜索
    - plus/pro: 增强AI搜索 + 隐藏城市搜索
    - max/vip: 完整AI搜索 + 高级分析
    """
    try:
        # 检查用户等级权限
        from fastapi_app.dependencies.permissions import Permission, PermissionChecker, Role

        user_role = PermissionChecker.get_user_role(current_user)
        logger.info(f"用户等级: {user_role.value}, AI增强搜索: {departure_code} -> {destination_code}")

        # 根据用户等级限制功能
        if user_role == Role.GUEST:
            # 游客限制为基础搜索，使用标准化错误
            create_upgrade_prompt('guest', 'AI搜索')
            raise UserLevelError.insufficient_level(
                current_level='guest', required_level='user', feature_name='AI搜索功能'
            )

        # 消费AI搜索配额
        has_ai_quota = await check_user_quota(current_user, QuotaType.AI_SEARCH)
        if not has_ai_quota:
            from fastapi_app.dependencies.quota_utils import get_quota_status

            quota_status = await get_quota_status(current_user, QuotaType.AI_SEARCH)
            # 使用标准化配额错误
            raise QuotaError.quota_exceeded(
                quota_type="AI搜索",
                used=quota_status.get('used_today', 0),
                limit=quota_status.get('daily_limit', 0),
                reset_time="明日00:00 UTC",
            )

        # 消费配额
        await consume_user_quota(current_user, QuotaType.AI_SEARCH, 1)

        # 获取更新后的AI配额状态
        ai_quota_status = await get_quota_status(current_user, QuotaType.AI_SEARCH)

        # 检查AI搜索权限
        has_enhanced_search = PermissionChecker.has_permission(current_user, Permission.FLIGHT_SEARCH_ENHANCED)
        has_unlimited_ai = PermissionChecker.has_permission(current_user, Permission.FLIGHT_AI_UNLIMITED)

        # 根据等级调整搜索参数
        search_config = {
            "use_ai_analysis": True,
            "include_hidden_city": has_enhanced_search,
            "max_results": 20 if user_role in [Role.USER] else 50,
            "enable_advanced_filtering": has_enhanced_search,
            "priority_processing": has_unlimited_ai,
        }

        logger.info(
            f"用户 {current_user.username if current_user else '匿名'} (等级: {user_role.value}) 使用AI搜索配置: {search_config}"
        )

        # 执行搜索逻辑...
        # 这里继续原有的搜索代码

        return APIResponse(
            success=True,
            message=f"AI增强搜索完成 (等级: {user_role.value})",
            data={
                "user_level": user_role.value,
                "search_config": search_config,
                "quota_info": {
                    "ai_search_quota": ai_quota_status,
                    "remaining_ai_searches": ai_quota_status.get('remaining', 0),
                },
                "flights": [],  # 实际搜索结果
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"AI增强搜索失败: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="AI搜索服务异常")


class AsyncSearchRequest(BaseModel):
    """异步搜索任务请求模型"""

    task_id: str
    status: str
    stage: str
    progress: float
    estimated_duration: int | None = None
    created_at: str
    updated_at: str
    estimated_duration: int | None = None


@router.post("/search/ai-enhanced/async", response_model=APIResponse)
async def start_ai_enhanced_search_async(
    departure_code: str = Query(..., description="出发机场代码", min_length=3, max_length=3),
    destination_code: str = Query(..., description="目的地机场代码", min_length=3, max_length=3),
    depart_date: str = Query(..., description="出发日期(YYYY-MM-DD)"),
    return_date: str | None = Query(None, description="返程日期(YYYY-MM-DD)"),
    adults: int = Query(1, description="成人数量", ge=1, le=9),
    children: int = Query(0, description="儿童数量", ge=0, le=8),
    infants_in_seat: int = Query(0, description="婴儿占座数量", ge=0, le=8),
    infants_on_lap: int = Query(0, description="婴儿怀抱数量", ge=0, le=8),
    seat_class: SeatClass = Query(SeatClass.ECONOMY, description="座位等级"),
    max_stops: MaxStops = Query(MaxStops.ANY, description="最大中转次数"),
    sort_by: SortBy = Query(SortBy.CHEAPEST, description="排序方式"),
    language: str = Query("zh", description="语言设置 (zh/en)"),
    currency: str = Query("CNY", description="货币设置 (CNY/USD)"),
    user_preferences: str = Query("", description="用户偏好和要求"),
    current_user: UserInfo | None = Depends(get_current_user_optional),
    task_service: AsyncTaskService = Depends(get_async_task_service),
):
    """
    异步AI增强航班搜索 - 提交任务

    立即返回任务ID，搜索在后台进行
    """
    try:
        # 处理游客和登录用户
        user_display = current_user.username if current_user else "游客"
        user_id = current_user.id if current_user else "guest"

        logger.info(f"用户 {user_display} 开始异步AI增强搜索: {departure_code} → {destination_code}")

        # 初始化异步任务服务
        try:
            await task_service.initialize()
        except RuntimeError as exc:
            logger.error(f"异步任务服务初始化失败: {exc}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="任务服务当前不可用，请稍后重试",
            ) from exc

        # 准备搜索参数
        search_params = {
            "departure_code": departure_code.upper(),
            "destination_code": destination_code.upper(),
            "depart_date": depart_date,
            "return_date": return_date,
            "adults": adults,
            "children": children,
            "infants_in_seat": infants_in_seat,
            "infants_on_lap": infants_on_lap,
            "seat_class": seat_class.value,
            "max_stops": max_stops.value,
            "sort_by": sort_by.value,
            "language": language,
            "currency": currency,
            "user_preferences": user_preferences,
            "is_guest_user": current_user is None,  # 关键：判断是否为游客用户
        }

        # 创建异步任务
        try:
            task_id = await task_service.create_task(
                task_type="ai_flight_search", search_params=search_params, user_id=user_id
            )
        except RuntimeError as exc:
            logger.error(f"创建异步任务失败: {exc}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="任务服务当前不可用，请稍后重试",
            ) from exc

        # 智能时间预估
        estimated_duration = _estimate_search_time(search_params)

        # 启动后台任务
        asyncio.create_task(_execute_ai_search_background(task_id, search_params, task_service))

        # 确保任务信息已写入缓存后再响应，降低竞态风险
        task_snapshot = None
        confirmation_attempts = 3
        confirmation_delay = 0.2

        for attempt in range(1, confirmation_attempts + 1):
            task_snapshot = await task_service.get_task_info(task_id)
            if task_snapshot:
                logger.debug(f"异步任务 {task_id} 已在缓存中确认 (尝试 {attempt})")
                break
            logger.debug(
                f"异步任务 {task_id} 尚未在缓存中可用，重试 ({attempt}/{confirmation_attempts})"
            )
            await asyncio.sleep(confirmation_delay)

        if task_snapshot is None:
            logger.error(f"异步任务 {task_id} 在预期时间内未注册到缓存，取消任务创建")
            await task_service.delete_task(task_id)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="任务服务当前不可用，请稍后重试",
            )

        return APIResponse(
            success=True,
            message="AI搜索任务已提交，请使用任务ID查询进度",
            data={
                "task_id": task_id,
                "status": "PENDING",
                "estimated_duration": estimated_duration,
                "polling_interval": 2,  # 建议2秒轮询一次，更加流畅
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"提交异步AI搜索任务失败: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"提交搜索任务失败: {str(e)}")


@router.get("/task/{task_id}/status", response_model=APIResponse)
async def get_task_status(
    task_id: str,
    current_user: UserInfo | None = Depends(get_current_user_optional),
    task_service: AsyncTaskService = Depends(get_async_task_service),
):
    """
    查询异步任务状态
    """
    try:
        # 初始化异步任务服务
        try:
            await task_service.initialize()
        except RuntimeError as exc:
            logger.error(f"任务服务初始化失败: {exc}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="任务服务当前不可用，请稍后重试",
            ) from exc

        # 获取任务信息
        task_info = await task_service.get_task_info(task_id)
        logger.info(f"🔍 查询任务信息: {task_id}, 结果: {task_info}")

        if not task_info:
            logger.warning(f"❌ 任务不存在: {task_id}")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")

        # 检查任务所有权（可选）
        # 对于游客用户，跳过权限检查
        if current_user and task_info.get("user_id") != current_user.id:
            # 如果是游客任务，允许访问
            if task_info.get("user_id") != "guest":
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问此任务")

        # 确保状态正确序列化
        status_value = task_info["status"]
        if hasattr(status_value, 'value'):
            status_value = status_value.value

        logger.info(f"📊 返回任务状态: {task_id} -> {status_value}")

        return APIResponse(
            success=True,
            message="任务状态获取成功",
            data={
                "task_id": task_id,
                "status": status_value,
                "progress": task_info.get("progress", 0),
                "message": task_info.get("message", ""),
                "created_at": task_info["created_at"],
                "updated_at": task_info["updated_at"],
                "estimated_duration": task_info.get("estimated_duration", 120),
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取任务状态失败: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"获取任务状态失败: {str(e)}")


@router.get("/task/{task_id}/result", response_model=APIResponse)
async def get_task_result(
    task_id: str,
    current_user: UserInfo | None = Depends(get_current_user_optional),
    task_service: AsyncTaskService = Depends(get_async_task_service),
):
    """
    获取异步任务结果
    """
    try:
        # 初始化异步任务服务
        try:
            await task_service.initialize()
        except RuntimeError as exc:
            logger.error(f"任务服务初始化失败: {exc}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="任务服务当前不可用，请稍后重试",
            ) from exc

        # 获取任务信息
        task_info = await task_service.get_task_info(task_id)

        if not task_info:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")

        # 检查任务所有权（可选）
        # 对于游客用户，跳过权限检查
        if current_user and task_info.get("user_id") != current_user.id:
            # 如果是游客任务，允许访问
            if task_info.get("user_id") != "guest":
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问此任务")

        # 检查任务状态
        if task_info["status"] != TaskStatus.COMPLETED.value:
            return APIResponse(
                success=False,
                message=f"任务尚未完成，当前状态: {task_info['status']}",
                data={
                    "task_id": task_id,
                    "status": task_info["status"],
                    "progress": task_info.get("progress", 0),
                    "message": task_info.get("message", ""),
                },
            )

        # 获取任务结果
        result = await task_service.get_task_result(task_id)

        if not result:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务结果不存在")

        return APIResponse(success=True, message="搜索结果获取成功", data=result)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取任务结果失败: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"获取任务结果失败: {str(e)}")


# ==================== 后台任务执行函数 ====================


def _estimate_search_time(search_params: dict[str, Any]) -> int:
    """
    智能估算搜索完成时间（秒）
    基于搜索参数的复杂度动态计算
    """
    base_time = 45  # 基础时间45秒

    # 根据用户偏好增加时间
    if search_params.get("user_preferences") and len(search_params["user_preferences"]) > 20:
        base_time += 15  # AI分析需要额外时间

    # 根据用户类型调整
    if search_params.get("is_guest_user"):
        base_time -= 10  # 游客用户使用简化搜索
    else:
        base_time += 20  # 登录用户使用完整搜索

    # 根据日期距离调整（未来30天内的搜索通常更快）
    try:
        from datetime import datetime

        depart_date = datetime.strptime(search_params["depart_date"], "%Y-%m-%d")
        days_ahead = (depart_date - datetime.now()).days
        if days_ahead > 30:
            base_time += 10  # 远期航班搜索更复杂
    except:
        pass

    # 往返程搜索需要更多时间
    if search_params.get("return_date"):
        base_time += 15

    # 多人搜索稍微增加时间
    passengers = search_params.get("adults", 1) + search_params.get("children", 0)
    if passengers > 2:
        base_time += 5

    # 确保时间在合理范围内
    return max(30, min(base_time, 180))  # 30秒-3分钟之间


# 已移除旧的进度阶段函数，现在使用 StageInfo.get_stage_by_progress()


def _calculate_remaining_time(progress: float, estimated_total: int) -> int:
    """计算剩余时间（秒）"""
    if progress >= 1.0:
        return 0
    if progress <= 0:
        return estimated_total

    # 基于当前进度计算剩余时间
    remaining_ratio = 1.0 - progress
    remaining_time = int(estimated_total * remaining_ratio)

    # 确保剩余时间合理
    return max(5, min(remaining_time, estimated_total))


async def _execute_ai_search_background(
    task_id: str, search_params: dict[str, Any], task_service: AsyncTaskService
):
    """
    后台执行AI增强搜索 - 增强版进度报告
    """
    try:
        logger.info(f"开始执行后台AI搜索任务: {task_id}")

        try:
            await task_service.initialize()
        except RuntimeError as exc:
            logger.error(f"后台任务初始化失败: {exc}")
            await task_service.update_task_status(
                task_id,
                TaskStatus.FAILED,
                progress=0,
                message="任务服务不可用，无法执行搜索",
                error=str(exc),
            )
            return

        # 阶段0: 连接数据库 (0-25%)
        await task_service.update_task_status(
            task_id,
            TaskStatus.PROCESSING,
            progress=0.05,
            message="正在连接数据库...",
            stage=ProcessingStage.INITIALIZATION,
        )

        await asyncio.sleep(0.5)  # 让前端看到进度变化

        await task_service.update_task_status(
            task_id,
            TaskStatus.PROCESSING,
            progress=0.10,
            message="正在初始化搜索引擎...",
            stage=ProcessingStage.INITIALIZATION,
        )

        await asyncio.sleep(0.5)

        await task_service.update_task_status(
            task_id,
            TaskStatus.PROCESSING,
            progress=0.20,
            message="正在准备搜索参数...",
            stage=ProcessingStage.INITIALIZATION,
        )

        # 创建AI搜索服务实例
        flight_service = AIFlightService()

        # 阶段1: 搜索航班 (25-50%)
        await task_service.update_task_status(
            task_id, TaskStatus.PROCESSING, progress=0.25, message="正在搜索航班...", stage=ProcessingStage.SEARCHING
        )

        # 模拟搜索过程中的进度更新
        search_stages = [
            (0.30, "正在查询主要航空公司..."),
            (0.35, "正在查询廉价航空公司..."),
            (0.40, "正在搜索隐藏城市机会..."),
            (0.45, "正在收集价格信息..."),
        ]

        for progress, message in search_stages:
            await task_service.update_task_status(
                task_id, TaskStatus.PROCESSING, progress=progress, message=message, stage=ProcessingStage.SEARCHING
            )
            await asyncio.sleep(0.3)  # 短暂延迟显示进度

        # 阶段2: 分析数据 (50-75%)
        await task_service.update_task_status(
            task_id, TaskStatus.PROCESSING, progress=0.55, message="正在分析数据...", stage=ProcessingStage.AI_ANALYSIS
        )

        await asyncio.sleep(0.5)

        await task_service.update_task_status(
            task_id,
            TaskStatus.PROCESSING,
            progress=0.65,
            message="AI智能分析价格和时间...",
            stage=ProcessingStage.AI_ANALYSIS,
        )

        # 执行AI增强搜索
        result = await flight_service.search_flights_ai_enhanced(
            departure_code=search_params["departure_code"],
            destination_code=search_params["destination_code"],
            depart_date=search_params["depart_date"],
            return_date=search_params.get("return_date"),
            adults=search_params["adults"],
            seat_class=search_params["seat_class"],
            children=search_params["children"],
            infants_in_seat=search_params["infants_in_seat"],
            infants_on_lap=search_params["infants_on_lap"],
            max_stops=search_params["max_stops"],
            sort_by=search_params["sort_by"],
            language=search_params["language"],
            currency=search_params["currency"],
            user_preferences=search_params["user_preferences"],
            is_guest_user=search_params.get("is_guest_user", False),
        )

        # 阶段3: 生成推荐 (75-100%)
        await task_service.update_task_status(
            task_id, TaskStatus.PROCESSING, progress=0.80, message="正在生成推荐...", stage=ProcessingStage.FINALIZING
        )

        await asyncio.sleep(0.3)

        await task_service.update_task_status(
            task_id,
            TaskStatus.PROCESSING,
            progress=0.90,
            message="为您个性化定制最佳方案...",
            stage=ProcessingStage.FINALIZING,
        )

        await asyncio.sleep(0.2)

        await task_service.update_task_status(
            task_id,
            TaskStatus.PROCESSING,
            progress=0.95,
            message="正在最终确认结果...",
            stage=ProcessingStage.FINALIZING,
        )

        # 保存搜索结果
        await task_service.save_task_result(task_id, result)

        # 更新任务状态为完成
        await task_service.update_task_status(
            task_id, TaskStatus.COMPLETED, progress=1.0, message="搜索完成", stage=ProcessingStage.FINALIZING
        )

        logger.info(f"后台AI搜索任务完成: {task_id}, 找到 {len(result.get('flights', []))} 个航班")

    except Exception as e:
        logger.error(f"后台AI搜索任务失败 {task_id}: {e}")

        # 更新任务状态为失败
        await task_service.update_task_status(
            task_id, TaskStatus.FAILED, progress=0, message="搜索失败", error=str(e)
        )


# ==================== SSE 实时推送端点 ====================


@router.get("/task/{task_id}/stream")
async def stream_task_status(
    task_id: str,
    current_user: UserInfo | None = Depends(get_current_user_optional),
    task_service: AsyncTaskService = Depends(get_async_task_service),
):
    """
    SSE实时推送任务状态
    支持游客访问，实时推送任务进度和结果
    """

    async def generate_sse_stream():
        """生成SSE数据流"""
        try:
            logger.info(f"🔄 开始SSE推送任务状态: {task_id}")

            try:
                await task_service.initialize()
            except RuntimeError as exc:
                logger.error(f"SSE初始化失败: {exc}")
                error_payload = {
                    "status": "SERVICE_UNAVAILABLE",
                    "message": "任务服务当前不可用，请稍后重试",
                    "error_code": "SERVICE_UNAVAILABLE",
                    "task_id": task_id,
                    "final": True,
                }
                yield f"data: {json.dumps(error_payload, ensure_ascii=False)}\n\n"
                yield f"event: error\ndata: {json.dumps({'error': 'SERVICE_UNAVAILABLE', 'final': True}, ensure_ascii=False)}\n\n"
                yield f"event: close\ndata: {json.dumps({'message': '任务服务不可用，连接关闭', 'final': True}, ensure_ascii=False)}\n\n"
                return

            # 检查任务是否存在，加入短暂重试以处理缓存写入延迟
            task_info = None
            max_retries = 3
            retry_delay = 0.5

            for attempt in range(1, max_retries + 1):
                task_info = await task_service.get_task_info(task_id)
                if task_info:
                    break
                logger.warning(f"SSE任务 {task_id} 未找到，正在重试 ({attempt}/{max_retries})")
                await asyncio.sleep(retry_delay)

            if not task_info:
                error_payload = {
                    "status": "TASK_NOT_FOUND",
                    "message": "任务不存在或已过期",
                    "error_code": "TASK_NOT_FOUND",
                    "task_id": task_id,
                    "final": True,
                }
                logger.warning(f"⚠️ SSE任务不存在: {task_id}")

                # 明确向前端发送最终错误事件，并随后终止生成器
                yield f"data: {json.dumps(error_payload, ensure_ascii=False)}\n\n"
                yield f"event: error\ndata: {json.dumps({'error': 'TASK_NOT_FOUND', 'final': True}, ensure_ascii=False)}\n\n"
                yield f"event: close\ndata: {json.dumps({'message': '任务不存在，连接关闭', 'final': True}, ensure_ascii=False)}\n\n"
                return

            # 检查任务所有权（游客可访问）
            if current_user and task_info.get("user_id") != current_user.id:
                if task_info.get("user_id") != "guest":
                    error_data = {
                        "status": "ACCESS_DENIED",
                        "message": "无权访问此任务",
                        "error_code": "ACCESS_DENIED",
                        "final": True,
                    }
                    yield f"data: {json.dumps(error_data, ensure_ascii=False)}\n\n"
                    yield f"event: error\ndata: {json.dumps({'error': 'ACCESS_DENIED', 'final': True}, ensure_ascii=False)}\n\n"
                    yield f"event: close\ndata: {json.dumps({'message': '权限不足，连接关闭', 'final': True}, ensure_ascii=False)}\n\n"
                    return

            # 发送初始状态
            initial_status = task_info.get("status", "PENDING")
            initial_progress = task_info.get("progress", 0)
            # 默认预估时间60秒
            default_estimated_duration = 60

            # 获取初始阶段信息
            initial_stage = task_info.get("stage", ProcessingStage.INITIALIZATION.value)
            try:
                # 尝试将字符串转换为ProcessingStage枚举
                if isinstance(initial_stage, str):
                    stage_enum = ProcessingStage(initial_stage)
                else:
                    stage_enum = ProcessingStage.INITIALIZATION
            except ValueError:
                stage_enum = ProcessingStage.INITIALIZATION

            stage_info = StageInfo.get_stage_info(stage_enum)

            initial_data = {
                "status": initial_status,
                "progress": initial_progress,
                "message": task_info.get("message", ""),
                "task_id": task_id,
                "created_at": task_info.get("created_at"),
                "updated_at": task_info.get("updated_at"),
                "estimated_duration": task_info.get("estimated_duration", default_estimated_duration),
                "reconnected": True if "last_event_id" in locals() else False,  # 标记是否为重连
                "stage": {
                    "id": stage_info.get("id", 0),  # 修复：确保初始阶段ID正确传递
                    "title": stage_info.get("title", "正在初始化"),
                    "description": stage_info.get("description", "准备中..."),
                    "icon": stage_info.get("icon", "search"),
                },
            }

            logger.info(f"📤 SSE发送初始状态: {task_id} -> {initial_status} ({initial_progress}%)")
            yield f"data: {json.dumps(initial_data, ensure_ascii=False)}\n\n"

            # 如果任务已完成，发送结果并结束
            if initial_status == "COMPLETED":
                try:
                    result = await task_service.get_task_result(task_id)
                    if result:
                        # 简化：直接发送后端原始数据结构，让前端处理
                        result_data = {
                            "status": "COMPLETED",
                            "progress": 100,
                            "message": "任务完成",
                            "task_id": task_id,
                            "result": result,  # 直接发送原始结果，让前端处理数据结构
                            "final": True,  # 明确标记为最终消息
                        }
                        logger.info(f"📤 SSE发送完成结果: {task_id}")
                        logger.info(
                            f"📊 结果包含: {len(result.get('flights', []))} 个航班, AI报告长度: {len(result.get('ai_analysis_report', ''))}"
                        )
                        yield f"data: {json.dumps(result_data, ensure_ascii=False)}\n\n"
                except Exception as e:
                    logger.error(f"❌ SSE获取任务结果失败: {e}")

                # 发送结束事件
                yield f"event: close\ndata: {json.dumps({'message': '任务已完成', 'final': True}, ensure_ascii=False)}\n\n"
                return

            # 如果任务失败，发送错误并结束
            if initial_status == "FAILED":
                error_data = {
                    "status": "FAILED",
                    "progress": 0,
                    "message": task_info.get("message", "任务失败"),
                    "task_id": task_id,
                    "error": task_info.get("error", "未知错误"),
                    "final": True,
                }
                logger.info(f"📤 SSE发送失败状态: {task_id}")
                yield f"data: {json.dumps(error_data, ensure_ascii=False)}\n\n"
                yield f"event: error\ndata: {json.dumps({'error': 'TASK_FAILED', 'final': True}, ensure_ascii=False)}\n\n"
                yield f"event: close\ndata: {json.dumps({'message': '任务失败，连接关闭', 'final': True}, ensure_ascii=False)}\n\n"
                return

            # 轮询任务状态变化
            last_status = initial_status
            last_progress = task_info.get("progress", 0)
            last_updated = task_info.get("updated_at")

            max_wait_time = 300  # 最大等待5分钟
            start_time = datetime.now()

            while True:
                try:
                    # 检查超时
                    if (datetime.now() - start_time).total_seconds() > max_wait_time:
                        timeout_data = {"status": "TIMEOUT", "message": "任务超时", "task_id": task_id, "final": True}
                        yield f"data: {json.dumps(timeout_data, ensure_ascii=False)}\n\n"
                        yield f"event: error\ndata: {json.dumps({'error': 'TIMEOUT', 'final': True}, ensure_ascii=False)}\n\n"
                        yield f"event: close\ndata: {json.dumps({'message': '任务超时，连接关闭', 'final': True}, ensure_ascii=False)}\n\n"
                        break

                    # 获取最新任务状态
                    current_task_info = await task_service.get_task_info(task_id)
                    if not current_task_info:
                        # 任务在轮询过程中被删除
                        error_data = {
                            "status": "TASK_NOT_FOUND",
                            "message": "任务已被删除或过期",
                            "task_id": task_id,
                            "final": True,
                        }
                        yield f"data: {json.dumps(error_data, ensure_ascii=False)}\n\n"
                        yield f"event: error\ndata: {json.dumps({'error': 'TASK_DELETED', 'final': True}, ensure_ascii=False)}\n\n"
                        yield f"event: close\ndata: {json.dumps({'message': '任务已删除，连接关闭', 'final': True}, ensure_ascii=False)}\n\n"
                        break

                    current_status = current_task_info.get("status", "PENDING")
                    current_progress = current_task_info.get("progress", 0)
                    current_updated = current_task_info.get("updated_at")
                    current_message = current_task_info.get("message", "")

                    # 检查是否有状态变化
                    status_changed = (
                        current_status != last_status
                        or current_progress != last_progress
                        or current_updated != last_updated
                    )

                    if status_changed:
                        # 获取当前阶段信息
                        current_stage = StageInfo.get_stage_by_progress(current_progress)
                        stage_info = StageInfo.get_stage_info(current_stage)

                        # 发送状态更新
                        update_data = {
                            "status": current_status,
                            "progress": current_progress,
                            "message": current_message,
                            "task_id": task_id,
                            "updated_at": current_updated,
                            "stage": {
                                "id": stage_info.get("id", 0),  # 修复：确保阶段ID正确传递
                                "title": stage_info.get("title", "正在处理"),
                                "description": stage_info.get("description", "处理中..."),
                                "icon": stage_info.get("icon", "search"),
                            },
                            "estimated_remaining": _calculate_remaining_time(
                                current_progress, task_info.get("estimated_duration", 60)
                            ),
                        }

                        logger.info(f"📤 SSE发送状态更新: {task_id} -> {current_status} ({current_progress}%)")
                        yield f"data: {json.dumps(update_data, ensure_ascii=False)}\n\n"

                        # 更新记录的状态
                        last_status = current_status
                        last_progress = current_progress
                        last_updated = current_updated

                    # 如果任务完成，发送结果并结束
                    if current_status == "COMPLETED":
                        try:
                            result = await task_service.get_task_result(task_id)
                            if result:
                                # 简化：直接发送后端原始数据结构，让前端处理
                                result_data = {
                                    "status": "COMPLETED",
                                    "progress": 100,
                                    "message": "任务完成",
                                    "task_id": task_id,
                                    "result": result,  # 直接发送原始结果，让前端处理数据结构
                                    "final": True,
                                }
                                logger.info(f"📤 SSE发送最终结果: {task_id}")
                                logger.info(
                                    f"📊 结果包含: {len(result.get('flights', []))} 个航班, AI报告长度: {len(result.get('ai_analysis_report', ''))}"
                                )
                                yield f"data: {json.dumps(result_data, ensure_ascii=False)}\n\n"
                        except Exception as e:
                            logger.error(f"❌ SSE获取最终结果失败: {e}")

                        # 发送结束事件
                        yield f"event: close\ndata: {json.dumps({'message': '任务完成', 'final': True}, ensure_ascii=False)}\n\n"
                        break

                    # 如果任务失败，发送错误并结束
                    if current_status == "FAILED":
                        error_data = {
                            "status": "FAILED",
                            "progress": 0,
                            "message": current_message,
                            "task_id": task_id,
                            "error": current_task_info.get("error", "未知错误"),
                            "final": True,
                        }
                        logger.info(f"📤 SSE发送失败结果: {task_id}")
                        yield f"data: {json.dumps(error_data, ensure_ascii=False)}\n\n"
                        yield f"event: error\ndata: {json.dumps({'error': 'TASK_FAILED', 'final': True}, ensure_ascii=False)}\n\n"
                        yield f"event: close\ndata: {json.dumps({'message': '任务失败', 'final': True}, ensure_ascii=False)}\n\n"
                        break

                    # 等待2秒后再次检查
                    await asyncio.sleep(2)

                except Exception as e:
                    logger.error(f"❌ SSE轮询过程中出错: {e}")
                    error_data = {"status": "ERROR", "message": f"推送过程中出错: {str(e)}", "task_id": task_id}
                    yield f"data: {json.dumps(error_data, ensure_ascii=False)}\n\n"
                    break

        except asyncio.CancelledError:
            logger.info(f"🔚 SSE推送被客户端取消: {task_id}")
            return
        except Exception as e:
            logger.error(f"❌ SSE流生成失败: {e}")
            error_data = {"status": "ERROR", "message": f"服务器内部错误: {str(e)}", "task_id": task_id, "final": True}
            yield f"data: {json.dumps(error_data, ensure_ascii=False)}\n\n"
            yield f"event: error\ndata: {json.dumps({'error': 'INTERNAL_ERROR', 'final': True}, ensure_ascii=False)}\n\n"
            yield f"event: close\ndata: {json.dumps({'message': '服务器错误，连接关闭', 'final': True}, ensure_ascii=False)}\n\n"
        finally:
            logger.info(f"🔚 SSE推送结束: {task_id}")

    # 返回SSE响应
    return StreamingResponse(
        generate_sse_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "*",
            "Access-Control-Expose-Headers": "*",
        },
    )

