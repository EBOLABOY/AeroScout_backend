"""
FastAPI航班路由
"""
import asyncio
import json
import uuid
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks
from fastapi.responses import StreamingResponse
from loguru import logger
from typing import Optional, Dict, Any, List
from pydantic import BaseModel

from fastapi_app.models.common import APIResponse
from fastapi_app.models.auth import UserInfo
from fastapi_app.models.flights import (
    FlightSearchRequest, FlightSearchResponse, MonitorDataResponse,
    SeatClass, MaxStops, SortBy
)
from fastapi_app.dependencies.auth import get_current_active_user, get_current_user_optional
from fastapi_app.services.ai_flight_service import AIFlightService
from fastapi_app.services.flight_service import get_flight_service
from fastapi_app.services.async_task_service import async_task_service, TaskStatus

# 创建路由器
router = APIRouter()


@router.get("/health", response_model=APIResponse)
async def health_check():
    """
    健康检查接口
    """
    return APIResponse(
        success=True,
        message="航班服务正常",
        data={"status": "healthy", "service": "flights"}
    )


@router.get("/airports", response_model=APIResponse)
async def get_airports(
    query: str = Query("", description="搜索关键词"),
    current_user: UserInfo = Depends(get_current_active_user)
):
    """
    获取机场信息 (旧版API，保持兼容性)
    """
    return await search_airports_internal(query)


@router.get("/airports/search", response_model=APIResponse)
async def search_airports(
    q: str = Query("", description="搜索关键词"),
    language: str = Query("zh", description="语言设置")
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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="机场搜索服务异常"
        )


@router.get("/airports/search/auth", response_model=APIResponse)
async def search_airports_authenticated(
    q: str = Query("", description="搜索关键词"),
    language: str = Query("zh", description="语言设置"),
    current_user: UserInfo = Depends(get_current_active_user)
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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="机场搜索服务异常"
        )


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
                            "presentation": {
                                "suggestionTitle": f"{name} ({code}) - {city}, {country}"
                            }
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
                            "presentation": {
                                "suggestionTitle": f"{name} ({code}) - {city}, {country}"
                            }
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
                    {"code": "TPE", "name": "台北桃园国际机场", "city": "台北", "country": "中国台湾", "type": "airport"},
                    {"code": "NRT", "name": "东京成田国际机场", "city": "东京", "country": "日本", "type": "airport"},
                    {"code": "ICN", "name": "首尔仁川国际机场", "city": "首尔", "country": "韩国", "type": "airport"},
                    {"code": "SIN", "name": "新加坡樟宜机场", "city": "新加坡", "country": "新加坡", "type": "airport"}
                ]

        except ImportError as e:
            logger.warning(f"smart-flights机场搜索API不可用: {e}")
            # 降级到静态数据
            static_airports = [
                {"code": "PEK", "name": "北京首都国际机场", "city": "北京", "country": "中国", "type": "airport"},
                {"code": "PVG", "name": "上海浦东国际机场", "city": "上海", "country": "中国", "type": "airport"},
                {"code": "CAN", "name": "广州白云国际机场", "city": "广州", "country": "中国", "type": "airport"},
                {"code": "SZX", "name": "深圳宝安国际机场", "city": "深圳", "country": "中国", "type": "airport"},
                {"code": "HGH", "name": "杭州萧山国际机场", "city": "杭州", "country": "中国", "type": "airport"}
            ]

            # 如果有查询参数，进行过滤
            if query:
                query_lower = query.lower()
                static_airports = [
                    airport for airport in static_airports
                    if query_lower in airport["name"].lower() or
                       query_lower in airport["city"].lower() or
                       query_lower in airport["code"].lower()
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
                    "presentation": {
                        "suggestionTitle": f"{name} ({code}) - {city}, {country}"
                    }
                }
                airports.append(airport_data)

        return APIResponse(
            success=True,
            message="机场搜索成功",
            data={"airports": airports, "total": len(airports)}
        )

    except Exception as e:
        logger.error(f"机场搜索内部错误: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="机场搜索服务异常"
        )


