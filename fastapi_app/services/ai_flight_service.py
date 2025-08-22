"""
AI增强航班搜索服务
专注于：
1. AI增强的三阶段航班搜索
2. Google Flights + Kiwi + AI推荐
3. 智能数据分析和Markdown展示
4. 用户个性化搜索体验
"""

import asyncio
from typing import List, Dict, Any, Optional
from loguru import logger
from datetime import datetime
current_platform = __import__("platform").system()

# 检查smart-flights库是否可用
try:
    # SSL修复已在文件开头完成，这里只记录日志
    logger.info(f"🖥️ 检测到操作系统: {current_platform}")
    if current_platform == "Windows":
        logger.info("🔧 Windows环境：SSL修复已在模块导入时完成")
    else:
        logger.info(f"🔒 {current_platform}环境：保持正常SSL验证，不禁用证书检查")

    # 现在导入smart-flights
    from fli.search import SearchFlights
    from fli.models import (
        FlightSearchFilters, FlightSegment, Airport,
        PassengerInfo, SeatType, MaxStops, SortBy, TripType
    )
    from fli.models.google_flights.base import LocalizationConfig, Language, Currency

    SMART_FLIGHTS_AVAILABLE = True
    logger.info("smart-flights服务可用")
except ImportError as e:
    SMART_FLIGHTS_AVAILABLE = False
    logger.warning(f"smart-flights库不可用: {e}")
except Exception as e:
    SMART_FLIGHTS_AVAILABLE = False
    logger.warning(f"smart-flights初始化失败: {e}")


