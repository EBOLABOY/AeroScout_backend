"""
航班数据清理过滤器

专门用于清理航班搜索数据中每条记录的冗余字段，
保留对用户选择航班有用的核心信息，删除技术细节和冗余数据。

核心功能：
1. 清理Kiwi数据：保留隐藏航班字段，删除技术冗余字段
2. 清理Google Flights数据：简化对象表示，提取核心信息  
3. 清理AI推荐数据：正确解析hidden_city_info，保留完整上下文
4. 采用黑名单策略：只删除明确无用的技术字段，确保业务信息完整
5. 标准化数据格式，确保AI易于理解，大幅减少数据体积
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
        
        # 数据来源混淆映射 - 隐藏真实API提供商
        self.source_mapping = {
            'google_flights': 'flight_engine_a',  # 主要搜索引擎A
            'kiwi': 'flight_engine_b',           # 主要搜索引擎B  
            'ai_recommended': 'ai_optimized'      # AI优化推荐
        }
        
        # 预编译正则表达式模式，提升性能
        self.price_pattern = re.compile(r'price=([\d.]+)')
        self.duration_pattern = re.compile(r'] price=[\d.]+ duration=(\d+)')
        self.stops_pattern = re.compile(r'stops=(\d+)')
        self.flight_leg_start_pattern = re.compile(r'FlightLeg\(')
        self.hidden_info_start_pattern = re.compile(r"hidden_city_info=")
        
        # 航段解析相关预编译模式
        self.airline_pattern = re.compile(r"airline=<Airline\.([^:]+):")
        self.flight_number_pattern = re.compile(r"flight_number='([^']+)'")
        self.dep_airport_pattern = re.compile(r"departure_airport=<Airport\.([^:]+):")
        self.arr_airport_pattern = re.compile(r"arrival_airport=<Airport\.([^:]+):")
        self.dep_time_pattern = re.compile(r"departure_datetime=datetime\.datetime\(([^)]+)\)")
        self.arr_time_pattern = re.compile(r"arrival_datetime=datetime\.datetime\(([^)]+)\)")
        self.duration_leg_pattern = re.compile(r"duration=(\d+)")
        
        # 降级解析相关预编译模式
        self.fallback_hidden_city_pattern = re.compile(r"'is_hidden_city': True")
        self.fallback_hidden_city_false_pattern = re.compile(r"'is_hidden_city': False")
        self.fallback_dest_code_pattern = re.compile(r"'hidden_destination_code': '([^']+)'")
        self.fallback_target_code_pattern = re.compile(r"'target_destination_code': '([^']+)'")
        self.fallback_ai_recommended_pattern = re.compile(r"'ai_recommended': True")
        self.fallback_search_method_pattern = re.compile(r"'search_method': '([^']+)'")
        
    
    def get_masked_source(self, original_source: str) -> str:
        """获取混淆后的数据来源标识"""
        return self.source_mapping.get(original_source, original_source)
    
    def _parse_base_flight_string(self, flight_raw_data: str) -> Optional[Dict[str, Any]]:
        """
        解析基础航班字符串数据，提取通用字段
        
        Args:
            flight_raw_data: 航班数据字符串
            
        Returns:
            包含基础字段的字典 {price, duration_minutes, stops, legs, departure_time, arrival_time, route}
        """
        try:
            # 使用预编译正则表达式提取价格
            price_match = self.price_pattern.search(flight_raw_data)
            price = float(price_match.group(1)) if price_match else None
            
            # 提取总时长（分钟）
            duration_match = self.duration_pattern.search(flight_raw_data)
            total_duration = int(duration_match.group(1)) if duration_match else None
            
            # 提取中转次数
            stops_match = self.stops_pattern.search(flight_raw_data)
            stops = int(stops_match.group(1)) if stops_match else 0
            
            # 提取航段信息
            legs = self._extract_flight_legs(flight_raw_data)
            
            if not legs:
                return None
                
            # 构建基础信息
            base_info = {
                'price': price,
                'duration_minutes': total_duration,
                'stops': stops,
                'departure_time': legs[0]['departure_time'] if legs else None,
                'arrival_time': legs[-1]['arrival_time'] if legs else None,
                'route': f"{legs[0]['from']} → {legs[-1]['to']}" if legs else None,
                'legs': legs
            }
            
            return base_info
            
        except Exception as e:
            logger.warning(f"解析基础航班字符串失败: {e}")
            return None

    def clean_google_flight_data(self, flight_raw_data: str) -> Optional[Dict[str, Any]]:
        """
        清理Google Flights原始字符串数据，提取核心信息
        
        Args:
            flight_raw_data: Google Flights原始航班数据字符串
            
        Returns:
            清理后的核心航班信息字典
        """
        try:
            # 使用基础解析方法
            base_info = self._parse_base_flight_string(flight_raw_data)
            if not base_info:
                return None
                
            # 添加Google Flights特有字段
            cleaned_info = {
                'source': self.source_mapping['google_flights'],  # 使用混淆标识
                **base_info
            }
            
            return cleaned_info
            
        except Exception as e:
            logger.warning(f"清理Google Flights数据失败: {e}")
            return None
    
    def clean_kiwi_flight_data(self, flight_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        清理Kiwi航班数据，删除冗余字段，保留核心信息
        重点保留隐藏航班相关的所有重要字段
        
        Args:
            flight_data: Kiwi原始航班数据字典
            
        Returns:
            清理后的核心航班信息字典
        """
        try:
            # 保留用户决策所需的核心字段
            cleaned_data = {
                'source': self.source_mapping['kiwi'],  # 使用混淆标识
                'price': flight_data.get('price'),
                'currency': flight_data.get('currency', 'USD'),
                'departure_time': flight_data.get('departure_time'),
                'arrival_time': flight_data.get('arrival_time'),
                'duration_minutes': flight_data.get('duration_minutes'),
                'departure_airport': flight_data.get('departure_airport'),
                'departure_airport_name': flight_data.get('departure_airport_name'),
                'arrival_airport': flight_data.get('arrival_airport'),
                'arrival_airport_name': flight_data.get('arrival_airport_name'),
                'stops': flight_data.get('segment_count', 1) - 1,
                'route_path': flight_data.get('route_path'),
                'route_description': flight_data.get('route_description'),
                
                # *** 关键修复：保留隐藏航班相关的所有重要字段 ***
                'is_hidden_city': flight_data.get('is_hidden_city', False),
                'is_throwaway': flight_data.get('is_throwaway', False),
                'hidden_destination_code': flight_data.get('hidden_destination_code'),
                'hidden_destination_name': flight_data.get('hidden_destination_name'),
                'flight_type': flight_data.get('flight_type'),
                'flight_type_description': flight_data.get('flight_type_description'),
                
                # 移除顶层航司字段，保持数据一致性
                # 航司信息应该从legs中获取，避免多航段时的混淆
                
                # 其他可能有用的字段
                'segment_count': flight_data.get('segment_count'),
                'trip_type': flight_data.get('trip_type')
            }
            
            # 清理航段信息，保留核心字段并丰富机场名称信息
            if 'route_segments' in flight_data and flight_data['route_segments']:
                # 构建机场代码到名称的映射
                airport_name_mapping = self._build_airport_name_mapping(flight_data)
                
                cleaned_segments = []
                for segment in flight_data['route_segments']:
                    # 提取基础航段信息
                    cleaned_segment = {
                        'from': segment.get('from'),
                        'to': segment.get('to'),
                        'airline': segment.get('carrier'),
                        'flight_number': segment.get('flight_number'),
                        'departure_time': segment.get('departure_time'),
                        'arrival_time': segment.get('arrival_time'),
                        'duration_minutes': segment.get('duration_minutes')
                    }
                    
                    # 丰富机场名称信息，提升数据一致性
                    from_code = cleaned_segment.get('from')
                    to_code = cleaned_segment.get('to')
                    
                    if from_code and from_code in airport_name_mapping:
                        cleaned_segment['from_name'] = airport_name_mapping[from_code]
                    
                    if to_code and to_code in airport_name_mapping:
                        cleaned_segment['to_name'] = airport_name_mapping[to_code]
                    
                    cleaned_segments.append(cleaned_segment)
                cleaned_data['legs'] = cleaned_segments
            
            return cleaned_data
            
        except Exception as e:
            logger.warning(f"清理Kiwi数据失败: {e}")
            return flight_data  # 出错时返回原始数据
    
    def _build_airport_name_mapping(self, flight_data: Dict[str, Any]) -> Dict[str, str]:
        """
        从Kiwi航班数据中构建机场代码到名称的映射
        
        Args:
            flight_data: Kiwi原始航班数据
            
        Returns:
            机场代码到名称的映射字典
        """
        mapping = {}
        
        # 从顶层的出发和到达机场信息构建映射
        dep_code = flight_data.get('departure_airport')
        dep_name = flight_data.get('departure_airport_name')
        if dep_code and dep_name:
            mapping[dep_code] = dep_name
        
        arr_code = flight_data.get('arrival_airport')
        arr_name = flight_data.get('arrival_airport_name')
        if arr_code and arr_name:
            mapping[arr_code] = arr_name
        
        # 从航段数据中提取额外的机场信息（如果存在）
        if 'route_segments' in flight_data:
            for segment in flight_data['route_segments']:
                # 检查是否有from_name和to_name字段
                from_code = segment.get('from')
                from_name = segment.get('from_name')
                if from_code and from_name and from_code not in mapping:
                    mapping[from_code] = from_name
                
                to_code = segment.get('to') 
                to_name = segment.get('to_name')
                if to_code and to_name and to_code not in mapping:
                    mapping[to_code] = to_name
        
        return mapping
    
    def _extract_flight_legs(self, flight_data: str) -> List[Dict[str, Any]]:
        """提取航段信息"""
        legs = []
        
        # 使用预编译的正则表达式找到FlightLeg的开始位置
        start_positions = []
        for match in self.flight_leg_start_pattern.finditer(flight_data):
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
            # 使用预编译正则表达式提取航司代码
            airline_match = self.airline_pattern.search(leg_data)
            airline_code = airline_match.group(1) if airline_match else None
            
            # 提取航班号
            flight_number_match = self.flight_number_pattern.search(leg_data)
            flight_number = flight_number_match.group(1) if flight_number_match else None
            
            # 提取起降机场代码
            dep_airport_match = self.dep_airport_pattern.search(leg_data)
            dep_airport = dep_airport_match.group(1) if dep_airport_match else None
            
            arr_airport_match = self.arr_airport_pattern.search(leg_data)
            arr_airport = arr_airport_match.group(1) if arr_airport_match else None
            
            # 提取时间信息
            dep_time_match = self.dep_time_pattern.search(leg_data)
            arr_time_match = self.arr_time_pattern.search(leg_data)
            
            dep_time = self._parse_datetime(dep_time_match.group(1)) if dep_time_match else None
            arr_time = self._parse_datetime(arr_time_match.group(1)) if arr_time_match else None
            
            # 提取航段时长
            duration_match = self.duration_leg_pattern.search(leg_data)
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
    
    def clean_ai_flight_data(self, flight_raw_data: str) -> Optional[Dict[str, Any]]:
        """
        清理AI推荐航班数据，正确解析hidden_city_info信息
        
        Args:
            flight_raw_data: AI推荐的原始航班数据字符串（包含hidden_city_info）
            
        Returns:
            清理后的核心航班信息字典，包含完整的隐藏城市信息
        """
        try:
            # 第一步：使用基础解析方法获取通用字段
            base_flight_info = self._parse_base_flight_string(flight_raw_data)
            
            if not base_flight_info:
                return None
            
            # 第二步：提取hidden_city_info信息
            hidden_info = self._extract_hidden_city_info(flight_raw_data)
            
            # 第三步：构建AI推荐数据
            ai_flight_info = {
                'source': self.source_mapping['ai_recommended'],  # 使用混淆标识
                **base_flight_info
            }
            
            # 第四步：添加隐藏城市信息
            if hidden_info:
                # 将hidden_city_info作为嵌套字典保留
                ai_flight_info['hidden_city_info'] = hidden_info
                
                # 同时提取关键字段到顶层，便于AI直接访问
                ai_flight_info['is_hidden_city'] = hidden_info.get('is_hidden_city', False)
                ai_flight_info['hidden_destination_code'] = hidden_info.get('hidden_destination_code')
                ai_flight_info['target_destination_code'] = hidden_info.get('target_destination_code')
                ai_flight_info['ai_recommended'] = hidden_info.get('ai_recommended', True)
                ai_flight_info['search_method'] = hidden_info.get('search_method')
            
            return ai_flight_info
            
        except Exception as e:
            logger.warning(f"清理AI推荐航班数据失败: {e}")
            return None
    
    def _extract_hidden_city_info(self, flight_data: str) -> Optional[Dict[str, Any]]:
        """
        从AI推荐航班字符串中提取hidden_city_info信息
        使用更健壮的解析算法，支持嵌套括号和特殊字符
        
        Args:
            flight_data: 包含hidden_city_info的原始字符串
            
        Returns:
            解析后的hidden_city_info字典
        """
        try:
            # 使用预编译正则表达式寻找hidden_city_info的开始位置
            match = self.hidden_info_start_pattern.search(flight_data)
            
            if not match:
                return None
            
            start_pos = match.end()
            
            # 如果下一个字符不是{，说明不是字典格式
            if start_pos >= len(flight_data) or flight_data[start_pos] != '{':
                return None
            
            # 使用括号匹配算法找到完整的字典
            brace_count = 0
            end_pos = start_pos
            
            for i in range(start_pos, len(flight_data)):
                char = flight_data[i]
                if char == '{':
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        end_pos = i + 1
                        break
            
            if brace_count != 0:
                # 括号不匹配，使用降级解析
                logger.warning("hidden_city_info括号不匹配，使用降级解析")
                return self._fallback_parse_hidden_info(flight_data)
            
            # 提取字典字符串
            hidden_info_str = flight_data[start_pos:end_pos]
            
            # 使用ast.literal_eval安全解析
            import ast
            hidden_info_dict = ast.literal_eval(hidden_info_str)
            
            return hidden_info_dict
            
        except Exception as e:
            logger.warning(f"解析hidden_city_info失败: {e}")
            # 降级到更简单的解析方法
            return self._fallback_parse_hidden_info(flight_data)
    
    def _fallback_parse_hidden_info(self, flight_data: str) -> Optional[Dict[str, Any]]:
        """
        当ast.literal_eval失败时的降级解析方法
        
        Args:
            flight_data: 原始字符串
            
        Returns:
            解析后的关键信息字典
        """
        try:
            fallback_info = {}
            
            # 使用预编译正则表达式提取关键字段
            if self.fallback_hidden_city_pattern.search(flight_data):
                fallback_info['is_hidden_city'] = True
            elif self.fallback_hidden_city_false_pattern.search(flight_data):
                fallback_info['is_hidden_city'] = False
            
            # 提取目的地代码
            dest_code_match = self.fallback_dest_code_pattern.search(flight_data)
            if dest_code_match:
                fallback_info['hidden_destination_code'] = dest_code_match.group(1)
            
            # 提取目标目的地代码
            target_code_match = self.fallback_target_code_pattern.search(flight_data)
            if target_code_match:
                fallback_info['target_destination_code'] = target_code_match.group(1)
            
            # 检查是否AI推荐
            if self.fallback_ai_recommended_pattern.search(flight_data):
                fallback_info['ai_recommended'] = True
                
            # 提取搜索方法
            method_match = self.fallback_search_method_pattern.search(flight_data)
            if method_match:
                fallback_info['search_method'] = method_match.group(1)
            
            return fallback_info if fallback_info else None
            
        except Exception as e:
            logger.warning(f"降级解析hidden_city_info也失败: {e}")
            return None
    
    def _parse_datetime(self, datetime_str: str) -> Optional[str]:
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
        删除对用户查看航班无用的冗余字段（采用黑名单策略，只删除明确无用的技术字段）
        
        Args:
            flight_data: 原始航班数据
            
        Returns:
            清理后的航班数据
        """
        cleaned = flight_data.copy()
        
        # 黑名单：只删除明确无用的技术性字段
        technical_fields_to_remove = [
            '_id', 'id', 'raw_data', 'debug_info', 'metadata', 
            'internal_id', 'cache_key', 'request_id', 'trace_id',
            'created_at', 'updated_at', 'version', 'api_version'
        ]
        
        # 删除顶层技术字段
        for field in technical_fields_to_remove:
            if field in cleaned:
                del cleaned[field]
        
        # 对航段信息也应用同样的清理策略（保留duration_minutes等有用字段）
        if 'legs' in cleaned and isinstance(cleaned['legs'], list):
            cleaned_legs = []
            for leg in cleaned['legs']:
                if isinstance(leg, dict):
                    cleaned_leg = leg.copy()
                    # 删除航段中的技术字段
                    for field in technical_fields_to_remove:
                        if field in cleaned_leg:
                            del cleaned_leg[field]
                    cleaned_legs.append(cleaned_leg)
                else:
                    cleaned_legs.append(leg)
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
            
            # 首先检查是否为Pydantic模型（FlightResult等）
            if hasattr(flight_data, 'model_dump'):
                # 转换为字典格式进行处理
                flight_dict = flight_data.model_dump()
                logger.debug(f"🔄 [数据转换] 检测到Pydantic模型，转换为字典: {type(flight_data)} → dict")
                
                # 对转换后的字典进行相应的清理
                if data_source == 'google_flights':
                    cleaned_flight = flight_dict  # Google Flights字典格式，直接使用
                elif data_source == 'kiwi':
                    cleaned_flight = self.clean_kiwi_flight_data(flight_dict)
                elif data_source == 'ai_recommended':
                    cleaned_flight = self.clean_kiwi_flight_data(flight_dict)
                    if cleaned_flight:
                        cleaned_flight['source'] = self.source_mapping['ai_recommended']
                        
            elif data_source == 'google_flights':
                if isinstance(flight_data, str):
                    # Google Flights字符串格式数据
                    cleaned_flight = self.clean_google_flight_data(flight_data)
                elif isinstance(flight_data, dict):
                    # Google Flights已清理的字典格式数据，直接使用
                    cleaned_flight = flight_data
                    
            elif data_source == 'kiwi' and isinstance(flight_data, dict):
                # Kiwi数据是字典格式
                cleaned_flight = self.clean_kiwi_flight_data(flight_data)
                
            elif data_source == 'ai_recommended':
                if isinstance(flight_data, str):
                    # *** 关键修复：AI推荐的字符串数据使用专属解析函数 ***
                    cleaned_flight = self.clean_ai_flight_data(flight_data)
                elif isinstance(flight_data, dict):
                    # AI推荐的字典格式数据（如果存在）
                    cleaned_flight = self.clean_kiwi_flight_data(flight_data)
                    # 确保source字段正确
                    if cleaned_flight:
                        cleaned_flight['source'] = self.source_mapping['ai_recommended']
                
            elif isinstance(flight_data, str):
                # 其他字符串格式数据的降级处理
                cleaned_flight = self.clean_google_flight_data(flight_data)
            
            if cleaned_flight:
                # 清理冗余字段
                final_flight = self._remove_redundant_fields(cleaned_flight)
                cleaned_flights.append(final_flight)
            else:
                logger.warning(f"⚠️ [{data_source}] 无法处理的数据类型: {type(flight_data)}")
        
        # 更新统计信息
        self.statistics['filtered_count'] = len(cleaned_flights)
        self.statistics['compression_ratio'] = (
            len(cleaned_flights) / len(raw_flights) if raw_flights else 1.0
        )
        self.statistics['processing_time'] = (datetime.now() - start_time).total_seconds()
        
        # 计算数据压缩效果（使用JSON字符串长度）
        import json
        
        def safe_json_size(data):
            """安全计算数据的JSON序列化大小"""
            if not data:
                return 0
            try:
                # 如果是Pydantic模型列表，转换为字典
                if isinstance(data, list) and data and hasattr(data[0], 'model_dump'):
                    serializable_data = [item.model_dump() if hasattr(item, 'model_dump') else item for item in data]
                else:
                    serializable_data = data
                return len(json.dumps(serializable_data, ensure_ascii=False, default=str))
            except Exception as e:
                logger.warning(f"⚠️ [{data_source}] JSON序列化失败，跳过大小计算: {e}")
                return 0
        
        original_size = safe_json_size(raw_flights)
        cleaned_size = safe_json_size(cleaned_flights)
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