@router.get("/airports/popular", response_model=APIResponse)
async def get_popular_airports(
    language: str = Query("zh", description="语言设置"),
    current_user: UserInfo = Depends(get_current_active_user)
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
            {"code": "KUL", "name": "吉隆坡国际机场", "city": "吉隆坡", "country": "马来西亚", "popular": True}
        ]

        return APIResponse(
            success=True,
            message=f"获取到 {len(popular_airports)} 个热门机场",
            data={"airports": popular_airports, "total": len(popular_airports), "language": language}
        )

    except Exception as e:
        logger.error(f"获取热门机场失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取热门机场失败"
        )


@router.get("/search")
async def search_flights(
    departure_code: str = Query(..., description="出发机场代码", min_length=3, max_length=3),
    destination_code: str = Query(..., description="目的地机场代码", min_length=3, max_length=3),
    depart_date: str = Query(..., description="出发日期(YYYY-MM-DD)"),
    return_date: Optional[str] = Query(None, description="返程日期(YYYY-MM-DD)"),
    adults: int = Query(1, description="成人数量", ge=1, le=9),
    children: int = Query(0, description="儿童数量", ge=0, le=8),
    infants_in_seat: int = Query(0, description="婴儿占座数量", ge=0, le=8),
    infants_on_lap: int = Query(0, description="婴儿怀抱数量", ge=0, le=8),
    seat_class: SeatClass = Query(SeatClass.ECONOMY, description="座位等级"),
    max_stops: MaxStops = Query(MaxStops.ANY, description="最大中转次数"),
    sort_by: SortBy = Query(SortBy.CHEAPEST, description="排序方式"),
    language: str = Query("zh", description="语言设置 (zh/en)"),
    currency: str = Query("CNY", description="货币设置 (CNY/USD)"),
    current_user: UserInfo = Depends(get_current_active_user)
):
    """
    搜索航班

    集成smart-flights库进行真实的航班搜索
    """
    try:
        logger.info(f"用户 {current_user.username} 搜索航班: {departure_code} -> {destination_code}, {depart_date}, 语言: {language}, 货币: {currency}")

        # 验证必需参数
        if not all([departure_code, destination_code, depart_date]):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail='缺少必需参数：出发机场代码、目的地机场代码、出发日期'
            )

        # 验证机场代码格式
        if len(departure_code) != 3 or len(destination_code) != 3:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail='机场代码必须是3位字母'
            )

        # 验证出发地和目的地不能相同
        if departure_code.upper() == destination_code.upper():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail='出发地和目的地不能相同'
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
            currency=currency
        )

        logger.info(f"航班搜索完成: 成功={result['success']}, 结果数={result['total_count']}")
        return result

    except HTTPException:
        # 重新抛出HTTP异常
        raise
    except Exception as e:
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
                'depart_date': depart_date if 'depart_date' in locals() else 'N/A'
            },
            'search_time': '',
            'total_count': 0
        }