class AIFlightService:
    """AI增强航班搜索服务 - 专注于智能搜索和AI数据处理"""
    
    def __init__(self):
        self.stats = {
            'total_requests': 0,
            'successful_requests': 0,
            'cache_hits': 0,
            'cache_misses': 0
        }
        logger.info("AIFlightService初始化成功")

    async def search_flights_ai_enhanced(
        self,
        departure_code: str,
        destination_code: str,
        depart_date: str,
        return_date: str = None,
        adults: int = 1,
        seat_class: str = "ECONOMY",
        children: int = 0,
        infants_in_seat: int = 0,
        infants_on_lap: int = 0,
        max_stops: str = "ANY",
        sort_by: str = "CHEAPEST",
        language: str = "zh",
        currency: str = "CNY",
        user_preferences: str = ""
    ) -> dict:
        """
        AI增强航班搜索：
        1. 收集三阶段原始数据
        2. 交给AI处理
        3. 返回Markdown报告
        """
        try:
            logger.info(f"🚀 开始AI增强航班搜索: {departure_code} → {destination_code}, {depart_date}")

            # 根据行程类型决定搜索阶段
            is_roundtrip = return_date is not None

            if is_roundtrip:
                # 往返航班：只执行前两个阶段（Google Flights + Kiwi）
                logger.info("🚀 开始并行执行两阶段搜索（往返航班）")

                tasks = [
                    # 阶段1: 获取Google Flights原始数据
                    self._get_google_raw_data(
                        departure_code, destination_code, depart_date, return_date,
                        adults, seat_class, children, infants_in_seat, infants_on_lap,
                        max_stops, sort_by, language, currency
                    ),
                    # 阶段2: 获取Kiwi航班原始数据（包含隐藏城市和常规航班）
                    self._get_kiwi_raw_data(
                        departure_code, destination_code, depart_date, return_date, adults, seat_class, language, currency
                    )
                ]

                # 并行执行两个搜索任务
                google_flights_raw, kiwi_flights_raw = await asyncio.gather(*tasks)
                ai_flights_raw = []  # 往返航班不使用AI推荐隐藏城市

                logger.info(f"两阶段原始数据收集完成: Google({len(google_flights_raw)}), Kiwi({len(kiwi_flights_raw)})")
            else:
                # 单程航班：执行完整的三阶段搜索
                logger.info("🚀 开始并行执行三阶段搜索（单程航班）")

                tasks = [
                    # 阶段1: 获取Google Flights原始数据
                    self._get_google_raw_data(
                        departure_code, destination_code, depart_date, return_date,
                        adults, seat_class, children, infants_in_seat, infants_on_lap,
                        max_stops, sort_by, language, currency
                    ),
                    # 阶段2: 获取Kiwi航班原始数据（包含隐藏城市和常规航班）
                    self._get_kiwi_raw_data(
                        departure_code, destination_code, depart_date, return_date, adults, seat_class, language, currency
                    ),
                    # 阶段3: 获取AI推荐的隐藏城市原始数据
                    self._get_ai_hidden_raw_data(
                        departure_code, destination_code, depart_date, return_date, adults, seat_class, language, currency
                    )
                ]

                # 并行执行所有搜索任务
                google_flights_raw, kiwi_flights_raw, ai_flights_raw = await asyncio.gather(*tasks)

            # 交给AI处理
            logger.info("🤖 将原始数据交给AI处理")
            ai_processed_result = await self._process_flights_with_ai(
                google_flights=google_flights_raw,
                kiwi_flights=kiwi_flights_raw,
                ai_flights=ai_flights_raw,
                language=language,
                departure_code=departure_code,
                destination_code=destination_code,
                user_preferences=user_preferences
            )

            if ai_processed_result['success']:
                logger.info("✅ AI处理成功，生成详细分析报告")
                return {
                    'success': True,
                    'data': {'itineraries': []},  # 不返回原始航班数据
                    'flights': [],  # 用户只需查看AI分析报告
                    'ai_analysis_report': ai_processed_result.get('ai_analysis_report', ''),
                    'ai_processing': {
                        'success': True,
                        'summary': ai_processed_result.get('summary', {}),
                        'processing_info': ai_processed_result.get('processing_info', {})
                    },
                    'total_count': 0,  # 不计算原始航班数量
                    'search_info': {
                        'source': 'ai_enhanced',
                        'search_time': datetime.now().isoformat(),
                        'departure_code': departure_code,
                        'destination_code': destination_code,
                        'processing_method': 'ai_markdown_only'
                    }
                }
            else:
                logger.error(f"AI处理失败: {ai_processed_result.get('error', '未知错误')}")
                return {
                    'success': False,
                    'error': ai_processed_result.get('error', 'AI处理失败'),
                    'data': {'itineraries': []},
                    'flights': [],
                    'ai_analysis_report': '',
                    'total_count': 0
                }

        except Exception as e:
            logger.error(f"AI增强航班搜索失败: {e}")
            return {
                'success': False,
                'error': str(e),
                'data': {'itineraries': []},
                'flights': [],
                'ai_analysis_report': '',
                'total_count': 0
            }

    async def _get_google_raw_data(
        self,
        departure_code: str,
        destination_code: str,
        depart_date: str,
        return_date: str = None,
        adults: int = 1,
        seat_class: str = "ECONOMY",
        children: int = 0,
        infants_in_seat: int = 0,
        infants_on_lap: int = 0,
        max_stops: str = "ANY",
        sort_by: str = "CHEAPEST",
        language: str = "zh",
        currency: str = "CNY"
    ) -> list:
        """获取Google Flights原始数据"""
        try:
            logger.info(f"获取常规搜索原始数据: {departure_code} → {destination_code}")

            if not SMART_FLIGHTS_AVAILABLE:
                logger.warning("smart-flights库不可用")
                return []

            # 在线程池中执行同步搜索
            loop = asyncio.get_event_loop()
            results = await loop.run_in_executor(
                None,
                self._sync_search_google,
                departure_code, destination_code, depart_date, return_date,
                adults, seat_class, children, infants_in_seat, infants_on_lap,
                max_stops, sort_by, language, currency
            )

            # 过滤掉价格为0的航班数据
            filtered_results = self._filter_valid_price_flights(results, source="常规搜索")

            logger.info(f"获取常规搜索原始数据完成: {len(results)} 条记录")
            if len(filtered_results) < len(results):
                logger.info(f"🔧 过滤掉价格为0的航班: {len(results) - len(filtered_results)} 条，剩余: {len(filtered_results)} 条")

            return filtered_results

        except Exception as e:
            logger.error(f"获取常规搜索原始数据失败: {e}")
            return []

    def _filter_valid_price_flights(self, flights: list, source: str = "Unknown") -> list:
        """
        过滤掉价格为0或无效的航班数据
        TODO: 与监控服务的价格提取逻辑统一，抽到 utils/price.py，避免重复实现。

        Args:
            flights: 原始航班数据列表
            source: 数据源名称，用于日志记录

        Returns:
            list: 过滤后的有效航班数据列表
        """
        if not flights:
            return []

        valid_flights = []

        for flight in flights:
            try:
                # 检查价格字段
                price = None

                # 尝试不同的价格字段名称
                if isinstance(flight, dict):
                    price = flight.get('price') or flight.get('total_price') or flight.get('cost')
                else:
                    # 如果是对象，尝试获取price属性
                    price = getattr(flight, 'price', None) or getattr(flight, 'total_price', None) or getattr(flight, 'cost', None)

                # 转换价格为数值
                if price is not None:
                    if isinstance(price, str):
                        # 移除货币符号和逗号，提取数字
                        import re
                        price_str = re.sub(r'[^\d.]', '', price)
                        if price_str:
                            price = float(price_str)
                        else:
                            price = 0.0
                    elif isinstance(price, (int, float)):
                        price = float(price)
                    else:
                        price = 0.0
                else:
                    price = 0.0

                # 只保留价格大于0的航班
                if price > 0:
                    valid_flights.append(flight)

            except Exception as e:
                # 如果处理单个航班时出错，记录警告但继续处理其他航班
                logger.warning(f"处理航班价格时出错: {e}, 跳过该航班")
                continue

        return valid_flights

    async def _get_kiwi_raw_data(
        self,
        departure_code: str,
        destination_code: str,
        depart_date: str,
        return_date: str = None,
        adults: int = 1,
        seat_class: str = "ECONOMY",
        language: str = "zh",
        currency: str = "CNY"
    ) -> list:
        """获取Kiwi航班原始数据（包含隐藏城市和常规航班）"""
        try:
            trip_type = "往返" if return_date else "单程"
            logger.info(f"🔍 [隐藏城市数据获取] 开始: {departure_code} → {destination_code} ({trip_type}, {seat_class})")

            if not SMART_FLIGHTS_AVAILABLE:
                logger.warning("smart-flights库不可用")
                return []

            # 在线程池中执行同步搜索
            loop = asyncio.get_event_loop()
            results = await loop.run_in_executor(
                None,
                self._sync_search_kiwi,
                departure_code, destination_code, depart_date, adults, language, currency, seat_class, return_date
            )

            # 【增强日志】记录原始返回数据的详细信息
            logger.info(f"🔍 [隐藏城市数据获取] 原始返回数据类型: {type(results)}")
            if results:
                logger.info(f"🔍 [隐藏城市数据获取] 原始数据长度: {len(results) if isinstance(results, (list, dict)) else 'N/A'}")
                # 记录第一条数据的结构（用于调试）
                if isinstance(results, list) and results:
                    first_item = results[0]
                    logger.info(f"🔍 [隐藏城市数据获取] 第一条数据类型: {type(first_item)}")
                    logger.info(f"🔍 [隐藏城市数据获取] 第一条数据预览: {str(first_item)[:300]}...")
                elif isinstance(results, dict):
                    logger.info(f"🔍 [隐藏城市数据获取] 字典键: {list(results.keys())}")
                    if 'results' in results:
                        flights_data = results['results'].get('flights', [])
                        if flights_data:
                            logger.info(f"🔍 [隐藏城市数据获取] 嵌套航班数据第一条: {str(flights_data[0])[:300]}...")
            else:
                logger.warning("🔍 [隐藏城市数据获取] 返回数据为空")

            # 处理KiwiFlightsAPI返回的数据格式 - 优化版本
            processed_data = []
            if isinstance(results, list):
                # KiwiFlightsAPI直接返回航班列表
                processed_data = results
                flight_count = len(results)
                logger.info(f"✅ [Kiwi数据获取] 处理完成 - 直接列表格式: {flight_count} 个航班")
            elif isinstance(results, dict):
                # 处理字典格式响应
                if 'flights' in results:
                    # 新格式：直接包含flights字段
                    flights_data = results.get('flights', [])
                    processed_data = flights_data
                    flight_count = len(flights_data)

                    # 记录额外的统计信息
                    total_count = results.get('total_count', flight_count)
                    hidden_count = results.get('hidden_city_count', 0)
                    logger.info(f"✅ [Kiwi数据获取] 处理完成 - 新字典格式: {flight_count} 个航班")
                    logger.info(f"📊 [Kiwi数据获取] 统计信息: 总数={total_count}, 隐藏城市={hidden_count}")

                elif 'results' in results:
                    # 兼容旧格式：从API响应中提取实际的航班数据
                    flights_data = results['results'].get('flights', [])
                    processed_data = flights_data
                    flight_count = len(flights_data)
                    logger.info(f"✅ [Kiwi数据获取] 处理完成 - 旧嵌套字典格式: {flight_count} 个航班")
                else:
                    logger.warning(f"⚠️ [Kiwi数据获取] 字典格式无flights字段: {list(results.keys())}")
                    return []
            else:
                logger.warning(f"⚠️ [Kiwi数据获取] API响应格式异常: {type(results)}")
                return []

            # 【增强日志】记录处理后数据的详细信息
            if processed_data:
                logger.info(f"🔍 [Kiwi数据获取] 处理后数据类型: {type(processed_data)}")
                logger.info(f"🔍 [Kiwi数据获取] 处理后数据长度: {len(processed_data)}")
                # 检查数据的JSON序列化能力
                try:
                    import json
                    # 尝试序列化第一条数据
                    if processed_data:
                        json_test = json.dumps(processed_data[0], default=str, ensure_ascii=False)
                        logger.info(f"✅ [Kiwi数据获取] JSON序列化测试成功，长度: {len(json_test)}")
                        logger.info(f"🔍 [Kiwi数据获取] JSON预览: {json_test[:200]}...")
                except Exception as json_error:
                    logger.error(f"❌ [Kiwi数据获取] JSON序列化测试失败: {json_error}")
                    logger.info(f"🔍 [Kiwi数据获取] 问题数据结构: {str(processed_data[0])[:300]}...")

            return processed_data

        except Exception as e:
            logger.error(f"❌ [Kiwi数据获取] 获取失败: {e}")
            import traceback
            logger.error(f"❌ [Kiwi数据获取] 错误堆栈: {traceback.format_exc()}")
            return []

    async def _get_ai_hidden_raw_data(
        self,
        departure_code: str,
        destination_code: str,
        depart_date: str,
        return_date: str = None,
        adults: int = 1,
        seat_class: str = "ECONOMY",
        language: str = "zh",
        currency: str = "CNY"
    ) -> list:
        """获取AI推荐的隐藏城市原始数据"""
        try:
            logger.info(f"获取AI推荐隐藏城市原始数据: {departure_code} → {destination_code}")

            # 使用AI推荐隐藏目的地

            # AI推荐隐藏目的地 - 使用优化的英文提示词，返回城市代码
            ai_prompt = f"""
# Persona
You are an expert-level travel hacker and an airline route network and pricing analyst.

# Task Context
I am planning to use a strategy known as "Hidden City Ticketing" or "Skiplagging." My true destination is {destination_code}, but I intend to book a ticket to a farther destination that has a layover in {destination_code}. I will end my journey at the layover and forfeit the final leg of the flight.

# Core Insight
You must strictly follow this key principle: The most successful Skiplagging opportunities involve using a major international or domestic hub (my true destination, {destination_code}) as a layover point for a flight to another major city or popular destination **within the same country**. Therefore, the majority of the cities you suggest must be major domestic cities in the same country as {destination_code}.

# User Information
- Departure Airport: {departure_code}
- True Destination (The Layover City): {destination_code}
- Departure Date: {depart_date}

# Chain of Thought
1. **Identify Hub Status:** Analyze {destination_code} as a major airline hub. Identify which key airlines (especially members of Oneworld, Star Alliance, and SkyTeam) use this airport as a critical hub for both domestic and international connections.
2. **Find Domestic Spoke Routes:** Strictly following the [Core Insight], search for high-frequency, high-capacity routes from {departure_code} to other major cities **within the same country as {departure_code}** that could potentially have connections through {destination_code}.
3. **Assess Domestic Market Competition:** Prioritize final destinations where there is intense competition for flights from {departure_code}. The presence of multiple airlines and routes is a strong indicator. Intense competition for the entire journey from {departure_code} to this final destination is what makes the Skiplagging ticket cheaper.
4. **Filter and Finalize:** Select the 10 most promising cities from the candidate list. Double-check that these suggestions are primarily major domestic cities in popular business or tourist destinations within the same country as {departure_code}.

# Output Requirements
- Strictly return 10 unique, 3-letter IATA city codes (not airport codes).
- The suggested cities must primarily be domestic cities in the same country as {destination_code}.
- Do not include the departure city or destination city in the output.
- Return only the city codes, separated by commas, with no additional text, explanations, or headers.
- Example Format: NYC,LAX,CHI,MIA,DFW,ATL,SEA,DEN,PHX,LAS
- Note: Use city codes like NYC (New York), LAX (Los Angeles), CHI (Chicago), not airport codes like JFK, LGA, EWR
            """

            # AI推荐隐藏目的地使用快速模型（小数据量）
            ai_response = await self._call_ai_api(ai_prompt, "gemini-2.5-flash")
            hidden_destinations = []

            if ai_response.get('success') and ai_response.get('content'):
                content = ai_response['content'].strip()
                # 提取城市代码
                import re
                city_codes = re.findall(r'\b[A-Z]{3}\b', content)
                hidden_destinations = city_codes[:10]  # 扩展到10个
                logger.info(f"AI推荐的隐藏城市: {hidden_destinations}")

            raw_data = []
            # 为每个隐藏城市搜索经过目标城市中转的航班
            for i, hidden_dest in enumerate(hidden_destinations[:10], 1):  # 处理最多10个
                try:
                    logger.debug(f"搜索 {departure_code} → {hidden_dest} ({i}/{len(hidden_destinations)})，指定经过 {destination_code} 中转")
                    loop = asyncio.get_event_loop()
                    hidden_flights = await loop.run_in_executor(
                        None,
                        self._sync_search_with_layover,
                        departure_code, hidden_dest, destination_code, depart_date,
                        adults, language, currency, seat_class
                    )
                    if hidden_flights:
                        # 为AI推荐的隐藏城市航班添加标记
                        for flight in hidden_flights:
                            if hasattr(flight, 'hidden_city_info'):
                                flight.hidden_city_info = {
                                    'is_hidden_city': True,
                                    'hidden_destination_code': hidden_dest,
                                    'target_destination_code': destination_code,
                                    'ai_recommended': True,
                                    'search_method': 'layover_restriction'
                                }
                            elif isinstance(flight, dict):
                                flight['hidden_city_info'] = {
                                    'is_hidden_city': True,
                                    'hidden_destination_code': hidden_dest,
                                    'target_destination_code': destination_code,
                                    'ai_recommended': True,
                                    'search_method': 'layover_restriction'
                                }
                        raw_data.extend(hidden_flights)
                        logger.info(f"✅ 找到经过 {destination_code} 中转到 {hidden_dest} 的航班: {len(hidden_flights)} 个")
                    else:
                        logger.debug(f"❌ 未找到经过 {destination_code} 中转到 {hidden_dest} 的航班")
                except Exception as e:
                    logger.error(f"搜索经过 {destination_code} 中转到 {hidden_dest} 失败: {e}")
                    continue

            # 过滤掉价格为0的航班数据（第3阶段需要价格过滤）
            filtered_results = self._filter_valid_price_flights(raw_data, source="AI推荐")

            logger.info(f"获取AI推荐隐藏城市原始数据完成: {len(raw_data)} 条记录")
            if len(filtered_results) < len(raw_data):
                logger.info(f"🔧 过滤掉价格为0的航班: {len(raw_data) - len(filtered_results)} 条，剩余: {len(filtered_results)} 条")

            # 直接返回过滤后的结果，不在这里排序和限制数量
            # 最终的排序和数量限制将在所有数据源合并后统一处理
            logger.info(f"✅ AI推荐航班收集完成: {len(filtered_results)} 条（将在最终合并时统一排序和限制）")
            return filtered_results

        except Exception as e:
            logger.error(f"获取AI推荐隐藏城市原始数据失败: {e}")
            return []

    def _sync_search_google(self, departure_code: str, destination_code: str, depart_date: str,
                          return_date: str = None, adults: int = 1, seat_class: str = "ECONOMY",
                          children: int = 0, infants_in_seat: int = 0, infants_on_lap: int = 0,
                          max_stops: str = "ANY", sort_by: str = "CHEAPEST",
                          language: str = "zh", currency: str = "CNY") -> list:
        """同步执行Google Flights搜索"""
        try:
            if not SMART_FLIGHTS_AVAILABLE:
                return []

            # 创建本地化配置 - 语言和货币根据前端参数动态设置（新版本不支持region参数）
            localization_config = LocalizationConfig(
                language=Language.CHINESE if language == "zh" else Language.ENGLISH,
                currency=Currency.CNY if currency == "CNY" else Currency.USD
            )

            # 创建乘客信息
            passenger_info = PassengerInfo(
                adults=adults,
                children=children,
                infants_in_seat=infants_in_seat,
                infants_on_lap=infants_on_lap
            )

            # 创建航班段 - 使用机场枚举
            try:
                departure_airport = getattr(Airport, departure_code)
                destination_airport = getattr(Airport, destination_code)
            except AttributeError as e:
                logger.error(f"机场代码不支持: {e}")
                return []

            flight_segments = [
                FlightSegment(
                    departure_airport=[[departure_airport, 0]],
                    arrival_airport=[[destination_airport, 0]],
                    travel_date=depart_date
                )
            ]

            if return_date:
                flight_segments.append(
                    FlightSegment(
                        departure_airport=[[destination_airport, 0]],
                        arrival_airport=[[departure_airport, 0]],
                        travel_date=return_date
                    )
                )

            # 根据舱位类型映射到SeatType枚举
            seat_type_mapping = {
                "ECONOMY": SeatType.ECONOMY,
                "PREMIUM_ECONOMY": SeatType.PREMIUM_ECONOMY,
                "BUSINESS": SeatType.BUSINESS,
                "FIRST": SeatType.FIRST
            }
            seat_type = seat_type_mapping.get(seat_class, SeatType.ECONOMY)

            # 根据最大中转次数映射到MaxStops枚举
            max_stops_mapping = {
                "ANY": MaxStops.ANY,
                "NON_STOP": MaxStops.NON_STOP,
                "ONE_STOP_OR_FEWER": MaxStops.ONE_STOP_OR_FEWER,
                "TWO_OR_FEWER_STOPS": MaxStops.TWO_OR_FEWER_STOPS
            }
            max_stops_enum = max_stops_mapping.get(max_stops, MaxStops.ANY)

            # 根据排序方式映射到SortBy枚举
            sort_by_mapping = {
                "BEST": SortBy.TOP_FLIGHTS,  # 将BEST映射到TOP_FLIGHTS
                "CHEAPEST": SortBy.CHEAPEST,
                "DURATION": SortBy.DURATION,
                "DEPARTURE_TIME": SortBy.DEPARTURE_TIME,
                "ARRIVAL_TIME": SortBy.ARRIVAL_TIME,
                "TOP_FLIGHTS": SortBy.TOP_FLIGHTS
            }
            sort_by_enum = sort_by_mapping.get(sort_by, SortBy.CHEAPEST)

            # 创建搜索过滤器
            filters = FlightSearchFilters(
                trip_type=TripType.ROUND_TRIP if return_date else TripType.ONE_WAY,
                passenger_info=passenger_info,
                flight_segments=flight_segments,
                seat_type=seat_type,
                stops=max_stops_enum,
                sort_by=sort_by_enum
            )

            # 根据行程类型设置不同的top_n值
            # 往返航班：50个（数据量控制），单程航班：135个（更多选择）
            top_n = 50 if return_date else 135
            trip_type_desc = "往返" if return_date else "单程"

            # 执行扩展搜索
            search_client = SearchFlights(localization_config=localization_config)
            results = search_client.search_extended(filters, top_n=top_n)

            if results:
                logger.info(f"✅ Google Flights{trip_type_desc}搜索成功: {len(results)} 个航班 (top_n={top_n})")
            else:
                logger.warning(f"⚠️ Google Flights{trip_type_desc}搜索未返回结果")

            return results or []

        except Exception as e:
            logger.error(f"Google Flights搜索失败: {e}")
            return []

    def _sync_search_kiwi(self, departure_code: str, destination_code: str, depart_date: str,
                         adults: int = 1, language: str = "zh", currency: str = "CNY",
                         seat_class: str = "ECONOMY", return_date: str = None) -> list:
        """同步执行Kiwi航班搜索 - 正确处理API响应格式"""
        try:
            if not SMART_FLIGHTS_AVAILABLE:
                return []

            logger.info(f"🔍 [Kiwi搜索] 开始: {departure_code} → {destination_code}")

            # 使用经过测试验证的KiwiFlightsAPI
            from fli.api.kiwi_flights import KiwiFlightsAPI

            all_results = []

            # 1. 搜索普通航班 (hidden_city_only=False)
            try:
                api_regular = KiwiFlightsAPI()

                import asyncio
                try:
                    loop = asyncio.get_event_loop()
                    regular_response = loop.run_until_complete(
                        api_regular.search_oneway_hidden_city(
                            origin=departure_code,
                            destination=destination_code,
                            departure_date=depart_date,
                            adults=adults,
                            limit=25,
                            cabin_class=seat_class,  # 🔧 修复：传递舱位参数
                            hidden_city_only=False  # 获取普通航班
                        )
                    )
                except RuntimeError:
                    # 如果没有事件循环，创建新的
                    regular_response = asyncio.run(
                        api_regular.search_oneway_hidden_city(
                            origin=departure_code,
                            destination=destination_code,
                            departure_date=depart_date,
                            adults=adults,
                            limit=25,
                            cabin_class=seat_class,  # 🔧 修复：传递舱位参数
                            hidden_city_only=False  # 获取普通航班
                        )
                    )

                # 【修复】正确处理API响应格式
                logger.info(f"🔍 [Kiwi搜索] 普通航班API响应: {type(regular_response)}")
                if isinstance(regular_response, dict) and regular_response.get('success'):
                    regular_flights = regular_response.get('flights', [])
                    logger.info(f"✅ [Kiwi搜索] 普通航班: {len(regular_flights)} 条")
                    all_results.extend(regular_flights)
                else:
                    logger.warning(f"⚠️ [Kiwi搜索] 普通航班搜索失败或无结果: {regular_response}")
                    regular_flights = []

            except Exception as e:
                logger.error(f"❌ [Kiwi搜索] 普通航班搜索失败: {e}")
                regular_flights = []

            # 2. 搜索隐藏城市航班 (hidden_city_only=True)
            try:
                api_hidden = KiwiFlightsAPI()

                import asyncio
                try:
                    loop = asyncio.get_event_loop()
                    hidden_response = loop.run_until_complete(
                        api_hidden.search_oneway_hidden_city(
                            origin=departure_code,
                            destination=destination_code,
                            departure_date=depart_date,
                            adults=adults,
                            limit=25,
                            cabin_class=seat_class,  # 🔧 修复：传递舱位参数
                            hidden_city_only=True   # 获取隐藏城市航班
                        )
                    )
                except RuntimeError:
                    # 如果没有事件循环，创建新的
                    hidden_response = asyncio.run(
                        api_hidden.search_oneway_hidden_city(
                            origin=departure_code,
                            destination=destination_code,
                            departure_date=depart_date,
                            adults=adults,
                            limit=25,
                            cabin_class=seat_class,  # 🔧 修复：传递舱位参数
                            hidden_city_only=True   # 获取隐藏城市航班
                        )
                    )

                # 【修复】正确处理API响应格式
                logger.info(f"🔍 [Kiwi搜索] 隐藏城市API响应: {type(hidden_response)}")
                if isinstance(hidden_response, dict) and hidden_response.get('success'):
                    hidden_flights = hidden_response.get('flights', [])
                    logger.info(f"✅ [Kiwi搜索] 隐藏城市航班: {len(hidden_flights)} 条")
                    all_results.extend(hidden_flights)
                else:
                    logger.warning(f"⚠️ [Kiwi搜索] 隐藏城市搜索失败或无结果: {hidden_response}")
                    hidden_flights = []

            except Exception as e:
                logger.error(f"❌ [Kiwi搜索] 隐藏城市航班搜索失败: {e}")
                hidden_flights = []

            # 处理搜索结果
            if not all_results:
                # 如果没有找到航班，返回状态信息
                logger.info(f"ℹ️ [Kiwi搜索] 未找到航班，返回状态信息")
                status_info = {
                    'id': 'kiwi_no_flights',
                    'source': 'kiwi_flights_api',
                    'status': 'no_flights_found',
                    'message': f'Kiwi搜索 {departure_code} → {destination_code} 未找到航班（可能是日期太远或航线无数据）',
                    'search_params': {
                        'origin': departure_code,
                        'destination': destination_code,
                        'departure_date': depart_date,
                        'adults': adults,
                        'seat_class': seat_class
                    },
                    'is_hidden_city': False,
                    'flight_type': 'no_flights',
                    'api_status': 'success_but_empty'
                }
                return [status_info]

            # 转换航班数据格式并添加标识 - 优化版本
            processed_results = []
            regular_count = len(regular_flights) if 'regular_flights' in locals() else 0

            for i, flight in enumerate(all_results):
                # 确保航班数据是字典格式
                if isinstance(flight, dict):
                    # 使用优化的数据转换方法
                    flight_dict = self._optimize_kiwi_flight_data(flight.copy())
                else:
                    flight_dict = {
                        'id': f'kiwi_{i}',
                        'raw_data': str(flight),
                        'source': 'kiwi_flights_api'
                    }

                # 添加隐藏城市标识 - 使用API原生字段
                original_is_hidden = flight_dict.get('is_hidden_city', False)
                if i < regular_count:
                    flight_dict['is_hidden_city'] = original_is_hidden
                    flight_dict['flight_type'] = 'hidden_city' if original_is_hidden else 'regular'
                else:
                    flight_dict['is_hidden_city'] = True  # 隐藏城市搜索结果
                    flight_dict['flight_type'] = 'hidden_city'

                # 确保有source标识
                flight_dict['source'] = 'kiwi_flights_api'
                processed_results.append(flight_dict)

            logger.info(f"✅ [Kiwi搜索] 处理完成: {len(processed_results)} 条航班")
            return processed_results

        except Exception as e:
            logger.error(f"❌ [Kiwi搜索] 搜索失败: {e}")
            import traceback
            logger.error(f"❌ [Kiwi搜索] 错误堆栈: {traceback.format_exc()}")
            return []

    def _optimize_kiwi_flight_data(self, flight_data: dict) -> dict:
        """
        优化Kiwi航班数据，充分利用丰富的数据结构

        Args:
            flight_data: 原始Kiwi航班数据

        Returns:
            dict: 优化后的航班数据
        """
        try:
            # 基础信息提取
            optimized_data = {
                # 基本标识
                'id': flight_data.get('id', ''),
                'source': 'kiwi_flights_api',

                # 价格信息
                'price': flight_data.get('price', ''),
                'price_eur': flight_data.get('price_eur', ''),
                'currency': flight_data.get('currency', 'USD'),
                'currency_symbol': flight_data.get('currency_symbol', '$'),

                # 时间信息
                'departure_time': flight_data.get('departure_time', ''),
                'arrival_time': flight_data.get('arrival_time', ''),
                'duration': flight_data.get('duration', 0),
                'duration_minutes': flight_data.get('duration_minutes', 0),

                # 机场信息
                'departure_airport': flight_data.get('departure_airport', ''),
                'departure_airport_name': flight_data.get('departure_airport_name', ''),
                'arrival_airport': flight_data.get('arrival_airport', ''),
                'arrival_airport_name': flight_data.get('arrival_airport_name', ''),

                # 航空公司信息
                'carrier_code': flight_data.get('carrier_code', ''),
                'carrier_name': flight_data.get('carrier_name', ''),
                'flight_number': flight_data.get('flight_number', ''),

                # 隐藏城市信息
                'is_hidden_city': flight_data.get('is_hidden_city', False),
                'is_throwaway': flight_data.get('is_throwaway', False),
                'hidden_destination_code': flight_data.get('hidden_destination_code', ''),
                'hidden_destination_name': flight_data.get('hidden_destination_name', ''),

                # 路线信息
                'segment_count': flight_data.get('segment_count', 0),
                'route_segments': flight_data.get('route_segments', []),
                'trip_type': flight_data.get('trip_type', 'oneway'),
            }

            # 构建完整路线描述
            route_segments = optimized_data.get('route_segments', [])
            if route_segments:
                # 构建路线路径
                route_path = []
                for segment in route_segments:
                    if not route_path:  # 第一个航段
                        route_path.append(segment.get('from', ''))
                    route_path.append(segment.get('to', ''))

                optimized_data['route_path'] = ' → '.join(route_path)
                optimized_data['route_description'] = self._build_route_description(route_segments)

                # 提取航空公司信息（如果主字段为空）
                if not optimized_data['carrier_name'] and route_segments:
                    first_segment = route_segments[0]
                    optimized_data['carrier_code'] = first_segment.get('carrier', '')
                    optimized_data['flight_number'] = first_segment.get('flight_number', '')

            # 格式化持续时间
            if optimized_data['duration_minutes']:
                hours = optimized_data['duration_minutes'] // 60
                minutes = optimized_data['duration_minutes'] % 60
                optimized_data['duration_formatted'] = f"{hours}小时{minutes}分钟" if hours > 0 else f"{minutes}分钟"

            # 添加航班类型标识
            if optimized_data['is_hidden_city']:
                optimized_data['flight_type'] = 'hidden_city'
                optimized_data['flight_type_description'] = '隐藏城市航班'
            elif optimized_data['segment_count'] > 1:
                optimized_data['flight_type'] = 'connecting'
                optimized_data['flight_type_description'] = '中转航班'
            else:
                optimized_data['flight_type'] = 'direct'
                optimized_data['flight_type_description'] = '直飞航班'

            # 保留原始数据（用于调试）
            optimized_data['_original_data'] = flight_data

            return optimized_data

        except Exception as e:
            logger.error(f"❌ 优化Kiwi航班数据失败: {e}")
            # 返回基本数据结构
            return {
                'id': flight_data.get('id', ''),
                'source': 'kiwi_flights_api',
                'price': flight_data.get('price', ''),
                'currency': flight_data.get('currency', 'USD'),
                'departure_time': flight_data.get('departure_time', ''),
                'arrival_time': flight_data.get('arrival_time', ''),
                'departure_airport': flight_data.get('departure_airport', ''),
                'arrival_airport': flight_data.get('arrival_airport', ''),
                'carrier_name': flight_data.get('carrier_name', ''),
                'is_hidden_city': flight_data.get('is_hidden_city', False),
                'error': f"数据优化失败: {e}",
                '_original_data': flight_data
            }

    def _build_route_description(self, route_segments: list) -> str:
        """
        构建详细的路线描述

        Args:
            route_segments: 路线段列表

        Returns:
            str: 路线描述
        """
        try:
            if not route_segments:
                return ""

            descriptions = []
            for i, segment in enumerate(route_segments):
                from_airport = segment.get('from', '')
                to_airport = segment.get('to', '')
                carrier = segment.get('carrier', '')
                flight_num = segment.get('flight_number', '')

                if i == 0:
                    # 第一段
                    desc = f"{from_airport} → {to_airport}"
                else:
                    # 后续段
                    desc = f"→ {to_airport}"

                if carrier and flight_num:
                    desc += f" ({carrier}{flight_num})"

                descriptions.append(desc)

            return " ".join(descriptions)

        except Exception as e:
            logger.error(f"❌ 构建路线描述失败: {e}")
            return "路线信息解析失败"

    def _standardize_flight_fields(self, flight_data: dict) -> None:
        """
        标准化航班数据字段名称，兼容不同数据源

        Args:
            flight_data: 航班数据字典（会被直接修改）
        """
        try:
            # 标准化航空公司字段
            if 'carrier_name' in flight_data and 'airline' not in flight_data:
                flight_data['airline'] = flight_data['carrier_name']
            elif 'airline' in flight_data and 'carrier_name' not in flight_data:
                flight_data['carrier_name'] = flight_data['airline']

            # 标准化航班号字段
            if 'flight_number' in flight_data and 'flightNumber' not in flight_data:
                flight_data['flightNumber'] = flight_data['flight_number']
            elif 'flightNumber' in flight_data and 'flight_number' not in flight_data:
                flight_data['flight_number'] = flight_data['flightNumber']

            # 标准化时间字段
            if 'departure_time' in flight_data and 'departureTime' not in flight_data:
                flight_data['departureTime'] = flight_data['departure_time']
            if 'arrival_time' in flight_data and 'arrivalTime' not in flight_data:
                flight_data['arrivalTime'] = flight_data['arrival_time']

            # 标准化机场字段
            if 'departure_airport' in flight_data and 'origin' not in flight_data:
                flight_data['origin'] = flight_data['departure_airport']
            if 'arrival_airport' in flight_data and 'destination' not in flight_data:
                flight_data['destination'] = flight_data['arrival_airport']

            # 标准化价格字段
            if 'price' in flight_data:
                # 确保价格是数字格式
                price_str = str(flight_data['price'])
                try:
                    flight_data['price_numeric'] = float(price_str)
                except ValueError:
                    flight_data['price_numeric'] = 0

            # 添加数据源标识（如果没有）
            if 'source' not in flight_data:
                flight_data['source'] = 'unknown'

        except Exception as e:
            logger.error(f"❌ 标准化航班字段失败: {e}")
            # 不抛出异常，继续处理



    def _clean_data_for_ai(self, data: list, data_type: str) -> list:
        """
        清理数据，移除无用字段以节省AI token

        Args:
            data: 原始数据列表
            data_type: 数据类型 ('kiwi', 'google', 'ai')

        Returns:
            list: 清理后的数据列表
        """
        try:
            if not data or not isinstance(data, list):
                return data

            cleaned_data = []

            # 定义需要保留的有用字段
            useful_fields = {
                'kiwi': {
                    # 基本信息
                    'source', 'price', 'currency', 'currency_symbol',
                    # 时间信息
                    'departure_time', 'arrival_time', 'duration_formatted', 'duration_minutes',
                    # 机场信息
                    'departure_airport', 'departure_airport_name',
                    'arrival_airport', 'arrival_airport_name',
                    # 航空公司信息
                    'carrier_name', 'carrier_code', 'flight_number',
                    # 路线信息
                    'route_path', 'route_description', 'segment_count', 'route_segments',
                    # 航班类型
                    'flight_type', 'flight_type_description', 'is_hidden_city',
                    # 隐藏城市信息
                    'hidden_destination_code', 'hidden_destination_name', 'is_throwaway',
                    # 标准化字段
                    'airline', 'origin', 'destination', 'price_numeric'
                },
                'google': {
                    # 保留Google Flights的核心字段
                    'price', 'currency', 'stops', 'legs',
                    # 航空公司信息（如果有值）
                    'airline', 'flightNumber',
                    # 时间信息（如果有值）
                    'departureTime', 'arrivalTime', 'duration',
                    # 直飞标识
                    'isDirect', 'stopsText',
                    # 机场信息
                    'departure_airport', 'arrival_airport'
                },
                'ai': {
                    # 保留AI推荐数据的主要字段
                    'airline', 'flightNumber', 'departureTime', 'arrivalTime',
                    'duration', 'stops', 'isDirect', 'stopsText', 'price', 'currency',
                    'legs', 'departure_airport', 'arrival_airport', 'total_price',
                    'hidden_city_info', 'is_hidden_city', 'ai_recommended'
                }
            }

            # 无用字段列表（这些字段会被明确移除）
            useless_fields = {
                # Kiwi数据的无用字段
                'id',  # 长串编码ID，对AI分析无用
                '_original_data',  # 原始数据备份，占用大量空间
                'price_eur',  # 欧元价格，通常不需要
                'trip_type',  # 行程类型，通常是固定值
                'duration',  # 秒数格式的持续时间，有duration_formatted就够了

                # Google Flights数据的无用字段
                'price_amount',  # 重复的价格字段
                'departureDateTime',  # ISO格式时间，有departureTime就够了
                'arrivalDateTime',  # ISO格式时间，有arrivalTime就够了
                'layovers',  # 中转信息，通常为空或冗余
                'raw_data',  # 调试用的原始数据
                'type',  # 数据类型信息，对AI无用
                'error',  # 错误信息，对AI分析无用
                'total_price',  # 重复的价格字段，有price就够了

                # 通用无用字段
                'hidden_city_info',  # 如果为None则无用
            }

            keep_fields = useful_fields.get(data_type, set())

            for item in data:
                if isinstance(item, dict):
                    # 清理字典数据
                    cleaned_item = {}

                    for key, value in item.items():
                        # 跳过无用字段
                        if key in useless_fields:
                            continue

                        # 如果定义了有用字段列表，只保留有用字段
                        if keep_fields and key not in keep_fields:
                            continue

                        # 清理空值和无意义值
                        if value is None or value == '' or value == 'N/A':
                            continue

                        # 清理过长的字符串（可能是编码数据）
                        if isinstance(value, str) and len(value) > 200 and key != 'route_description':
                            continue

                        cleaned_item[key] = value

                    if cleaned_item:  # 只添加非空的清理后数据
                        cleaned_data.append(cleaned_item)
                else:
                    # 非字典数据直接保留
                    cleaned_data.append(item)

            # 记录清理效果
            original_size = len(str(data))
            cleaned_size = len(str(cleaned_data))
            reduction_percent = (1 - cleaned_size / original_size) * 100 if original_size > 0 else 0

            logger.info(f"🧹 [数据清理] {data_type}数据: {len(data)}条 → {len(cleaned_data)}条")
            logger.info(f"📊 [数据清理] {data_type}大小: {original_size:,} → {cleaned_size:,} 字符 (减少{reduction_percent:.1f}%)")

            return cleaned_data

        except Exception as e:
            logger.error(f"❌ 清理{data_type}数据失败: {e}")
            # 清理失败时返回原始数据
            return data

    def _sync_search_with_layover(self, departure_code: str, final_destination: str,
                                layover_airport: str, depart_date: str, adults: int = 1,
                                language: str = "zh", currency: str = "CNY", seat_class: str = "ECONOMY") -> list:
        """同步搜索航班并手动过滤出经过指定中转机场的航班"""
        try:
            if not SMART_FLIGHTS_AVAILABLE:
                return []

            logger.debug(f"🔍 搜索 {departure_code} → {final_destination}，然后过滤出经过 {layover_airport} 的航班")

            # 创建本地化配置
            localization_config = LocalizationConfig(
                language=Language.CHINESE if language == "zh" else Language.ENGLISH,
                currency=Currency.CNY if currency == "CNY" else Currency.USD
            )

            # 创建乘客信息
            passenger_info = PassengerInfo(adults=adults, children=0, infants_in_seat=0, infants_on_lap=0)

            # 创建航班段 - 不指定中转限制
            try:
                departure_airport = getattr(Airport, departure_code)
                final_destination_airport = getattr(Airport, final_destination)
            except AttributeError as e:
                logger.error(f"机场代码不支持: {e}")
                return []

            flight_segments = [
                FlightSegment(
                    departure_airport=[[departure_airport, 0]],
                    arrival_airport=[[final_destination_airport, 0]],
                    travel_date=depart_date
                )
            ]

            # 根据舱位类型映射到SeatType枚举
            seat_type_mapping = {
                "ECONOMY": SeatType.ECONOMY,
                "PREMIUM_ECONOMY": SeatType.PREMIUM_ECONOMY,
                "BUSINESS": SeatType.BUSINESS,
                "FIRST": SeatType.FIRST
            }
            seat_type = seat_type_mapping.get(seat_class, SeatType.ECONOMY)

            # 创建搜索过滤器 - 不使用中转限制
            filters = FlightSearchFilters(
                trip_type=TripType.ONE_WAY,
                passenger_info=passenger_info,
                flight_segments=flight_segments,
                seat_type=seat_type,
                stops=MaxStops.ANY,  # 允许中转
                sort_by=SortBy.CHEAPEST
            )

            # 执行搜索
            search_client = SearchFlights(localization_config=localization_config)
            all_results = search_client.search_extended(filters, top_n=100)  # 获取更多结果用于过滤

            if not all_results:
                logger.debug(f"❌ 未找到 {departure_code} → {final_destination} 的航班")
                return []

            logger.debug(f"✅ 找到 {len(all_results)} 个 {departure_code} → {final_destination} 的航班，开始过滤")

            # 手动过滤出经过指定中转机场的航班
            filtered_results = []
            for flight in all_results:
                if hasattr(flight, 'legs') and flight.legs:
                    # 检查航班是否经过指定的中转机场
                    route_airports = []
                    for leg in flight.legs:
                        departure_airport_code = getattr(leg, 'departure_airport', '').name if hasattr(getattr(leg, 'departure_airport', ''), 'name') else str(getattr(leg, 'departure_airport', ''))
                        arrival_airport_code = getattr(leg, 'arrival_airport', '').name if hasattr(getattr(leg, 'arrival_airport', ''), 'name') else str(getattr(leg, 'arrival_airport', ''))

                        # 提取机场代码（去掉Airport.前缀）
                        if 'Airport.' in departure_airport_code:
                            departure_airport_code = departure_airport_code.replace('Airport.', '')
                        if 'Airport.' in arrival_airport_code:
                            arrival_airport_code = arrival_airport_code.replace('Airport.', '')

                        if departure_airport_code not in route_airports:
                            route_airports.append(departure_airport_code)
                        if arrival_airport_code not in route_airports:
                            route_airports.append(arrival_airport_code)

                    # 检查是否经过目标中转机场
                    if layover_airport in route_airports:
                        filtered_results.append(flight)
                        logger.debug(f"✅ 找到经过 {layover_airport} 的航班: {' → '.join(route_airports)}")

            logger.debug(f"✅ 过滤完成，找到 {len(filtered_results)} 个经过 {layover_airport} 中转的航班")

            # 直接返回过滤结果，不在这里排序和限制数量
            # 排序和数量限制将在最后合并所有结果时统一处理
            return filtered_results

        except Exception as e:
            logger.error(f"指定中转搜索失败: {e}")
            return []

    async def _process_flights_with_ai(
        self,
        google_flights: List[Dict],
        kiwi_flights: List[Dict],
        ai_flights: List[Dict],
        language: str = "zh",
        departure_code: str = "",
        destination_code: str = "",
        user_preferences: str = ""
    ) -> Dict[str, Any]:
        """
        使用AI处理航班数据，支持重试机制
        """
        max_retries = 3

        for attempt in range(max_retries):
            try:
                logger.info(f"🤖 [AI处理] 开始处理航班数据: {departure_code} → {destination_code}")

                # 【增强日志】详细记录输入数据的结构和内容
                logger.info(f"🔍 [AI处理] 输入数据统计:")

                # Google Flights数据分析
                google_count = len(google_flights) if isinstance(google_flights, list) else 0
                logger.info(f"  - Google Flights: {google_count} 条 (类型: {type(google_flights)})")
                if google_flights and google_count > 0:
                    logger.info(f"  - Google样本: {str(google_flights[0])[:200]}...")

                # Kiwi数据详细分析
                kiwi_count = 0
                logger.info(f"  - Kiwi原始数据类型: {type(kiwi_flights)}")
                if isinstance(kiwi_flights, dict) and 'results' in kiwi_flights:
                    kiwi_count = len(kiwi_flights['results'].get('flights', []))
                    logger.info(f"  - Kiwi (嵌套格式): {kiwi_count} 条")
                    if kiwi_count > 0:
                        sample_flight = kiwi_flights['results']['flights'][0]
                        logger.info(f"  - Kiwi样本: {str(sample_flight)[:200]}...")
                elif isinstance(kiwi_flights, list):
                    kiwi_count = len(kiwi_flights)
                    logger.info(f"  - Kiwi (列表格式): {kiwi_count} 条")
                    if kiwi_count > 0:
                        logger.info(f"  - Kiwi样本: {str(kiwi_flights[0])[:200]}...")
                else:
                    logger.warning(f"  - Kiwi数据格式异常: {type(kiwi_flights)}, 内容: {str(kiwi_flights)[:100]}...")

                # AI数据分析
                ai_count = len(ai_flights) if isinstance(ai_flights, list) else 0
                logger.info(f"  - AI推荐: {ai_count} 条 (类型: {type(ai_flights)})")
                if ai_flights and ai_count > 0:
                    logger.info(f"  - AI样本: {str(ai_flights[0])[:200]}...")

                logger.info(f"📊 [AI处理] 数据源统计: Google({google_count}), Kiwi({kiwi_count}), AI({ai_count})")

                # 【增强日志】检查Kiwi数据的JSON序列化能力
                if kiwi_flights:
                    try:
                        import json
                        # 测试Kiwi数据的序列化
                        if isinstance(kiwi_flights, list) and kiwi_flights:
                            test_kiwi = json.dumps(kiwi_flights[0], default=str, ensure_ascii=False)
                            logger.info(f"✅ [AI处理] Kiwi数据JSON序列化测试成功")
                            logger.info(f"🔍 [AI处理] Kiwi序列化样本: {test_kiwi[:200]}...")
                        elif isinstance(kiwi_flights, dict):
                            test_kiwi = json.dumps(kiwi_flights, default=str, ensure_ascii=False)
                            logger.info(f"✅ [AI处理] Kiwi字典数据JSON序列化测试成功")
                            logger.info(f"🔍 [AI处理] Kiwi序列化长度: {len(test_kiwi)}")
                    except Exception as kiwi_json_error:
                        logger.error(f"❌ [AI处理] Kiwi数据JSON序列化失败: {kiwi_json_error}")
                        logger.error(f"❌ [AI处理] 问题数据: {str(kiwi_flights)[:300]}...")

                # 如果所有数据源都为空，返回错误
                total_flights = google_count + kiwi_count + ai_count
                if total_flights == 0:
                    logger.warning("⚠️ [AI处理] 所有数据源都为空，无法进行AI分析")
                    return {
                        'ai_analysis_report': '## 搜索结果\n\n抱歉，未找到符合条件的航班。请尝试调整搜索条件。',
                        'summary': {
                            'total_flights': 0,
                            'google_flights': 0,
                            'kiwi_flights': 0,
                            'ai_flights': 0,
                            'processing_method': 'empty_data'
                        }
                    }

                # 对AI推荐数据进行最终的排序和数量限制
                if ai_flights and len(ai_flights) > 100:
                    # 按价格排序（升序）
                    try:
                        ai_flights_sorted = sorted(ai_flights, key=lambda x: getattr(x, 'price', float('inf')))
                        ai_flights = ai_flights_sorted[:100]  # 取前100个最便宜的
                        logger.info(f"🔧 [AI处理] AI推荐数据最终排序和限制: 从 {ai_count} 条减少到 {len(ai_flights)} 条（前100最便宜）")
                    except Exception as e:
                        logger.warning(f"⚠️ [AI处理] AI推荐数据排序失败: {e}")
                        ai_flights = ai_flights[:100]  # 如果排序失败，至少限制数量
                        logger.info(f"🔧 [AI处理] AI推荐数据数量限制: 从 {ai_count} 条减少到 {len(ai_flights)} 条")

                # 统一使用单轮对话处理所有数据（已优化数据清理，可以处理大量数据）
                final_total = len(google_flights) + len(kiwi_flights) + len(ai_flights)
                logger.info(f"📊 [AI处理] 最终处理{final_total}条航班数据，使用重试机制")
                processed_data = await self._process_with_fallback_ai(
                    google_flights, kiwi_flights, ai_flights,
                    language, departure_code, destination_code, user_preferences
                )

                # 详细记录processed_data的内容
                logger.info(f"🔍 [AI处理结果] processed_data类型: {type(processed_data)}")
                if processed_data:
                    logger.info(f"🔍 [AI处理结果] processed_data键: {list(processed_data.keys()) if isinstance(processed_data, dict) else 'Not a dict'}")
                    ai_report = processed_data.get('ai_analysis_report', '')
                    logger.info(f"🔍 [AI处理结果] ai_analysis_report长度: {len(ai_report)}")
                    if ai_report:
                        preview = ai_report[:200].replace('\n', '\\n')
                        logger.info(f"🔍 [AI处理结果] ai_analysis_report预览: {preview}")
                    else:
                        logger.warning("⚠️ [AI处理结果] ai_analysis_report为空！")
                else:
                    logger.error("❌ [AI处理结果] processed_data为None或False！")

                if processed_data and processed_data.get('ai_analysis_report'):
                    # 检查是否是新的Markdown格式
                    if processed_data.get('summary', {}).get('markdown_format'):
                        logger.info(f"✅ AI Markdown分析报告生成成功")
                        logger.info(f"📊 处理了 {len(google_flights) + len(kiwi_flights) + len(ai_flights)} 个原始航班，生成智能分析报告")

                        # 只返回AI分析报告，不返回航班数据
                        ai_report = processed_data.get('ai_analysis_report', '')
                        logger.info(f"📊 返回AI分析报告，长度: {len(ai_report)} 字符")

                        return {
                            'success': True,
                            'flights': [],  # 不返回航班数据，只返回AI报告
                            'summary': processed_data.get('summary', {}),
                            'ai_analysis_report': ai_report,
                            'total_count': 0,  # 不返回航班数据
                            'processing_info': {
                                'source_counts': {
                                    'regular_search': len(google_flights),
                                'hidden_city_search': len(kiwi_flights),
                                'ai_analysis': len(ai_flights)
                            },
                            'processed_at': datetime.now().isoformat(),
                            'language': language,
                            'processor': 'ai_markdown',
                            'user_preferences': user_preferences,
                            'format': 'markdown',
                            'report_only': True  # 标记只返回报告
                        }
                    }
                    else:
                        # 兼容旧的JSON格式
                        logger.info(f"✅ AI数据处理成功，处理了 {len(processed_data.get('flights', []))} 个航班")
                        return {
                            'success': True,
                            'flights': processed_data.get('flights', []),
                            'summary': processed_data.get('summary', {}),
                            'ai_analysis_report': processed_data.get('ai_analysis_report', ''),
                            'processing_info': {
                                'source_counts': {
                                    'regular_search': len(google_flights),
                                    'hidden_city_search': len(kiwi_flights),
                                    'ai_analysis': len(ai_flights)
                                },
                                'processed_at': datetime.now().isoformat(),
                                'language': language,
                                'processor': 'ai',
                                'user_preferences': user_preferences,
                                'format': 'json'
                            }
                        }
                else:
                    # AI处理失败或返回空内容时，抛出异常触发重试
                    logger.warning(f"⚠️ AI分析报告为空，将触发重试 (尝试 {attempt + 1}/{max_retries})")
                    raise Exception("AI返回空内容，需要重试")

            except Exception as e:
                logger.error(f"AI航班数据处理异常 (尝试 {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    import asyncio
                    wait_time = (attempt + 1) * 2  # 递增等待时间：2秒、4秒、6秒
                    logger.info(f"⏳ {wait_time}秒后重试...")
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    # 所有重试都失败了
                    logger.error(f"❌ AI航班数据处理失败，已重试 {max_retries} 次")
                    return {
                        'success': False,
                        'flights': [],
                        'error': f"AI处理失败，已重试 {max_retries} 次: {str(e)}"
                    }



    def _convert_flight_to_dict(self, flight) -> dict:
        """将FlightResult对象转换为字典格式 - 优化版本"""
        try:
            if isinstance(flight, dict):
                # 处理字典格式的航班数据
                flight_copy = flight.copy()

                # 检查是否是Kiwi优化后的数据
                if flight_copy.get('source') == 'kiwi_flights_api' and 'route_segments' in flight_copy:
                    # 已经是优化后的Kiwi数据，直接返回
                    return flight_copy

                # 如果有hidden_city_info，提取关键信息到顶层
                if 'hidden_city_info' in flight_copy:
                    hidden_info = flight_copy['hidden_city_info']
                    if isinstance(hidden_info, dict):
                        flight_copy['is_hidden_city'] = hidden_info.get('is_hidden_city', False)
                        flight_copy['hidden_destination_code'] = hidden_info.get('hidden_destination_code', '')
                        flight_copy['ai_recommended'] = hidden_info.get('ai_recommended', False)

                # 标准化字段名称（兼容不同数据源）
                self._standardize_flight_fields(flight_copy)

                # 确保隐藏城市标识存在
                if 'is_hidden_city' not in flight_copy:
                    flight_copy['is_hidden_city'] = False

                return flight_copy

            # 检查是否是smart-flights的FlightResult对象
            if hasattr(flight, '__class__') and 'FlightResult' in str(flight.__class__):
                flight_dict = {}

                # 基本属性
                basic_attrs = ['airline', 'flightNumber', 'departureTime', 'arrivalTime', 'duration', 'stops', 'isDirect', 'stopsText']
                for attr in basic_attrs:
                    if hasattr(flight, attr):
                        value = getattr(flight, attr)
                        flight_dict[attr] = value

                # 处理价格对象
                if hasattr(flight, 'price'):
                    price_obj = getattr(flight, 'price')
                    if hasattr(price_obj, 'formatted'):
                        flight_dict['price'] = price_obj.formatted
                        flight_dict['price_amount'] = getattr(price_obj, 'amount', 0)
                        flight_dict['currency'] = getattr(price_obj, 'currency', 'USD')
                    elif hasattr(price_obj, 'amount'):
                        amount = getattr(price_obj, 'amount', 0)
                        currency = getattr(price_obj, 'currency', 'USD')
                        flight_dict['price'] = f"{amount} {currency}"
                        flight_dict['price_amount'] = amount
                        flight_dict['currency'] = currency
                    else:
                        flight_dict['price'] = str(price_obj)
                        flight_dict['price_amount'] = 0
                        flight_dict['currency'] = 'USD'
                else:
                    flight_dict['price'] = 'N/A'
                    flight_dict['price_amount'] = 0
                    flight_dict['currency'] = 'USD'

                # 处理航段信息
                if hasattr(flight, 'legs'):
                    legs = getattr(flight, 'legs', [])
                    if legs:
                        legs_data = []
                        for leg in legs:
                            leg_dict = {}
                            if hasattr(leg, 'origin') and hasattr(leg.origin, 'displayCode'):
                                leg_dict['origin'] = leg.origin.displayCode
                            if hasattr(leg, 'destination') and hasattr(leg.destination, 'displayCode'):
                                leg_dict['destination'] = leg.destination.displayCode
                            if hasattr(leg, 'departure'):
                                leg_dict['departure'] = leg.departure
                            if hasattr(leg, 'arrival'):
                                leg_dict['arrival'] = leg.arrival
                            if hasattr(leg, 'durationInMinutes'):
                                leg_dict['duration'] = leg.durationInMinutes
                            legs_data.append(leg_dict)
                        flight_dict['legs'] = legs_data
                    else:
                        flight_dict['legs'] = []
                else:
                    flight_dict['legs'] = []

                # 处理隐藏城市信息
                if hasattr(flight, 'hidden_city_info'):
                    hidden_info = getattr(flight, 'hidden_city_info')
                    if hidden_info:
                        flight_dict['hidden_city_info'] = hidden_info
                        # 提取关键标识到顶层，便于AI识别
                        if isinstance(hidden_info, dict):
                            flight_dict['is_hidden_city'] = hidden_info.get('is_hidden_city', False)
                            flight_dict['hidden_destination_code'] = hidden_info.get('hidden_destination_code', '')
                            flight_dict['ai_recommended'] = hidden_info.get('ai_recommended', False)

                # 添加一些默认字段以确保兼容性
                if 'airline' not in flight_dict:
                    flight_dict['airline'] = 'Unknown'
                if 'flightNumber' not in flight_dict:
                    flight_dict['flightNumber'] = 'N/A'
                if 'departureTime' not in flight_dict:
                    flight_dict['departureTime'] = 'N/A'
                if 'arrivalTime' not in flight_dict:
                    flight_dict['arrivalTime'] = 'N/A'

                # 确保隐藏城市标识存在
                if 'is_hidden_city' not in flight_dict:
                    flight_dict['is_hidden_city'] = False

                return flight_dict

            # 如果有dict方法，尝试使用
            elif hasattr(flight, 'dict'):
                return flight.dict()

            # 如果有__dict__属性，使用它
            elif hasattr(flight, '__dict__'):
                return flight.__dict__

            else:
                # 如果都不是，返回基本信息
                return {
                    'raw_data': str(flight),
                    'type': str(type(flight)),
                    'airline': 'Unknown',
                    'flightNumber': 'N/A',
                    'price': 'N/A',
                    'departureTime': 'N/A',
                    'arrivalTime': 'N/A'
                }

        except Exception as e:
            logger.warning(f"转换航班对象失败: {e}")
            return {
                'error': str(e),
                'raw_data': str(flight),
                'type': str(type(flight)),
                'airline': 'Unknown',
                'flightNumber': 'N/A',
                'price': 'N/A',
                'departureTime': 'N/A',
                'arrivalTime': 'N/A'
            }

    def _build_processing_prompt(
        self,
        google_data: List,
        kiwi_data: List,
        ai_data: List,
        language: str,
        departure_code: str,
        destination_code: str,
        user_preferences: str = ""
    ) -> str:
        """构建AI处理提示 - 直接使用原始数据，不进行转换"""

        # 直接使用原始数据，让AI自己处理不同的数据格式
        # Google Flights: FlightResult对象
        # Kiwi: 字典格式
        # AI推荐: FlightResult对象

        # 使用优化版V3提示词系统，分离静态指令和动态数据
        from ..prompts.flight_processor_prompts_v2 import create_final_analysis_prompt

        return create_final_analysis_prompt(
            google_flights_data=google_data,
            kiwi_data=kiwi_data,
            ai_data=ai_data,
            language=language,
            departure_code=departure_code,
            destination_code=destination_code,
            user_preferences=user_preferences
        )



    # 移除多轮对话方法，统一使用单轮对话处理

    async def _process_with_fallback_ai(self, google_flights, kiwi_flights, ai_flights,
                                       language, departure_code, destination_code, user_preferences):
        """使用重试机制处理航班数据，使用环境变量配置的模型"""
        max_retries = 3

        for attempt in range(max_retries):
            try:
                logger.info(f"🔄 开始AI处理（尝试 {attempt + 1}/{max_retries}）")

                # 构建完整的单轮提示词
                prompt = self._build_processing_prompt(
                    google_flights, kiwi_flights, ai_flights,
                    language, departure_code, destination_code, user_preferences
                )

                # 使用环境变量配置的AI模型
                from ..config.settings import AI_MODEL
                model_name = AI_MODEL
                payload_size = len(prompt.encode('utf-8'))
                logger.info(f"🤖 使用配置的AI模型: {model_name} (数据量: {payload_size:,}字节)")

                result = await self._call_ai_api(prompt, model_name, language, enable_fallback=False)

                if result and result.get('success'):
                    ai_content = result.get('content', '')

                    logger.info(f"✅ AI处理成功，使用模型: {model_name}")

                    # 详细记录AI返回的内容
                    logger.info(f"📝 AI返回内容长度: {len(ai_content)} 字符")
                    if ai_content:
                        # 记录前500个字符用于调试
                        preview = ai_content[:500].replace('\n', '\\n')
                        logger.info(f"📝 AI返回内容预览: {preview}")
                        if len(ai_content) > 500:
                            logger.info(f"📝 AI返回内容还有 {len(ai_content) - 500} 个字符...")

                        # 检查内容是否为空，如果为空则抛出异常触发重试
                        if not ai_content.strip():
                            logger.warning("⚠️ AI返回内容为空，触发重试")
                            raise Exception("AI返回空内容")

                        return {
                            'ai_analysis_report': ai_content,
                            'summary': {
                                'markdown_format': True,
                                'model_used': model_name,
                                'processing_method': 'single_turn_with_retry',
                                'attempt': attempt + 1
                            }
                        }
                    else:
                        logger.warning("⚠️ AI返回内容为空，触发重试")
                        raise Exception("AI返回空内容")
                else:
                    logger.warning(f"❌ AI处理失败 (尝试 {attempt + 1}/{max_retries})")
                    if attempt < max_retries - 1:
                        import asyncio
                        wait_time = (attempt + 1) * 2  # 递增等待时间：2秒、4秒、6秒
                        logger.info(f"⏳ {wait_time}秒后重试...")
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        raise Exception("AI处理失败，已达到最大重试次数")

            except Exception as e:
                logger.error(f"❌ AI处理异常 (尝试 {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    import asyncio
                    wait_time = (attempt + 1) * 2
                    logger.info(f"⏳ {wait_time}秒后重试...")
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    # 所有重试都失败了，返回错误报告
                    logger.error(f"❌ AI处理失败，已重试 {max_retries} 次")
                    return {
                        'ai_analysis_report': self._generate_fallback_report(
                            google_flights, kiwi_flights, ai_flights,
                            departure_code, destination_code, user_preferences
                        ),
                        'summary': {
                            'markdown_format': True,
                            'model_used': 'fallback',
                            'processing_method': 'fallback_report',
                            'error': 'AI模型暂时不可用，已生成基础分析报告'
                        }
                    }

    def _generate_fallback_report(self, google_flights, kiwi_flights, ai_flights, departure_code, destination_code, user_preferences):
        """生成降级报告，当AI处理失败时使用"""
        try:
            # 合并所有航班数据
            all_flights = []
            if google_flights:
                all_flights.extend(google_flights)
            if kiwi_flights:
                all_flights.extend(kiwi_flights)
            if ai_flights:
                all_flights.extend(ai_flights)

            # 基础统计
            total_flights = len(all_flights)

            # 简单的价格分析
            prices = []
            for flight in all_flights:
                if flight.get('price') and flight['price'].get('amount'):
                    prices.append(flight['price']['amount'])

            min_price = min(prices) if prices else 0
            avg_price = sum(prices) / len(prices) if prices else 0

            # 生成基础报告
            report = f"""# 航班搜索结果

## 搜索信息
- 出发地: {departure_code}
- 目的地: {destination_code}
- 用户偏好: {user_preferences or '无特殊要求'}

## 搜索结果统计
- 找到航班: {total_flights} 个
- 最低价格: ¥{min_price:,.0f}
- 平均价格: ¥{avg_price:,.0f}

## 说明
由于AI服务暂时不可用，此报告为基础分析结果。
建议稍后重试以获得更详细的AI分析和推荐。
"""

            return report

        except Exception as e:
            logger.error(f"生成降级报告失败: {e}")
            return f"""# 航班搜索结果

搜索完成，但AI分析服务暂时不可用。
找到 {len(google_flights or []) + len(kiwi_flights or []) + len(ai_flights or [])} 个航班结果。

请稍后重试以获得详细的AI分析和推荐。
"""

    async def _call_ai_api(self, prompt: str, model_name: str = None, language: str = "zh", enable_fallback: bool = False) -> Dict:
        """调用AI API进行数据处理，使用环境变量配置的模型"""

        # 使用环境变量配置的AI模型
        if model_name is None:
            from ..config.settings import AI_MODEL
            model_name = AI_MODEL
            payload_size = len(prompt.encode('utf-8'))
            logger.info(f"🤖 使用配置的AI模型: {model_name} (数据量: {payload_size:,}字节)")

        # 直接调用指定模型（不使用降级机制）
        result = await self._try_ai_api_call_with_retry(prompt, model_name, language)

        # 确保总是返回字典格式
        if not isinstance(result, dict):
            return {
                'success': False,
                'error': 'AI API调用失败',
                'content': None
            }

        return result

    async def _try_ai_api_call_with_retry(self, prompt: str, model_name: str, language: str = "zh", max_retries: int = 3) -> Dict:
        """带重试机制的AI API调用"""
        import asyncio

        for attempt in range(max_retries):
            try:
                result = await self._try_ai_api_call(prompt, model_name, language)

                if result and result.get('success'):
                    return result

                # 如果是429错误，等待后重试
                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 2  # 递增等待时间：2秒、4秒、6秒
                    logger.warning(f"⏳ AI API调用失败，{wait_time}秒后重试 (尝试 {attempt + 1}/{max_retries})")
                    await asyncio.sleep(wait_time)
                    continue

            except Exception as e:
                logger.error(f"❌ AI API调用异常 (尝试 {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 2
                    await asyncio.sleep(wait_time)
                    continue

        # 所有重试都失败了
        logger.error(f"❌ AI API调用失败，已重试 {max_retries} 次")
        return {
            'success': False,
            'error': f'AI API调用失败，已重试 {max_retries} 次',
            'content': None
        }

    async def _try_ai_api_call(self, prompt: str, model_name: str, language: str = "zh") -> Optional[Dict]:
        """尝试调用AI API"""
        try:
            import aiohttp
            import os
            from dotenv import load_dotenv

            # 从配置中获取 AI API 设置
            from ..config.settings import AI_API_KEY, AI_API_URL
            api_key = AI_API_KEY
            ai_api_url = AI_API_URL

            if not api_key:
                error_msg = "AI API密钥未配置"
                logger.error(error_msg)
                return {
                    'success': False,
                    'error': error_msg,
                    'content': None
                }

            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }

            # 获取优化的系统提示词V3（减少冗余，提高效率）
            from ..prompts.flight_processor_prompts_v2 import get_consolidated_instructions_prompt
            system_prompt = get_consolidated_instructions_prompt(language)

            payload = {
                "model": model_name,
                "messages": [
                    {
                        "role": "system",
                        "content": system_prompt
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "temperature": 0.2
                # 移除max_tokens限制，充分利用Gemini 2.5 Flash的1M token上下文
            }

            # 记录请求数据大小
            import json
            payload_size = len(json.dumps(payload, ensure_ascii=False))
            prompt_size = len(prompt)
            logger.info(f"🚀 发送AI请求 - Payload大小: {payload_size:,} 字节, Prompt大小: {prompt_size:,} 字符")
            logger.info(f"📊 使用模型: {model_name}, 超时设置: 5分钟")

            # 检查数据量是否过大，如果超过200KB则警告
            if payload_size > 200000:
                logger.warning(f"⚠️ 请求数据量较大: {payload_size:,} 字节，可能导致403错误")
                logger.warning("💡 建议：考虑实现数据分批处理或减少数据量")

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{ai_api_url}/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=300)  # 5分钟超时，为大量数据分析预留更多时间
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        content = result['choices'][0]['message']['content']

                        # 详细记录AI原始响应
                        logger.info(f"🔍 AI原始响应长度: {len(content)} 字符")
                        if content:
                            preview = content[:200].replace('\n', '\\n')
                            logger.info(f"🔍 AI原始响应预览: {preview}")
                        else:
                            logger.warning("⚠️ AI原始响应为空！")

                        # 检查strip后的长度
                        stripped_content = content.strip()
                        logger.info(f"🔍 AI响应strip后长度: {len(stripped_content)} 字符")
                        if len(content) != len(stripped_content):
                            logger.warning(f"⚠️ strip()删除了 {len(content) - len(stripped_content)} 个字符！")
                            logger.info(f"🔍 被删除的字符: {repr(content[:50])}")

                        # 处理纯Markdown响应
                        try:
                            # 只记录处理成功，不输出任何AI内容
                            logger.info("AI Markdown响应处理完成")

                            # 新版本返回纯Markdown格式，不再包含JSON
                            # 直接返回markdown内容作为分析报告，不使用strip()
                            return {
                                'success': True,  # 添加成功标记
                                'content': content,  # 保留原始内容，不使用strip()
                                'flights': [],  # 航班数据现在在markdown中
                                'ai_analysis_report': content,  # 保留原始内容，不使用strip()
                                'summary': {
                                    'total_flights': 0,  # 将从markdown中解析
                                    'markdown_format': True,
                                    'processing_method': 'markdown_only'
                                }
                            }

                        except Exception as e:
                            error_msg = f"AI响应处理失败: {e}"
                            logger.error(error_msg)
                            logger.debug(f"AI原始响应长度: {len(content)} 字符")
                            return {
                                'success': False,
                                'error': error_msg,
                                'content': None
                            }
                    else:
                        error_msg = f"AI API调用失败: {response.status}"
                        logger.error(error_msg)

                        # 读取错误响应内容
                        try:
                            error_content = await response.text()
                            logger.debug(f"错误响应内容: {error_content}")
                        except:
                            error_content = "无法读取错误内容"

                        return {
                            'success': False,
                            'error': error_msg,
                            'status_code': response.status,
                            'error_content': error_content,
                            'content': None
                        }

        except asyncio.TimeoutError:
            error_msg = "AI API调用超时 (5分钟)"
            logger.error(error_msg)
            return {
                'success': False,
                'error': error_msg,
                'content': None
            }
        except aiohttp.ClientError as e:
            error_msg = f"AI API网络连接错误: {e}"
            logger.error(error_msg)
            return {
                'success': False,
                'error': error_msg,
                'content': None
            }
        except Exception as e:
            error_msg = f"调用AI API异常: {type(e).__name__}: {e}"
            logger.error(error_msg)
            import traceback
            logger.debug(f"详细错误信息: {traceback.format_exc()}")
            return {
                'success': False,
                'error': error_msg,
                'content': None
            }


# 全局服务实例
_ai_flight_service: Optional[AIFlightService] = None


def get_ai_flight_service() -> AIFlightService:
    """获取AI航班搜索服务实例（单例模式）"""
    global _ai_flight_service
    if _ai_flight_service is None:
        _ai_flight_service = AIFlightService()
    return _ai_flight_service
