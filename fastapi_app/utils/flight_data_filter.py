"""
航班数据清理过滤器

专门用于清理航班搜索数据中每条记录的冗余字段，
保留对用户选择航班有用的核心信息，删除技术细节和冗余数据。

核心功能：
1. 清理Kiwi数据：删除冗余字段，保留时间、地点、价格、航班号等
2. 清理Google Flights数据：简化对象表示，提取核心信息
3. 标准化数据格式，确保AI易于理解
4. 大幅减少数据体积，提高AI处理效率
"""

import re
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Union
from loguru import logger


class FlightDataFilter:
    """航班数据清理过滤器 - 清理单条记录冗余字段"""
    
    def __init__(self):
        self.statistics = {
            'original_count': 0,
            'filtered_count': 0,
            'compression_ratio': 0.0,
            'processing_time': 0.0
        }
    
    def clean_google_flight_data(self, flight_raw_data: str) -> Optional[Dict[str, Any]]:
        """
        清理Google Flights原始字符串数据，提取核心信息
        
        Args:
            flight_raw_data: Google Flights原始航班数据字符串
            
        Returns:
            清理后的核心航班信息字典
        """
        try:
            # 提取价格
            price_match = re.search(r'price=([\d.]+)', flight_raw_data)
            price = float(price_match.group(1)) if price_match else None
            
            # 提取总时长（分钟）- 注意这是总时长，不是第一个航段的时长
            duration_match = re.search(r'] price=[\d.]+ duration=(\d+)', flight_raw_data)
            total_duration = int(duration_match.group(1)) if duration_match else None
            
            # 提取中转次数
            stops_match = re.search(r'stops=(\d+)', flight_raw_data)
            stops = int(stops_match.group(1)) if stops_match else 0
            
            # 提取航段信息
            legs = self._extract_flight_legs(flight_raw_data)
            
            if not legs:
                return None
                
            # 构建清理后的核心信息
            cleaned_info = {
                'source': 'google_flights',
                'price': price,
                'duration_minutes': total_duration,
                'stops': stops,
                'departure_time': legs[0]['departure_time'] if legs else None,
                'arrival_time': legs[-1]['arrival_time'] if legs else None,
                'route': f"{legs[0]['from']} → {legs[-1]['to']}" if legs else None,
                'legs': legs
            }
            
            return cleaned_info
            
        except Exception as e:
            logger.warning(f"清理Google Flights数据失败: {e}")
            return None
    
    def clean_kiwi_flight_data(self, flight_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        清理Kiwi航班数据，删除冗余字段，保留核心信息
        
        Args:
            flight_data: Kiwi原始航班数据字典
            
        Returns:
            清理后的核心航班信息字典
        """
        try:
            # 只保留用户决策所需的核心字段
            cleaned_data = {
                'source': 'kiwi',
                'price': flight_data.get('price'),
                'currency': flight_data.get('currency', 'USD'),
                'departure_time': flight_data.get('departure_time'),
                'arrival_time': flight_data.get('arrival_time'),
                'duration_minutes': flight_data.get('duration_minutes'),
                'departure_airport': flight_data.get('departure_airport'),
                'arrival_airport': flight_data.get('arrival_airport'),
                'stops': flight_data.get('segment_count', 1) - 1,
                'route_path': flight_data.get('route_path'),
                'route_description': flight_data.get('route_description')
            }
            
            # 清理航段信息，只保留核心字段
            if 'route_segments' in flight_data and flight_data['route_segments']:
                cleaned_segments = []
                for segment in flight_data['route_segments']:
                    cleaned_segment = {
                        'from': segment.get('from'),
                        'to': segment.get('to'),
                        'airline': segment.get('carrier'),
                        'flight_number': segment.get('flight_number'),
                        'departure_time': segment.get('departure_time'),
                        'arrival_time': segment.get('arrival_time')
                    }
                    cleaned_segments.append(cleaned_segment)
                cleaned_data['legs'] = cleaned_segments
            
            return cleaned_data
            
        except Exception as e:
            logger.warning(f"清理Kiwi数据失败: {e}")
            return flight_data  # 出错时返回原始数据
    
    def _extract_flight_legs(self, flight_data: str) -> List[Dict[str, Any]]:
        """提取航段信息"""
        legs = []
        
        # 使用更智能的方法，找到FlightLeg的开始和结束位置
        start_pattern = r'FlightLeg\('
        
        # 找到所有FlightLeg的起始位置
        start_positions = []
        for match in re.finditer(start_pattern, flight_data):
            start_positions.append(match.start())
        
        for i, start_pos in enumerate(start_positions):
            # 从起始位置开始，找到对应的结束括号
            open_brackets = 0
            start_content_pos = start_pos + len('FlightLeg(')
            
            for j in range(start_content_pos, len(flight_data)):
                if flight_data[j] == '(':
                    open_brackets += 1
                elif flight_data[j] == ')':
                    if open_brackets == 0:
                        # 找到了匹配的结束括号
                        leg_content = flight_data[start_content_pos:j]
                        leg_info = self._parse_flight_leg(leg_content)
                        if leg_info:
                            legs.append(leg_info)
                        break
                    else:
                        open_brackets -= 1
                
        return legs
    
    def _parse_flight_leg(self, leg_data: str) -> Optional[Dict[str, Any]]:
        """解析单个航段信息"""
        try:
            # 提取航司代码（从枚举中）
            airline_match = re.search(r"airline=<Airline\.([^:]+):", leg_data)
            airline_code = airline_match.group(1) if airline_match else None
            
            # 提取航班号
            flight_number_match = re.search(r"flight_number='([^']+)'", leg_data)
            flight_number = flight_number_match.group(1) if flight_number_match else None
            
            # 提取起降机场代码
            dep_airport_match = re.search(r"departure_airport=<Airport\.([^:]+):", leg_data)
            dep_airport = dep_airport_match.group(1) if dep_airport_match else None
            
            arr_airport_match = re.search(r"arrival_airport=<Airport\.([^:]+):", leg_data)
            arr_airport = arr_airport_match.group(1) if arr_airport_match else None
            
            # 提取时间信息
            dep_time_match = re.search(r"departure_datetime=datetime\.datetime\(([^)]+)\)", leg_data)
            arr_time_match = re.search(r"arrival_datetime=datetime\.datetime\(([^)]+)\)", leg_data)
            
            dep_time = self._parse_datetime(dep_time_match.group(1)) if dep_time_match else None
            arr_time = self._parse_datetime(arr_time_match.group(1)) if arr_time_match else None
            
            # 提取航段时长
            duration_match = re.search(r"duration=(\d+)", leg_data)
            duration = int(duration_match.group(1)) if duration_match else None
            
            return {
                'airline': airline_code,
                'flight_number': flight_number,
                'from': dep_airport,
                'to': arr_airport,
                'departure_time': dep_time,
                'arrival_time': arr_time,
                'duration_minutes': duration
            }
            
        except Exception as e:
            logger.warning(f"解析航段信息失败: {e}")
            return None
    
    def _parse_datetime(self, datetime_str: str) -> Optional[str]:
        """解析datetime字符串为标准格式"""
        try:
            # 从"2025, 10, 8, 2, 0"格式解析（注意可能有秒数）
            parts = [int(x.strip()) for x in datetime_str.split(',')]
            if len(parts) >= 5:
                year, month, day, hour, minute = parts[:5]
                dt = datetime(year, month, day, hour, minute)
                return dt.strftime('%Y-%m-%d %H:%M')
            elif len(parts) >= 4:
                year, month, day, hour = parts[:4]
                dt = datetime(year, month, day, hour, 0)
                return dt.strftime('%Y-%m-%d %H:%M')
        except Exception as e:
            logger.warning(f"解析时间失败: {datetime_str}, 错误: {e}")
        return None
    
    def _remove_redundant_fields(self, flight_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        删除对用户查看航班无用的冗余字段
        
        Args:
            flight_data: 原始航班数据
            
        Returns:
            清理后的航班数据
        """
        cleaned = flight_data.copy()
        
        # 删除可计算的冗余字段（duration_minutes可以从时间计算）
        if 'legs' in cleaned:
            cleaned_legs = []
            for leg in cleaned['legs']:
                cleaned_leg = leg.copy()
                # 保留核心字段，删除可计算字段
                if 'duration_minutes' in cleaned_leg:
                    del cleaned_leg['duration_minutes']
                cleaned_legs.append(cleaned_leg)
            cleaned['legs'] = cleaned_legs
        
        return cleaned
    
    def clean_flight_data_list(self, raw_flights: List, data_source: str) -> List[Dict[str, Any]]:
        """
        清理航班数据列表，删除每条记录中的冗余字段
        
        Args:
            raw_flights: 原始航班数据列表
            data_source: 数据源类型 ('google_flights', 'kiwi', 'ai_recommended')
            
        Returns:
            清理后的航班数据列表
        """
        start_time = datetime.now()
        self.statistics['original_count'] = len(raw_flights)
        
        cleaned_flights = []
        
        for flight_data in raw_flights:
            cleaned_flight = None
            
            if data_source == 'google_flights':
                if isinstance(flight_data, str):
                    # Google Flights字符串格式数据
                    cleaned_flight = self.clean_google_flight_data(flight_data)
                elif isinstance(flight_data, dict):
                    # Google Flights已清理的字典格式数据，直接使用
                    cleaned_flight = flight_data
                    
            elif data_source in ['kiwi', 'ai_recommended'] and isinstance(flight_data, dict):
                # Kiwi和AI推荐数据是字典格式
                cleaned_flight = self.clean_kiwi_flight_data(flight_data)
                
            elif isinstance(flight_data, str) and data_source != 'google_flights':
                # 处理可能的字符串格式数据
                cleaned_flight = self.clean_google_flight_data(flight_data)
            
            if cleaned_flight:
                # 清理冗余字段
                final_flight = self._remove_redundant_fields(cleaned_flight)
                cleaned_flights.append(final_flight)
        
        # 更新统计信息
        self.statistics['filtered_count'] = len(cleaned_flights)
        self.statistics['compression_ratio'] = (
            len(cleaned_flights) / len(raw_flights) if raw_flights else 1.0
        )
        self.statistics['processing_time'] = (datetime.now() - start_time).total_seconds()
        
        # 计算数据压缩效果
        original_size = len(str(raw_flights))
        cleaned_size = len(str(cleaned_flights))
        size_reduction = (1 - cleaned_size / original_size) * 100 if original_size > 0 else 0
        
        logger.info(f"🧹 [{data_source}] 数据清理完成: {len(raw_flights)} → {len(cleaned_flights)} 条")
        logger.info(f"📊 [{data_source}] 体积压缩: {size_reduction:.1f}%")
        
        return cleaned_flights
    
    def clean_multi_source_data(
        self, 
        google_flights: List = None,
        kiwi_flights: List = None, 
        ai_flights: List = None
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        清理多源航班数据，删除每条记录中的冗余字段
        
        Args:
            google_flights: Google Flights原始数据
            kiwi_flights: Kiwi原始数据
            ai_flights: AI推荐原始数据
            
        Returns:
            清理后的分类数据
        """
        result = {}
        total_original = 0
        total_cleaned = 0
        
        if google_flights:
            result['google_flights'] = self.clean_flight_data_list(google_flights, 'google_flights')
            total_original += len(google_flights)
            total_cleaned += len(result['google_flights'])
        
        if kiwi_flights:
            result['kiwi_flights'] = self.clean_flight_data_list(kiwi_flights, 'kiwi')
            total_original += len(kiwi_flights)
            total_cleaned += len(result['kiwi_flights'])
            
        if ai_flights:
            result['ai_flights'] = self.clean_flight_data_list(ai_flights, 'ai_recommended')
            total_original += len(ai_flights)
            total_cleaned += len(result['ai_flights'])
        
        logger.info(f"📊 多源数据清理汇总: {total_original} → {total_cleaned} 条")
        
        return result

    def clean_complete_ai_input_data(
        self,
        ai_input_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        清理完整的AI输入数据，保留用户偏好和搜索参数，去除冗余元信息
        
        Args:
            ai_input_data: 完整的AI输入数据字典
            
        Returns:
            Dict: 清理后的完整数据，去除重复信息和无用技术字段
        """
        cleaned_result = {}
        
        # 保留重要的非航班数据（去除无用技术字段）
        important_fields = [
            'stage', 'timestamp', 'search_params', 'user_preferences'
        ]
        
        for field in important_fields:
            if field in ai_input_data:
                cleaned_result[field] = ai_input_data[field]
        
        # 检查并去除重复的user_preferences
        search_params = cleaned_result.get('search_params', {})
        if (isinstance(search_params, dict) and 
            search_params.get('user_preferences') == cleaned_result.get('user_preferences')):
            # 删除search_params中的重复user_preferences
            search_params = search_params.copy()
            del search_params['user_preferences']
            cleaned_result['search_params'] = search_params
            logger.info("🧹 删除重复的user_preferences字段")
        
        # 清理航班数据
        combined_data = ai_input_data.get('combined_data', {})
        if combined_data:
            cleaned_combined = self.clean_multi_source_data(
                google_flights=combined_data.get('google_flights'),
                kiwi_flights=combined_data.get('kiwi_flights'),
                ai_flights=combined_data.get('ai_flights')
            )
            cleaned_result['combined_data'] = cleaned_combined
            
            # 生成简化的数据摘要（不包含技术调试信息）
            cleaned_result['data_summary'] = {
                'google_flights_count': len(cleaned_combined.get('google_flights', [])),
                'kiwi_flights_count': len(cleaned_combined.get('kiwi_flights', [])),
                'ai_flights_count': len(cleaned_combined.get('ai_flights', [])),
                'total_flights': sum([
                    len(cleaned_combined.get('google_flights', [])),
                    len(cleaned_combined.get('kiwi_flights', [])),
                    len(cleaned_combined.get('ai_flights', []))
                ])
            }
        
        return cleaned_result
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取清理统计信息"""
        return self.statistics.copy()
    
    def calculate_data_compression(self, original_data: Dict, cleaned_data: Dict) -> Dict[str, Any]:
        """
        计算数据压缩效果
        
        Args:
            original_data: 原始数据
            cleaned_data: 清理后数据
            
        Returns:
            压缩统计信息
        """
        try:
            import json
            
            original_json = json.dumps(original_data, ensure_ascii=False, default=str)
            cleaned_json = json.dumps(cleaned_data, ensure_ascii=False, default=str)
            
            original_size = len(original_json)
            cleaned_size = len(cleaned_json)
            compression_ratio = (1 - cleaned_size / original_size) * 100 if original_size > 0 else 0
            
            return {
                'original_size_chars': original_size,
                'cleaned_size_chars': cleaned_size,
                'compression_ratio_percent': compression_ratio,
                'size_reduction_chars': original_size - cleaned_size
            }
            
        except Exception as e:
            logger.warning(f"计算压缩率失败: {e}")
            return {
                'original_size_chars': 0,
                'cleaned_size_chars': 0,
                'compression_ratio_percent': 0,
                'size_reduction_chars': 0
            }


# 全局过滤器实例
_flight_data_filter = None

def get_flight_data_filter() -> FlightDataFilter:
    """获取航班数据清理过滤器实例（单例模式）"""
    global _flight_data_filter
    if _flight_data_filter is None:
        _flight_data_filter = FlightDataFilter()
    return _flight_data_filter