@router.get("/search/comprehensive")
async def search_flights_comprehensive(
    departure_code: str = Query(..., description="出发机场代码", min_length=3, max_length=3),
    destination_code: str = Query(..., description="目的地机场代码", min_length=3, max_length=3),
    depart_date: str = Query(..., description="出发日期(YYYY-MM-DD)"),
    return_date: Optional[str] = Query(None, description="返程日期(YYYY-MM-DD)"),
    adults: int = Query(1, description="成人数量", ge=1, le=9),
    children: int = Query(0, description="儿童数量", ge=0, le=8),
    infants_in_seat: int = Query(0, description="婴儿占座数量", ge=0, le=8),
    infants_on_lap: int = Query(0, description="婴儿怀抱数量", ge=0, le=8),
    seat_class: SeatClass = Query(SeatClass.ECONOMY, description="座位等级"),
    max_stops: MaxStops = Query(MaxStops.ANY, description="最大中转次数"),
    sort_by: SortBy = Query(SortBy.CHEAPEST, description="排序方式"),
    language: str = Query("zh", description="语言设置 (zh/en)"),
    currency: str = Query("CNY", description="货币设置 (CNY/USD)"),
    current_user: UserInfo = Depends(get_current_active_user)
):
    """
    三阶段综合航班搜索

    阶段1: Google Flights 常规搜索
    阶段2: Kiwi 隐藏城市搜索
    阶段3: AI 分析隐藏城市机会
    """
    try:
        logger.info(f"用户 {current_user.username} 开始三阶段航班搜索: {departure_code} -> {destination_code}, {depart_date}")

        # 验证必需参数
        if not all([departure_code, destination_code, depart_date]):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail='缺少必需参数：出发机场代码、目的地机场代码、出发日期'
            )

        # 验证机场代码格式
        if len(departure_code) != 3 or len(destination_code) != 3:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail='机场代码必须是3位字母'
            )

        # 验证出发地和目的地不能相同
        if departure_code.upper() == destination_code.upper():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail='出发地和目的地不能相同'
            )

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
            currency=currency
        )

        logger.info(f"三阶段航班搜索完成: 成功={result['success']}, 总结果数={result['total_count']}")

        # 添加搜索阶段统计信息
        if 'search_stages' in result:
            stages_info = []
            for stage_key, stage_data in result['search_stages'].items():
                stages_info.append({
                    'stage': stage_key,
                    'name': stage_data['name'],
                    'status': stage_data['status'],
                    'flight_count': len(stage_data.get('flights', []))
                })
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
                'stages_completed': 0
            }
        }


@router.get("/monitor/{city_code}")
async def get_monitor_data_legacy(
    city_code: str,
    blacklist_cities: Optional[str] = Query(None, description="黑名单城市，逗号分隔"),
    blacklist_countries: Optional[str] = Query(None, description="黑名单国家，逗号分隔"),
    current_user: UserInfo = Depends(get_current_active_user)
):
    """
    获取监控页面数据 (旧版API，保持兼容性，现在返回所有航班)
    """
    return await get_monitor_data_internal(city_code, blacklist_cities, blacklist_countries, current_user)


async def get_monitor_data_internal(
    city_code: str,
    blacklist_cities: Optional[str],
    blacklist_countries: Optional[str],
    current_user: UserInfo
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
                detail=f'不支持的城市代码: {city_code}，支持的城市: {", ".join(supported_cities)}'
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
            city_code=city_code.upper(),
            blacklist_cities=blacklist_cities_list,
            blacklist_countries=blacklist_countries_list
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
            'city_flag': '🏙️'
        }


