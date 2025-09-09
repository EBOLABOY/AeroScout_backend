"""
监控和Trip.com API服务
专门处理：
1. 监控页面数据获取
2. Trip.com API集成
3. 监控任务执行
4. 价格监控功能
"""

import asyncio
import json
import os
from datetime import datetime

import requests
from loguru import logger

from fastapi_app.services.cache_service import get_cache_service


class MonitorFlightService:
    """监控和Trip.com API服务，专门处理监控相关功能"""

    def __init__(self):
        """初始化监控航班服务"""
        self.cache_service = None  # 将在异步方法中初始化
        logger.info("MonitorFlightService初始化成功，专注于监控和Trip.com API")

        # 统计信息
        self.stats = {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'cache_hits': 0,
            'cache_misses': 0,
        }

    async def _get_cache_service(self):
        """获取缓存服务"""
        if self.cache_service is None:
            self.cache_service = await get_cache_service()
        return self.cache_service

    async def get_monitor_data_async(
        self,
        city_code: str,
        blacklist_cities: list[str] = None,
        blacklist_countries: list[str] = None,
        depart_date: str = None,
        return_date: str = None,
    ) -> dict:
        """
        获取监控页面数据 - 使用Trip.com API

        Args:
            city_code: 城市代码 (如: HKG, SZX, CAN, MFM)
            blacklist_cities: 黑名单城市列表
            blacklist_countries: 黑名单国家列表
            depart_date: 出发日期 (可选，默认使用环境变量)
            return_date: 返程日期 (可选，默认使用环境变量)

        Returns:
            dict: 包含航班数据和统计信息的字典
        """
        try:
            logger.info(f"获取监控数据: {city_code}, 出发日期: {depart_date}, 返程日期: {return_date}")
            self.stats['total_requests'] += 1

            # 检查是否明确传递了日期参数
            import inspect

            frame = inspect.currentframe()
            args, _, _, values = inspect.getargvalues(frame)

            # 判断是否明确传递了 depart_date 和 return_date 参数
            'depart_date' in values and values['depart_date'] is not None
            has_return_param = 'return_date' in values

            # 使用传入的日期，如果没有则从环境变量获取
            if not depart_date:
                depart_date = os.getenv("DEPART_DATE", "2025-09-30")

            # 处理返程日期逻辑
            if has_return_param:
                # 明确传递了 return_date 参数（可能是 None 表示单程票），保持原值
                pass  # return_date 保持传入的值
            else:
                # 没有传递 return_date 参数，使用环境变量默认值
                trip_type = os.getenv("TRIP_TYPE", "2")
                if trip_type == "2":
                    return_date = os.getenv("RETURN_DATE", "2025-10-08")
                else:
                    return_date = None

            # 生成缓存键
            blacklist_key = ""
            if blacklist_cities:
                blacklist_key += f"_cities_{','.join(sorted(blacklist_cities))}"
            if blacklist_countries:
                blacklist_key += f"_countries_{','.join(sorted(blacklist_countries))}"

            # 生成缓存键，单程票和往返票使用不同的键
            if return_date is None:
                cache_key = f"flight_data:{city_code.upper()}:{depart_date}:oneway{blacklist_key}"
            else:
                cache_key = f"flight_data:{city_code.upper()}:{depart_date}:{return_date}{blacklist_key}"

            # 尝试从缓存获取数据
            cache_service = await self._get_cache_service()
            cached_data = await cache_service.get(cache_key, dict)
            if cached_data:
                logger.info(f"从缓存获取监控数据: {city_code}")
                self.stats['cache_hits'] += 1
                return cached_data

            # 缓存未命中，从API获取数据
            logger.info(f"缓存未命中，从API获取数据: {city_code}")
            self.stats['cache_misses'] += 1

            # 使用Trip.com API获取航班数据
            flights = await self.fetch_trip_flights(city_code.upper(), None, depart_date, return_date)

            if not flights:
                logger.warning(f"未获取到 {city_code} 的航班数据")
                return {
                    'success': False,
                    'error': f'未获取到 {city_code} 的航班数据',
                    'flights': [],
                    'stats': {'total': 0, 'lowPrice': 0, 'minPrice': 0},
                    'city_name': city_code,
                    'city_flag': '🏙️',
                }

            # 应用黑名单过滤
            if blacklist_cities or blacklist_countries:
                original_count = len(flights)
                logger.info(f"应用黑名单过滤 - 城市: {blacklist_cities}, 国家: {blacklist_countries}")

                # 打印前几个航班的目的地和国家信息用于调试
                if flights:
                    for i, flight in enumerate(flights[:3]):
                        logger.info(
                            f"航班 {i+1}: 目的地='{flight.get('目的地', 'N/A')}', 国家='{flight.get('国家', 'N/A')}', destination='{flight.get('destination', 'N/A')}', country='{flight.get('country', 'N/A')}'"
                        )

                flights = self._apply_blacklist_filter(flights, blacklist_cities, blacklist_countries)
                logger.info(f"黑名单过滤: {original_count} → {len(flights)} 个航班")

            # 按价格排序，返回所有航班
            all_available_flights = flights
            all_available_flights.sort(key=lambda x: x.get('价格', float('inf')))

            # 计算统计信息
            total_flights = len(all_available_flights)
            min_price = min([f.get('价格', 0) for f in all_available_flights]) if all_available_flights else 0

            # 获取城市显示信息
            city_info = self._get_city_info(city_code)

            logger.info(f"监控数据获取完成: {total_flights} 个航班（包括国内外），返回所有航班")
            self.stats['successful_requests'] += 1

            # 构建返回数据
            result_data = {
                'success': True,
                'flights': all_available_flights,
                'stats': {
                    'total': total_flights,
                    'lowPrice': 0,  # 这里可以根据需要计算低价航班数量
                    'minPrice': min_price,
                },
                'lastUpdate': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'city_name': city_info['name'],
                'city_flag': city_info['flag'],
            }

            # 缓存结果数据（缓存30分钟）
            cache_service = await self._get_cache_service()
            await cache_service.set(cache_key, result_data, expire=1800)
            logger.info(f"已缓存监控数据: {cache_key}")

            return result_data

        except Exception as e:
            logger.error(f"获取监控数据失败: {e}")
            self.stats['failed_requests'] += 1
            return {
                'success': False,
                'error': str(e),
                'flights': [],
                'stats': {'total': 0, 'lowPrice': 0, 'minPrice': 0},
                'city_name': city_code,
                'city_flag': '🏙️',
            }

    async def clear_flight_cache(self, city_code: str = None):
        """清除航班缓存"""
        try:
            cache_service = await self._get_cache_service()
            if city_code:
                # 清除特定城市的缓存
                pattern = f"flight_data:{city_code.upper()}:*"
                deleted_count = await cache_service.delete_pattern(pattern)
                logger.info(f"清除城市 {city_code} 的缓存，删除 {deleted_count} 个键")
            else:
                # 清除所有航班缓存
                pattern = "flight_data:*"
                deleted_count = await cache_service.delete_pattern(pattern)
                logger.info(f"清除所有航班缓存，删除 {deleted_count} 个键")
            return deleted_count
        except Exception as e:
            logger.error(f"清除缓存失败: {e}")
            return 0

    def get_cache_stats(self):
        """获取缓存统计信息"""
        return {
            'total_requests': self.stats['total_requests'],
            'successful_requests': self.stats['successful_requests'],
            'failed_requests': self.stats['failed_requests'],
            'cache_hits': self.stats['cache_hits'],
            'cache_misses': self.stats['cache_misses'],
            'cache_hit_rate': (
                self.stats['cache_hits'] / (self.stats['cache_hits'] + self.stats['cache_misses'])
                if (self.stats['cache_hits'] + self.stats['cache_misses']) > 0
                else 0
            ),
        }

    async def fetch_trip_flights(
        self, departure_code: str, destination_code: str = None, depart_date: str = None, return_date: str = None
    ) -> list[dict]:
        """
        从Trip.com获取航班数据

        Args:
            departure_code: 出发城市代码
            destination_code: 目的地城市代码（可选，为None时获取所有目的地）
            depart_date: 出发日期
            return_date: 返程日期

        Returns:
            List[dict]: 清洗后的航班数据列表
        """
        try:
            logger.info(f"开始从Trip.com获取航班数据: {departure_code} → {destination_code or '所有目的地'}")

            # Trip.com API端点
            url = "https://hk.trip.com/restapi/soa2/19728/fuzzySearch"

            # 获取请求头和payload
            headers = self._get_trip_headers()
            payload = self._update_trip_payload(departure_code, destination_code, depart_date, return_date)

            # 在线程池中执行同步请求
            loop = asyncio.get_event_loop()
            response_data = await loop.run_in_executor(None, self._sync_trip_request, url, headers, payload)

            if response_data:
                # 清洗数据
                cleaned_flights = self._clean_trip_flight_data(response_data)
                logger.info(f"Trip.com数据获取成功: {len(cleaned_flights)} 个航班")
                return cleaned_flights
            else:
                logger.warning("Trip.com API未返回有效数据")
                return []

        except Exception as e:
            logger.error(f"Trip.com API调用失败: {e}")
            return []

    def _sync_trip_request(self, url: str, headers: dict, payload: dict) -> dict:
        """同步执行Trip.com API请求"""
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            response.raise_for_status()

            # 解析响应数据
            response_data = response.json()
            return response_data
        except requests.exceptions.Timeout:
            logger.error("Trip.com API请求超时")
            return None
        except requests.exceptions.ConnectionError:
            logger.error("Trip.com API连接失败")
            return None
        except requests.exceptions.HTTPError as e:
            logger.error(f"Trip.com API HTTP错误: {e}")
            return None
        except json.JSONDecodeError:
            logger.error("Trip.com API响应不是有效的JSON格式")
            return None
        except Exception as e:
            logger.error(f"Trip.com API请求异常: {e}")
            return None

    def _get_trip_headers(self) -> dict:
        """获取Trip.com API请求头 - 基于GitHub项目的正确格式"""
        return {
            'accept': '*/*',
            'accept-language': 'zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7,en-GB;q=0.6',
            'content-type': 'application/json',
            'origin': 'https://hk.trip.com',
            'referer': 'https://hk.trip.com/flights/showfarefirst?dcity=hkg&acity=sel&ddate=2025-06-30&rdate=2025-07-03&triptype=ow&class=y&lowpricesource=searchform&quantity=1&searchboxarg=t&nonstoponly=off&locale=zh-HK&curr=CNY',
            'sec-ch-ua': '"Chromium";v="136", "Microsoft Edge";v="136", "Not.A/Brand";v="99"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36 Edg/136.0.0.0',
            'x-ctx-country': 'HK',
            'x-ctx-currency': 'CNY',
            'x-ctx-locale': 'zh-HK',
            'x-ctx-ubt-pvid': '12',
            'x-ctx-ubt-sid': '24',
            'x-ctx-ubt-vid': '1746708309569.1d384rgx2qT7',
            'cookieorigin': 'https://hk.trip.com',
            'currency': 'CNY',
            'locale': 'zh-HK',
            'priority': 'u=1, i',
        }

    def _update_trip_payload(
        self, departure_code: str, destination_code: str = None, depart_date: str = None, return_date: str = None
    ) -> dict:
        """更新Trip.com API请求payload - 基于GitHub项目的正确格式"""
        # 生成动态参数
        current_time = datetime.now()
        transaction_id = f"1-mf-{current_time.strftime('%Y%m%d%H%M%S')}-WEB"
        client_time = current_time.strftime("%Y-%m-%dT%H:%M:%S+08:00")

        # 根据是否有返程日期决定行程类型
        trip_type = 1 if return_date is None else 2  # 1=单程，2=往返

        base_payload = {
            "tt": trip_type,  # 行程类型：1=单程，2=往返
            "st": 15,
            "source": "mapList",
            "asyncToken": "",
            "ptoken": "",
            "route": 1,
            "segments": [],
            "filters": [{"type": 18, "code": "1,0,0"}],
            "tripDays": [],
            "leaveDay": 0,
            "vaccine": False,
            "transactionId": transaction_id,
            "limitCount": 0,
            "batchBeginNum": 0,
            "batchEndNum": 0,
            "specialType": 0,
            "head": {
                "cid": "09034129218004024014",
                "ctok": "",
                "cver": "3",
                "lang": "01",
                "sid": "8888",
                "syscode": "40",
                "auth": "",
                "xsid": "",
                "extension": [
                    {"name": "abTesting", "value": ""},
                    {"name": "source", "value": "ONLINE"},
                    {"name": "sotpGroup", "value": "Trip"},
                    {"name": "sotpLocale", "value": "zh-HK"},
                    {"name": "sotpCurrency", "value": "CNY"},
                    {"name": "allianceID", "value": "0"},
                    {"name": "sid", "value": "0"},
                    {"name": "ouid", "value": "ctag.hash.nwfme5hcv7n6"},
                    {"name": "uuid"},
                    {"name": "useDistributionType", "value": "1"},
                    {"name": "flt_app_session_transactionId", "value": transaction_id},
                    {"name": "vid", "value": "1746708309569.1d384rgx2qT7"},
                    {"name": "pvid", "value": "40"},
                    {"name": "Flt_SessionId", "value": "1"},
                    {"name": "channel"},
                    {"name": "x-ua", "value": "v=3_os=ONLINE_osv=10"},
                    {"name": "PageId", "value": "10650034306"},
                    {"name": "clientTime", "value": client_time},
                    {"name": "Locale", "value": "zh_hk"},
                    {"name": "Currency", "value": "CNY"},
                    {"name": "Language", "value": "hk"},
                    {"name": "fromVersion", "value": "2"},
                    {"name": "frontVersion", "value": "2"},
                    {"name": "SourceApp", "value": "Trip"},
                ],
                "Locale": "zh-HK",
                "Language": "hk",
                "Currency": "CNY",
                "ClientID": "",
                "appid": "700020",
            },
        }

        # 构建 segments
        segment = {
            "dcl": [],
            "acl": [],
            "dow": [],
            "dcs": [{"ct": 1, "code": departure_code}],
            "acs": [
                {
                    "ct": 6,
                    "code": "bd_49_29",  # 境外目的地区域代码
                }
            ],
            "drl": [{"begin": depart_date or "2025-09-30", "end": depart_date or "2025-09-30"}],
        }

        # 只有往返票才添加返程日期
        if return_date is not None:
            segment["rdrl"] = [{"begin": return_date, "end": return_date}]

        # 如果指定了目的地，更新目的地设置
        if destination_code:
            segment["acs"] = [{"ct": 1, "code": destination_code}]

        base_payload["segments"] = [segment]
        return base_payload

    def _apply_blacklist_filter(
        self, flights: list[dict], blacklist_cities: list[str] = None, blacklist_countries: list[str] = None
    ) -> list[dict]:
        """应用黑名单过滤"""
        filtered_flights = flights

        if blacklist_cities:
            # 支持繁体/简体字符匹配
            blacklist_cities_normalized = []
            for city in blacklist_cities:
                blacklist_cities_normalized.append(city)
                # 添加常见的繁简体转换
                if city == "中國":
                    blacklist_cities_normalized.append("中国")
                elif city == "中国":
                    blacklist_cities_normalized.append("中國")
                elif city == "臺灣":
                    blacklist_cities_normalized.append("台湾")
                elif city == "台湾":
                    blacklist_cities_normalized.append("臺灣")

            filtered_flights = [
                flight
                for flight in filtered_flights
                if not any(
                    blacklist_city in flight.get('目的地', '')
                    or blacklist_city in flight.get('destination', '')
                    or blacklist_city in flight.get('country', '')
                    or blacklist_city in flight.get('国家', '')
                    for blacklist_city in blacklist_cities_normalized
                )
            ]

        if blacklist_countries:
            # 支持繁体/简体字符匹配
            blacklist_countries_normalized = []
            for country in blacklist_countries:
                blacklist_countries_normalized.append(country)
                # 添加常见的繁简体转换
                if country == "中國":
                    blacklist_countries_normalized.append("中国")
                elif country == "中国":
                    blacklist_countries_normalized.append("中國")
                elif country == "臺灣":
                    blacklist_countries_normalized.append("台湾")
                elif country == "台湾":
                    blacklist_countries_normalized.append("臺灣")

            filtered_flights = [
                flight
                for flight in filtered_flights
                if not any(
                    blacklist_country in flight.get('国家', '')
                    or blacklist_country in flight.get('country', '')
                    or blacklist_country in flight.get('目的地', '')
                    or blacklist_country in flight.get('destination', '')
                    for blacklist_country in blacklist_countries_normalized
                )
            ]

        return filtered_flights

    def _get_city_info(self, city_code: str) -> dict:
        """获取城市显示信息"""
        city_map = {
            'HKG': {'name': '香港', 'flag': '🇭🇰'},
            'SZX': {'name': '深圳', 'flag': '🇨🇳'},
            'CAN': {'name': '广州', 'flag': '🇨🇳'},
            'MFM': {'name': '澳门', 'flag': '🇲🇴'},
            'PVG': {'name': '上海', 'flag': '🇨🇳'},
            'PEK': {'name': '北京', 'flag': '🇨🇳'},
            'TSN': {'name': '天津', 'flag': '🇨🇳'},
        }
        return city_map.get(city_code, {'name': city_code, 'flag': '🏙️'})

    def _clean_trip_flight_data(self, response_data: dict) -> list[dict]:
        """清洗Trip.com API返回的航班数据"""
        try:
            flights = []

            # 检查响应结构
            if not isinstance(response_data, dict):
                logger.warning("响应数据不是字典格式")
                return flights

            # 使用GitHub项目中的正确数据路径：routes
            if 'routes' not in response_data or not isinstance(response_data['routes'], list):
                logger.warning("响应中未找到 'routes' 键或其不是列表")
                # 记录响应结构以供调试
                logger.debug(f"响应键: {list(response_data.keys()) if isinstance(response_data, dict) else '非字典'}")
                return flights

            flight_data = response_data['routes']
            logger.info(f"找到航班数据，路径: routes，包含 {len(flight_data)} 个路线")

            # 处理航班数据
            for item in flight_data:  # 处理所有航班数据
                try:
                    flight_info = self._extract_flight_info(item)
                    if flight_info:
                        flights.append(flight_info)
                except Exception as e:
                    logger.debug(f"处理单个航班数据失败: {e}")
                    continue

            logger.info(f"成功清洗 {len(flights)} 个航班数据")
            return flights

        except Exception as e:
            logger.error(f"清洗Trip.com航班数据失败: {e}")
            return []

    def _extract_flight_info(self, route: dict) -> dict:
        """从单个路线项目中提取信息 - 基于GitHub项目的正确格式"""
        try:
            # 安全地提取抵达城市信息
            arrive_city_info = route.get('arriveCity', {})
            arrival_city_name = arrive_city_info.get('name', '未知')
            arrival_city_code = arrive_city_info.get('code', 'N/A')
            arrival_country = arrive_city_info.get('countryName', '未知')
            arrival_province = arrive_city_info.get('provinceName', '')
            image_url = arrive_city_info.get('imageUrl', None)

            # 提取地理信息
            latitude = arrive_city_info.get('lat', '')
            longitude = arrive_city_info.get('lon', '')
            timezone_offset = arrive_city_info.get('gmtutcVariation', 8)

            # 安全地提取价格列表信息 (取第一个)
            price_info_list = route.get('pl', [])
            price_info = price_info_list[0] if price_info_list else {}
            price = price_info.get('price', None)
            pre_price = price_info.get('prePrice', None)
            currency = price_info.get('currency', 'CNY')
            dec_rate = price_info.get('decRate', 0)  # 降价比例
            depart_date = price_info.get('departDate', 'N/A')
            return_date = price_info.get('returnDate', 'N/A')
            jump_url_path = price_info.get('jumpUrl', '')

            # 计算价格变化信息
            price_change = 0
            price_change_percent = 0
            price_trend = 'stable'  # stable, up, down
            if pre_price and pre_price > 0 and price:
                price_change = price - pre_price
                price_change_percent = round((price_change / pre_price) * 100, 1)
                if price_change > 0:
                    price_trend = 'up'
                elif price_change < 0:
                    price_trend = 'down'

            # 构建完整 URL
            base_url = "https://hk.trip.com"
            full_jump_url = base_url + jump_url_path if jump_url_path.startswith('/') else jump_url_path

            # 提取热度评分和推荐信息
            hot_score = route.get('hot', None)
            rec_type = route.get('recType', 0)

            # 提取旅行主题
            theme_codes = arrive_city_info.get('themeCodes', [])
            theme_names = []
            theme_mapping = {
                'ARCHITECTURE_HUMANITIES': '建筑人文',
                'NATURAL_SCENERY': '自然风光',
                'SANDY_BEACH': '海滩度假',
                'SHOPPING': '购物天堂',
                'FOOD': '美食之旅',
                'ADVENTURE': '探险刺激',
                'CULTURE': '文化体验',
                'RELAXATION': '休闲放松',
                'HISTORY': '历史古迹',
                'NIGHTLIFE': '夜生活',
                'FAMILY': '亲子游',
                'ROMANTIC': '浪漫之旅',
            }
            for theme_code in theme_codes:
                theme_name = theme_mapping.get(theme_code, theme_code.replace('_', ' ').title())
                theme_names.append(theme_name)

            # 提取景点标签
            tags_list = route.get('tags', [])
            attraction_tags = [tag.get('name', '') for tag in tags_list if tag.get('name')]
            tags_str = ", ".join(attraction_tags)

            # 获取路线是否为国际航线的标记
            is_international = route.get('isIntl', False)

            # 提取航班持续时间（如果有）
            duration = route.get('duration', 0)

            # 构建航班信息 - 使用前端期望的字段名称
            flight_info = {
                # 前端期望的主要字段
                'destination': arrival_city_name,
                'code': arrival_city_code,
                'country': arrival_country,
                'province': arrival_province,
                'price': price,
                'currency': currency,
                'image': image_url,
                'bookingUrl': full_jump_url,
                'departDate': depart_date,
                'returnDate': return_date,
                'hotScore': hot_score,
                'tags': tags_str,
                'isInternational': is_international,
                # 新增的丰富信息字段
                'priceChange': price_change,
                'priceChangePercent': price_change_percent,
                'priceTrend': price_trend,
                'previousPrice': pre_price,
                'discountRate': dec_rate,
                'themes': theme_names,
                'attractionTags': attraction_tags,
                'recType': rec_type,
                'duration': duration,
                'latitude': latitude,
                'longitude': longitude,
                'timezoneOffset': timezone_offset,
                # 兼容旧版本的中文字段名（保持向后兼容）
                '目的地': arrival_city_name,
                '代码': arrival_city_code,
                '国家': arrival_country,
                '价格': price,
                '货币': currency,
                '出发日期': depart_date,
                '返程日期': return_date,
                '热度': hot_score,
                '标签': tags_str,
                '图片链接': image_url,
                '预订链接': full_jump_url,
                'is_international': is_international,
                # 为原始API数据添加缺失的字段，以兼容模板
                '飞行时长': '查看详情',  # 原始API不提供飞行时长
                '航空公司': '查看详情',  # 原始API不提供航空公司信息
                '航班号': '查看详情',  # 原始API不提供航班号
                '出发时间': '查看详情',  # 原始API不提供具体时间
                '到达时间': '查看详情',  # 原始API不提供具体时间
                '链接': full_jump_url,
            }

            return flight_info

        except Exception as e:
            logger.debug(f"提取航班信息失败: {e}")
            return None


# 全局服务实例
_monitor_flight_service: MonitorFlightService | None = None


def get_monitor_flight_service() -> MonitorFlightService:
    """获取监控航班服务实例（单例模式）"""
    global _monitor_flight_service
    if _monitor_flight_service is None:
        _monitor_flight_service = MonitorFlightService()
    return _monitor_flight_service


# 保持向后兼容性
def get_flight_service() -> MonitorFlightService:
    """获取航班服务实例（向后兼容）"""
    return get_monitor_flight_service()
