#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试数据保存工具
用于在测试期间保存航班查询的各阶段原始数据和AI输入数据
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
from loguru import logger


class TestDataSaver:
    """测试数据保存器 - 仅在测试模式下启用"""
    
    def __init__(self, enable_save: bool = False, data_dir: str = "./test_data"):
        """
        初始化测试数据保存器
        
        Args:
            enable_save: 是否启用数据保存
            data_dir: 数据保存目录
        """
        self.enable_save = enable_save
        self.data_dir = Path(data_dir)
        
        if self.enable_save:
            # 创建数据保存目录
            self.data_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"🧪 测试数据保存已启用，保存目录: {self.data_dir}")
        else:
            logger.info("🧪 测试数据保存未启用")
    
    def save_stage_data(
        self,
        stage_name: str,
        data: Any,
        search_params: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[str]:
        """
        保存某个阶段的原始数据
        
        Args:
            stage_name: 阶段名称 (google_flights, kiwi_flights, ai_recommended)
            data: 原始数据
            search_params: 搜索参数
            metadata: 额外元数据
            
        Returns:
            保存的文件路径，如果未启用则返回None
        """
        if not self.enable_save:
            return None
        
        try:
            # 生成文件名
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]  # 包含毫秒
            departure = search_params.get('departure_code', 'UNK')
            destination = search_params.get('destination_code', 'UNK')
            filename = f"{timestamp}_{departure}_{destination}_{stage_name}.json"
            filepath = self.data_dir / filename
            
            # 准备保存数据
            save_data = {
                "stage": stage_name,
                "timestamp": timestamp,
                "search_params": search_params,
                "metadata": metadata or {},
                "data_type": str(type(data)),
                "data_count": len(data) if isinstance(data, (list, dict)) else 0,
                "raw_data": self._serialize_data(data)
            }
            
            # 保存到JSON文件
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(save_data, f, ensure_ascii=False, indent=2, default=str)
            
            logger.info(f"🧪 [测试数据保存] {stage_name}: {filepath.name}")
            return str(filepath)
            
        except Exception as e:
            logger.error(f"❌ 保存{stage_name}数据失败: {e}")
            return None
    
    def save_ai_input_data(
        self,
        google_flights: List,
        kiwi_flights: List, 
        ai_flights: List,
        search_params: Dict[str, Any],
        user_preferences: str = "",
        ai_prompt: str = ""
    ) -> Optional[str]:
        """
        保存发送给AI的整合数据
        
        Args:
            google_flights: Google Flights数据
            kiwi_flights: Kiwi数据
            ai_flights: AI推荐数据
            search_params: 搜索参数
            user_preferences: 用户偏好
            ai_prompt: AI提示词
            
        Returns:
            保存的文件路径，如果未启用则返回None
        """
        if not self.enable_save:
            return None
        
        try:
            # 生成文件名
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
            departure = search_params.get('departure_code', 'UNK')
            destination = search_params.get('destination_code', 'UNK')
            filename = f"{timestamp}_{departure}_{destination}_ai_input.json"
            filepath = self.data_dir / filename
            
            # 准备AI输入数据
            ai_input_data = {
                "stage": "ai_input",
                "timestamp": timestamp,
                "search_params": search_params,
                "user_preferences": user_preferences,
                "ai_prompt_length": len(ai_prompt) if ai_prompt else 0,
                "ai_prompt_preview": ai_prompt[:500] if ai_prompt else "",  # 只保存前500字符预览
                "data_summary": {
                    "google_flights_count": len(google_flights) if isinstance(google_flights, list) else 0,
                    "kiwi_flights_count": len(kiwi_flights) if isinstance(kiwi_flights, list) else 0,
                    "ai_flights_count": len(ai_flights) if isinstance(ai_flights, list) else 0,
                    "google_flights_type": str(type(google_flights)),
                    "kiwi_flights_type": str(type(kiwi_flights)),
                    "ai_flights_type": str(type(ai_flights))
                },
                "combined_data": {
                    "google_flights": self._serialize_data(google_flights),
                    "kiwi_flights": self._serialize_data(kiwi_flights),
                    "ai_flights": self._serialize_data(ai_flights)
                }
            }
            
            # 如果AI提示词不为空且不太长，保存完整版本
            if ai_prompt and len(ai_prompt) < 50000:  # 50KB以下保存完整版本
                ai_input_data["ai_prompt_full"] = ai_prompt
            
            # 保存到JSON文件
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(ai_input_data, f, ensure_ascii=False, indent=2, default=str)
            
            total_count = ai_input_data["data_summary"]["google_flights_count"] + \
                         ai_input_data["data_summary"]["kiwi_flights_count"] + \
                         ai_input_data["data_summary"]["ai_flights_count"]
            
            logger.info(f"🧪 [测试数据保存] AI输入数据: {filepath.name} (共{total_count}条航班)")
            return str(filepath)
            
        except Exception as e:
            logger.error(f"❌ 保存AI输入数据失败: {e}")
            return None
    
    def save_ai_output_data(
        self,
        ai_response: Dict[str, Any],
        search_params: Dict[str, Any],
        processing_info: Optional[Dict[str, Any]] = None
    ) -> Optional[str]:
        """
        保存AI的输出结果
        
        Args:
            ai_response: AI响应数据
            search_params: 搜索参数
            processing_info: 处理信息
            
        Returns:
            保存的文件路径，如果未启用则返回None
        """
        if not self.enable_save:
            return None
        
        try:
            # 生成文件名
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
            departure = search_params.get('departure_code', 'UNK')
            destination = search_params.get('destination_code', 'UNK')
            filename = f"{timestamp}_{departure}_{destination}_ai_output.json"
            filepath = self.data_dir / filename
            
            # 准备AI输出数据
            ai_output_data = {
                "stage": "ai_output",
                "timestamp": timestamp,
                "search_params": search_params,
                "processing_info": processing_info or {},
                "ai_response": ai_response,
                "response_summary": {
                    "success": ai_response.get('success', False),
                    "ai_analysis_report_length": len(ai_response.get('ai_analysis_report', '')),
                    "flights_count": len(ai_response.get('flights', [])),
                    "has_summary": 'summary' in ai_response,
                    "response_keys": list(ai_response.keys()) if isinstance(ai_response, dict) else []
                }
            }
            
            # 保存到JSON文件
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(ai_output_data, f, ensure_ascii=False, indent=2, default=str)
            
            logger.info(f"🧪 [测试数据保存] AI输出数据: {filepath.name}")
            return str(filepath)
            
        except Exception as e:
            logger.error(f"❌ 保存AI输出数据失败: {e}")
            return None
    
    def _serialize_data(self, data: Any) -> Any:
        """
        序列化数据，处理不能直接JSON序列化的对象
        
        Args:
            data: 原始数据
            
        Returns:
            可序列化的数据
        """
        try:
            if isinstance(data, (dict, list, str, int, float, bool)) or data is None:
                return data
            elif hasattr(data, '__dict__'):
                # 如果是对象，转换为字典
                return self._obj_to_dict(data)
            elif hasattr(data, 'dict'):
                # Pydantic模型等
                return data.dict()
            else:
                # 其他情况转换为字符串
                return str(data)
        except Exception as e:
            logger.warning(f"⚠️ 数据序列化失败: {e}")
            return f"序列化失败: {str(data)[:200]}"
    
    def _obj_to_dict(self, obj: Any) -> Dict[str, Any]:
        """
        将对象转换为字典
        
        Args:
            obj: 要转换的对象
            
        Returns:
            字典表示
        """
        try:
            result = {}
            
            # 获取对象的所有属性
            for attr_name in dir(obj):
                if not attr_name.startswith('_'):  # 跳过私有属性
                    try:
                        attr_value = getattr(obj, attr_name)
                        if not callable(attr_value):  # 跳过方法
                            result[attr_name] = self._serialize_data(attr_value)
                    except Exception:
                        # 如果获取属性失败，跳过
                        continue
            
            # 如果没有获取到任何属性，尝试使用__dict__
            if not result and hasattr(obj, '__dict__'):
                result = {k: self._serialize_data(v) for k, v in obj.__dict__.items()}
            
            # 添加类型信息
            result['_object_type'] = str(type(obj))
            
            return result
            
        except Exception as e:
            logger.warning(f"⚠️ 对象转换字典失败: {e}")
            return {
                '_object_type': str(type(obj)),
                '_str_representation': str(obj)[:500],
                '_conversion_error': str(e)
            }
    
    def get_data_directory(self) -> Optional[Path]:
        """
        获取数据保存目录
        
        Returns:
            数据目录路径，如果未启用则返回None
        """
        if self.enable_save:
            return self.data_dir
        return None
    
    def list_saved_files(self, pattern: str = "*.json") -> List[Path]:
        """
        列出已保存的文件
        
        Args:
            pattern: 文件模式匹配
            
        Returns:
            文件路径列表
        """
        if not self.enable_save or not self.data_dir.exists():
            return []
        
        try:
            return sorted(self.data_dir.glob(pattern), key=lambda x: x.stat().st_mtime, reverse=True)
        except Exception as e:
            logger.error(f"❌ 列出保存文件失败: {e}")
            return []


# 全局实例 - 从配置中获取设置
_test_data_saver: Optional[TestDataSaver] = None


def get_test_data_saver() -> TestDataSaver:
    """获取测试数据保存器实例（单例模式）"""
    global _test_data_saver
    if _test_data_saver is None:
        # 直接从环境变量读取，支持运行时动态配置
        import os
        enable_save = os.getenv("ENABLE_TEST_DATA_SAVE", "False").lower() == "true"
        data_dir = os.getenv("TEST_DATA_DIR", "./test_data")
        
        _test_data_saver = TestDataSaver(
            enable_save=enable_save,
            data_dir=data_dir
        )
    return _test_data_saver