@router.get("/search/ai-enhanced")
async def search_flights_ai_enhanced(
    departure_code: str = Query(..., description="出发机场代码", min_length=3, max_length=3),
    destination_code: str = Query(..., description="目的地机场代码", min_length=3, max_length=3),
    depart_date: str = Query(..., description="出发日期(YYYY-MM-DD)"),
    return_date: Optional[str] = Query(None, description="返程日期(YYYY-MM-DD)"),
    adults: int = Query(1, description="成人数量", ge=1, le=9),
    children: int = Query(0, description="儿童数量", ge=0, le=8),
    infants_in_seat: int = Query(0, description="婴儿占座数量", ge=0, le=8),
    infants_on_lap: int = Query(0, description="婴儿怀抱数量", ge=0, le=8),
    seat_class: SeatClass = Query(SeatClass.ECONOMY, description="座位等级"),
    max_stops: MaxStops = Query(MaxStops.ANY, description="最大中转次数"),
    sort_by: SortBy = Query(SortBy.CHEAPEST, description="排序方式"),
    language: str = Query("zh", description="语言设置 (zh/en)"),
    currency: str = Query("CNY", description="货币设置 (CNY/USD)"),
    user_preferences: str = Query("", description="用户偏好和要求（如：我想要最便宜的航班、希望直飞、早上出发等）"),
    current_user: Optional[UserInfo] = Depends(get_current_user_optional)
):
    """
    AI增强的航班搜索 - 支持游客和登录用户

    执行差异化搜索策略：
    - 🎯 游客用户：简化搜索（仅Kiwi + AI分析）
    - 🚀 登录用户：完整搜索（Google Flights + Kiwi + AI推荐 + AI分析）

    特点：
    - 🤖 AI智能数据清洗和本地化
    - 🔍 差异化搜索策略
    - 🌐 根据语言设置自动本地化机场名称
    - 📊 去重和数据统一
    """
    try:
        user_display = current_user.username if current_user else "游客"
        logger.info(f"🤖 用户 {user_display} 开始AI增强航班搜索: {departure_code} -> {destination_code}, {depart_date}")

        # 验证必需参数
        if not all([departure_code, destination_code, depart_date]):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail='缺少必需参数：出发机场代码、目的地机场代码、出发日期'
            )

        # 验证机场代码格式
        if len(departure_code) != 3 or len(destination_code) != 3:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail='机场代码必须是3位字母'
            )

        # 验证出发地和目的地不能相同
        if departure_code.upper() == destination_code.upper():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail='出发地和目的地不能相同'
            )

        # 获取AI增强航班搜索服务
        flight_service = AIFlightService()

        # 执行简化的AI增强搜索
        result = await flight_service.search_flights_ai_enhanced(
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
            user_preferences=user_preferences,
            is_guest_user=current_user is None  # 关键：判断是否为游客用户
        )

        logger.info(f"AI增强搜索完成: 成功={result['success']}, 总结果数={result.get('total_count', 0)}")

        # 添加AI处理信息到日志
        ai_processing = result.get('ai_processing', {})
        if ai_processing.get('success'):
            logger.info("✅ AI数据处理成功")
        else:
            logger.warning(f"⚠️ AI数据处理失败: {ai_processing.get('error', 'Unknown error')}")

        return result

    except HTTPException:
        # 重新抛出HTTP异常
        raise
    except Exception as e:
        logger.error(f"AI增强航班搜索失败: {e}")
        return {
            'success': False,
            'error': str(e),
            'flights': [],
            'search_stages': {},
            'ai_processing': {
                'success': False,
                'error': str(e)
            },
            'message': str(e),
            'total_count': 0,
            'search_info': {
                'source': 'ai_enhanced_comprehensive',
                'search_time': '',
                'departure_code': departure_code if 'departure_code' in locals() else 'N/A',
                'destination_code': destination_code if 'destination_code' in locals() else 'N/A',
                'depart_date': depart_date if 'depart_date' in locals() else 'N/A',
                'processing_method': 'failed'
            }
        }


# ==================== 异步搜索接口 ====================

class AsyncTaskResponse(BaseModel):
    """异步任务响应"""
    task_id: str
    status: str
    message: str
    estimated_duration: Optional[int] = None


class TaskStatusResponse(BaseModel):
    """任务状态响应"""
    task_id: str
    status: str
    progress: float
    message: str
    created_at: str
    updated_at: str
    estimated_duration: Optional[int] = None


@router.post("/search/ai-enhanced/async", response_model=APIResponse)
async def start_ai_enhanced_search_async(
    departure_code: str = Query(..., description="出发机场代码", min_length=3, max_length=3),
    destination_code: str = Query(..., description="目的地机场代码", min_length=3, max_length=3),
    depart_date: str = Query(..., description="出发日期(YYYY-MM-DD)"),
    return_date: Optional[str] = Query(None, description="返程日期(YYYY-MM-DD)"),
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
    current_user: Optional[UserInfo] = Depends(get_current_user_optional)
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
        await async_task_service.initialize()

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
            "is_guest_user": current_user is None  # 关键：判断是否为游客用户
        }

        # 创建异步任务
        task_id = await async_task_service.create_task(
            task_type="ai_flight_search",
            search_params=search_params,
            user_id=user_id
        )
        
        # 智能时间预估
        estimated_duration = _estimate_search_time(search_params)

        # 启动后台任务
        asyncio.create_task(
            _execute_ai_search_background(task_id, search_params)
        )

        return APIResponse(
            success=True,
            message="AI搜索任务已提交，请使用任务ID查询进度",
            data={
                "task_id": task_id,
                "status": "PENDING",
                "estimated_duration": estimated_duration,
                "polling_interval": 2  # 建议2秒轮询一次，更加流畅
            }
        )

    except Exception as e:
        logger.error(f"提交异步AI搜索任务失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"提交搜索任务失败: {str(e)}"
        )


