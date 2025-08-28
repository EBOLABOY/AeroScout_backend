#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据保存功能测试脚本
测试航班数据清洗器的保存功能是否正常工作
"""

import os
import sys
import json
from pathlib import Path

# 添加项目路径到sys.path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from fastapi_app.utils.flight_data_filter import get_flight_data_filter

def test_data_save_functionality():
    """测试数据保存功能"""
    print("开始测试数据保存功能...")
    
    # 获取数据过滤器实例
    filter_instance = get_flight_data_filter()
    
    # 创建模拟数据
    mock_original_data = {
        "google_flights": [
            {
                "id": "test_google_1",
                "price": 1000,
                "currency": "CNY",
                "departure_time": "2025-09-15 08:00",
                "arrival_time": "2025-09-15 20:00",
                "duration_minutes": 720,
                "route": "SHA-NYC",
                "useless_field": "should_be_removed",
                "debug_info": {"internal": "data"}
            },
            {
                "id": "test_google_2", 
                "price": 1200,
                "currency": "CNY",
                "departure_time": "2025-09-15 10:00",
                "arrival_time": "2025-09-15 22:00",
                "duration_minutes": 720,
                "route": "SHA-NYC"
            }
        ],
        "kiwi_flights": [
            {
                "id": "test_kiwi_1",
                "price": 950,
                "currency": "CNY", 
                "departure_time": "2025-09-15 09:00",
                "arrival_time": "2025-09-15 21:00",
                "duration_minutes": 720,
                "is_hidden_city": True,
                "hidden_destination": "BOS"
            }
        ],
        "ai_flights": []
    }
    
    mock_search_params = {
        "departure_code": "SHA",
        "destination_code": "NYC", 
        "depart_date": "2025-09-15",
        "adults": 1,
        "seat_class": "ECONOMY",
        "language": "zh",
        "currency": "CNY",
        "is_guest_user": False
    }
    
    try:
        # 测试数据清洗和保存
        cleaned_data = filter_instance.clean_multi_source_data(
            google_flights=mock_original_data["google_flights"],
            kiwi_flights=mock_original_data["kiwi_flights"], 
            ai_flights=mock_original_data["ai_flights"],
            search_params=mock_search_params,
            save_comparison=True
        )
        
        print("数据清洗完成")
        print(f"清洗结果: Google({len(cleaned_data.get('google_flights', []))}), Kiwi({len(cleaned_data.get('kiwi_flights', []))})")
        
        # 检查保存目录
        save_dir = Path(filter_instance.save_directory)
        if save_dir.exists():
            print(f"保存目录存在: {save_dir}")
            
            # 查找最新的对比文件
            comparison_files = list(save_dir.glob("data_comparison_*.json"))
            if comparison_files:
                latest_file = max(comparison_files, key=lambda f: f.stat().st_mtime)
                print(f"找到对比文件: {latest_file}")
                
                # 验证文件内容
                with open(latest_file, 'r', encoding='utf-8') as f:
                    comparison_data = json.load(f)
                
                expected_keys = ["metadata", "original_data", "cleaned_data"]
                if all(key in comparison_data for key in expected_keys):
                    print("对比文件格式正确")
                    
                    # 显示压缩统计
                    compression_stats = comparison_data["metadata"]["compression_stats"]
                    reduction_ratio = compression_stats["reduction_ratio"]
                    print(f"数据压缩率: {reduction_ratio:.1f}%")
                    
                    print("数据保存功能测试通过!")
                    return True
                else:
                    print("对比文件格式不正确")
                    return False
            else:
                print("未找到对比文件")
                return False
        else:
            print(f"保存目录不存在: {save_dir}")
            return False
            
    except Exception as e:
        print(f"测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_data_save_functionality()
    sys.exit(0 if success else 1)