#!/usr/bin/env python3
"""
测试数据保存到本地路径功能

此脚本用于验证修改后的数据保存配置是否正确工作，
确保数据保存到本地路径而不是容器内的临时目录。
"""

import os
import sys
import json
from datetime import datetime

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi_app.utils.flight_data_filter import FlightDataFilter


def test_data_save_paths():
    """测试数据保存路径配置"""
    print("=" * 50)
    print("测试数据保存路径配置")
    print("=" * 50)
    
    # 初始化数据过滤器
    filter = FlightDataFilter()
    
    print(f"✅ 配置的保存目录: {filter.save_directory}")
    print(f"✅ 备选临时目录: {filter.fallback_temp_directory}")
    print(f"✅ 数据保存启用状态: {filter.data_save_enabled}")
    
    # 检查目录存在性
    if os.path.exists(filter.save_directory):
        print(f"✅ 主保存目录存在: {filter.save_directory}")
    else:
        print(f"❌ 主保存目录不存在: {filter.save_directory}")
    
    # 检查写入权限
    try:
        test_file = os.path.join(filter.save_directory, "test_write.tmp")
        with open(test_file, 'w') as f:
            f.write("test")
        os.remove(test_file)
        print(f"✅ 主保存目录可写: {filter.save_directory}")
    except Exception as e:
        print(f"❌ 主保存目录无法写入: {e}")


def test_data_comparison_save():
    """测试数据对比保存功能"""
    print("\n" + "=" * 50)
    print("测试数据对比保存功能")
    print("=" * 50)
    
    # 初始化数据过滤器
    filter = FlightDataFilter()
    
    # 模拟测试数据
    original_data = {
        'google_flights': [
            {'flight_id': 'test_001', 'price': 2500, 'airline': 'Test Air', 'debug_info': 'should_be_removed'},
        ],
        'kiwi_flights': [
            {'booking_token': 'abc123', 'price': 2300, 'hidden_city_info': 'hidden data', '_metadata': 'remove_me'},
        ],
        'ai_flights': [
            {'recommendation_id': 'ai_001', 'price': 2400, 'ai_score': 0.95, '_internal_id': 'internal'},
        ]
    }
    
    cleaned_data = {
        'google_flights': [
            {'flight_id': 'test_001', 'price': 2500, 'airline': 'Test Air'},
        ],
        'kiwi_flights': [
            {'booking_token': 'abc123', 'price': 2300, 'hidden_city_info': 'hidden data'},
        ],
        'ai_flights': [
            {'recommendation_id': 'ai_001', 'price': 2400, 'ai_score': 0.95},
        ]
    }
    
    search_params = {
        'departure_code': 'SHA',
        'destination_code': 'NYC',
        'depart_date': '2025-09-15',
        'adults': 1
    }
    
    # 执行保存测试
    try:
        saved_path = filter.save_data_comparison(
            original_data=original_data,
            cleaned_data=cleaned_data,
            search_params=search_params
        )
        
        if saved_path:
            print(f"✅ 数据对比文件保存成功: {saved_path}")
            
            # 验证文件存在且可读
            if os.path.exists(saved_path):
                print(f"✅ 文件存在: {saved_path}")
                
                # 验证JSON格式
                try:
                    with open(saved_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    print(f"✅ JSON格式正确，包含 {len(data)} 个顶级键")
                    
                    # 验证必要字段
                    if 'metadata' in data and 'original_data' in data and 'cleaned_data' in data:
                        print("✅ 数据结构完整")
                    else:
                        print("❌ 数据结构缺少必要字段")
                        
                except json.JSONDecodeError as e:
                    print(f"❌ JSON格式错误: {e}")
                    
            else:
                print(f"❌ 文件不存在: {saved_path}")
        else:
            print("❌ 数据保存失败，返回空路径")
            
    except Exception as e:
        print(f"❌ 数据保存异常: {e}")


def test_environment_detection():
    """测试环境检测逻辑"""
    print("\n" + "=" * 50)
    print("测试环境检测逻辑")
    print("=" * 50)
    
    print(f"当前工作目录: {os.getcwd()}")
    print(f"Python路径: {sys.executable}")
    
    # 检查关键路径
    paths_to_check = [
        "/app",
        "/tmp",
        "./data_analysis",
        "data_analysis"
    ]
    
    for path in paths_to_check:
        if os.path.exists(path):
            print(f"路径存在: {path}")
        else:
            print(f"路径不存在: {path}")


def main():
    """主测试函数"""
    print("开始测试本地数据保存功能")
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 运行所有测试
    test_environment_detection()
    test_data_save_paths()
    test_data_comparison_save()
    
    print("\n" + "=" * 50)
    print("测试完成！")
    print("=" * 50)


if __name__ == "__main__":
    main()