@router.get("/task/{task_id}/status", response_model=APIResponse)
async def get_task_status(
    task_id: str,
    current_user: Optional[UserInfo] = Depends(get_current_user_optional)
):
    """
    查询异步任务状态
    """
    try:
        # 初始化异步任务服务
        await async_task_service.initialize()

        # 获取任务信息
        task_info = await async_task_service.get_task_info(task_id)
        logger.info(f"🔍 查询任务信息: {task_id}, 结果: {task_info}")

        if not task_info:
            logger.warning(f"❌ 任务不存在: {task_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="任务不存在"
            )

        # 检查任务所有权（可选）
        # 对于游客用户，跳过权限检查
        if current_user and task_info.get("user_id") != current_user.id:
            # 如果是游客任务，允许访问
            if task_info.get("user_id") != "guest":
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="无权访问此任务"
                )

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
                "estimated_duration": task_info.get("estimated_duration", 120)
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取任务状态失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取任务状态失败: {str(e)}"
        )


@router.get("/task/{task_id}/result", response_model=APIResponse)
async def get_task_result(
    task_id: str,
    current_user: Optional[UserInfo] = Depends(get_current_user_optional)
):
    """
    获取异步任务结果
    """
    try:
        # 初始化异步任务服务
        await async_task_service.initialize()

        # 获取任务信息
        task_info = await async_task_service.get_task_info(task_id)

        if not task_info:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="任务不存在"
            )

        # 检查任务所有权（可选）
        # 对于游客用户，跳过权限检查
        if current_user and task_info.get("user_id") != current_user.id:
            # 如果是游客任务，允许访问
            if task_info.get("user_id") != "guest":
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="无权访问此任务"
                )

        # 检查任务状态
        if task_info["status"] != TaskStatus.COMPLETED.value:
            return APIResponse(
                success=False,
                message=f"任务尚未完成，当前状态: {task_info['status']}",
                data={
                    "task_id": task_id,
                    "status": task_info["status"],
                    "progress": task_info.get("progress", 0),
                    "message": task_info.get("message", "")
                }
            )

        # 获取任务结果
        result = await async_task_service.get_task_result(task_id)

        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="任务结果不存在"
            )

        return APIResponse(
            success=True,
            message="搜索结果获取成功",
            data=result
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取任务结果失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取任务结果失败: {str(e)}"
        )


# ==================== 后台任务执行函数 ====================

def _estimate_search_time(search_params: Dict[str, Any]) -> int:
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
        from datetime import datetime, timedelta
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


def _get_progress_stage(progress: float) -> str:
    """根据进度返回当前阶段"""
    if progress < 0.1:
        return "initialization"
    elif progress < 0.6:
        return "searching"
    elif progress < 0.9:
        return "ai_analysis"
    elif progress < 1.0:
        return "finalizing"
    else:
        return "completed"


def _calculate_remaining_time(progress: float, estimated_total: int) -> int:
    """计算剩余时间（秒）"""
    if progress >= 1.0:
        return 0
    if progress <= 0:
        return estimated_total
    
    # 基于当前进度计算剩余时间
    remaining_ratio = (1.0 - progress)
    remaining_time = int(estimated_total * remaining_ratio)
    
    # 确保剩余时间合理
    return max(5, min(remaining_time, estimated_total))


async def _execute_ai_search_background(task_id: str, search_params: Dict[str, Any]):
    """
    后台执行AI增强搜索 - 增强版进度报告
    """
    try:
        logger.info(f"开始执行后台AI搜索任务: {task_id}")

        # 阶段1: 初始化 (0-10%)
        await async_task_service.update_task_status(
            task_id,
            TaskStatus.PROCESSING,
            progress=0.05,
            message="正在初始化搜索引擎..."
        )
        
        await asyncio.sleep(0.5)  # 让前端看到进度变化
        
        await async_task_service.update_task_status(
            task_id,
            TaskStatus.PROCESSING,
            progress=0.1,
            message="正在连接航空公司数据库..."
        )

        # 创建AI搜索服务实例
        flight_service = AIFlightService()

        # 阶段2: 数据收集 (10-60%)
        await async_task_service.update_task_status(
            task_id,
            TaskStatus.PROCESSING,
            progress=0.15,
            message="正在搜索基础航班数据..."
        )
        
        # 模拟搜索过程中的进度更新
        search_stages = [
            (0.25, "正在查询主要航空公司..."),
            (0.35, "正在查询廉价航空公司..."),
            (0.45, "正在搜索隐藏城市机会..."),
            (0.55, "正在收集价格信息...")
        ]
        
        for progress, message in search_stages:
            await async_task_service.update_task_status(
                task_id,
                TaskStatus.PROCESSING,
                progress=progress,
                message=message
            )
            await asyncio.sleep(0.3)  # 短暂延迟显示进度

        # 阶段3: AI分析 (60-90%)
        await async_task_service.update_task_status(
            task_id,
            TaskStatus.PROCESSING,
            progress=0.60,
            message="正在进行AI数据分析..."
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
            is_guest_user=search_params.get("is_guest_user", False)
        )

        # 阶段4: 结果处理 (90-100%)
        await async_task_service.update_task_status(
            task_id,
            TaskStatus.PROCESSING,
            progress=0.85,
            message="正在生成个性化推荐..."
        )
        
        await asyncio.sleep(0.2)
        
        await async_task_service.update_task_status(
            task_id,
            TaskStatus.PROCESSING,
            progress=0.95,
            message="正在最终确认结果..."
        )

        # 保存搜索结果
        await async_task_service.save_task_result(task_id, result)

        # 更新任务状态为完成
        await async_task_service.update_task_status(
            task_id,
            TaskStatus.COMPLETED,
            progress=1.0,
            message="搜索完成"
        )

        logger.info(f"后台AI搜索任务完成: {task_id}, 找到 {len(result.get('flights', []))} 个航班")

    except Exception as e:
        logger.error(f"后台AI搜索任务失败 {task_id}: {e}")

        # 更新任务状态为失败
        await async_task_service.update_task_status(
            task_id,
            TaskStatus.FAILED,
            progress=0,
            message="搜索失败",
            error=str(e)
        )


# ==================== SSE 实时推送端点 ====================

@router.get("/task/{task_id}/stream")
async def stream_task_status(
    task_id: str,
    current_user: Optional[UserInfo] = Depends(get_current_user_optional)
):
    """
    SSE实时推送任务状态
    支持游客访问，实时推送任务进度和结果
    """

    async def generate_sse_stream():
        """生成SSE数据流"""
        try:
            logger.info(f"🔄 开始SSE推送任务状态: {task_id}")

            # 检查任务是否存在
            task_info = await async_task_service.get_task_info(task_id)
            if not task_info:
                # 发送错误事件并立即关闭连接
                error_data = {
                    "status": "TASK_NOT_FOUND",
                    "message": "任务不存在或已过期",
                    "error_code": "TASK_NOT_FOUND",
                    "task_id": task_id,
                    "final": True  # 明确标记这是最终消息
                }
                logger.warning(f"⚠️ SSE任务不存在: {task_id}")
                yield f"data: {json.dumps(error_data, ensure_ascii=False)}\n\n"
                # 发送明确的终止事件
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
                        "final": True
                    }
                    yield f"data: {json.dumps(error_data, ensure_ascii=False)}\n\n"
                    yield f"event: error\ndata: {json.dumps({'error': 'ACCESS_DENIED', 'final': True}, ensure_ascii=False)}\n\n"
                    yield f"event: close\ndata: {json.dumps({'message': '权限不足，连接关闭', 'final': True}, ensure_ascii=False)}\n\n"
                    return

            # 发送初始状态
            initial_status = task_info.get("status", "PENDING")
            initial_progress = task_info.get("progress", 0)
            initial_data = {
                "status": initial_status,
                "progress": initial_progress,
                "message": task_info.get("message", ""),
                "task_id": task_id,
                "created_at": task_info.get("created_at"),
                "updated_at": task_info.get("updated_at"),
                "estimated_duration": task_info.get("estimated_duration", _estimate_search_time({})),
                "reconnected": True if "last_event_id" in locals() else False  # 标记是否为重连
            }

            logger.info(f"📤 SSE发送初始状态: {task_id} -> {initial_status} ({initial_progress}%)")
            yield f"data: {json.dumps(initial_data, ensure_ascii=False)}\n\n"

            # 如果任务已完成，发送结果并结束
            if initial_status == "COMPLETED":
                try:
                    result = await async_task_service.get_task_result(task_id)
                    if result:
                        # 简化：直接发送后端原始数据结构，让前端处理
                        result_data = {
                            "status": "COMPLETED",
                            "progress": 100,
                            "message": "任务完成",
                            "task_id": task_id,
                            "result": result,  # 直接发送原始结果，让前端处理数据结构
                            "final": True  # 明确标记为最终消息
                        }
                        logger.info(f"📤 SSE发送完成结果: {task_id}")
                        logger.info(f"📊 结果包含: {len(result.get('flights', []))} 个航班, AI报告长度: {len(result.get('ai_analysis_report', ''))}")
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
                    "final": True
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
                        timeout_data = {
                            "status": "TIMEOUT",
                            "message": "任务超时",
                            "task_id": task_id,
                            "final": True
                        }
                        yield f"data: {json.dumps(timeout_data, ensure_ascii=False)}\n\n"
                        yield f"event: error\ndata: {json.dumps({'error': 'TIMEOUT', 'final': True}, ensure_ascii=False)}\n\n"
                        yield f"event: close\ndata: {json.dumps({'message': '任务超时，连接关闭', 'final': True}, ensure_ascii=False)}\n\n"
                        break

                    # 获取最新任务状态
                    current_task_info = await async_task_service.get_task_info(task_id)
                    if not current_task_info:
                        # 任务在轮询过程中被删除
                        error_data = {
                            "status": "TASK_NOT_FOUND",
                            "message": "任务已被删除或过期",
                            "task_id": task_id,
                            "final": True
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
                        current_status != last_status or
                        current_progress != last_progress or
                        current_updated != last_updated
                    )

                    if status_changed:
                        # 发送状态更新
                        update_data = {
                            "status": current_status,
                            "progress": current_progress,
                            "message": current_message,
                            "task_id": task_id,
                            "updated_at": current_updated,
                            "stage": _get_progress_stage(current_progress),  # 添加阶段信息
                            "estimated_remaining": _calculate_remaining_time(current_progress, task_info.get("estimated_duration", 60))
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
                            result = await async_task_service.get_task_result(task_id)
                            if result:
                                # 简化：直接发送后端原始数据结构，让前端处理
                                result_data = {
                                    "status": "COMPLETED",
                                    "progress": 100,
                                    "message": "任务完成",
                                    "task_id": task_id,
                                    "result": result,  # 直接发送原始结果，让前端处理数据结构
                                    "final": True
                                }
                                logger.info(f"📤 SSE发送最终结果: {task_id}")
                                logger.info(f"📊 结果包含: {len(result.get('flights', []))} 个航班, AI报告长度: {len(result.get('ai_analysis_report', ''))}")
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
                            "final": True
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
                    error_data = {
                        "status": "ERROR",
                        "message": f"推送过程中出错: {str(e)}",
                        "task_id": task_id
                    }
                    yield f"data: {json.dumps(error_data, ensure_ascii=False)}\n\n"
                    break

            logger.info(f"🔚 SSE推送结束: {task_id}")

        except Exception as e:
            logger.error(f"❌ SSE流生成失败: {e}")
            error_data = {
                "status": "ERROR",
                "message": f"服务器内部错误: {str(e)}",
                "task_id": task_id
            }
            yield f"data: {json.dumps(error_data, ensure_ascii=False)}\n\n"

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
        }
    )
