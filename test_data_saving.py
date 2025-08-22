#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试数据保存功能验证脚本
"""

import os
import sys
import asyncio
from pathlib import Path

# Windows环境编码修复
if os.name == 'nt':  # Windows
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.detach())
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.detach())

# 设置环境变量以启用测试数据保存
os.environ["ENABLE_TEST_DATA_SAVE"] = "True"
os.environ["TEST_DATA_DIR"] = "./test_data_demo"

# 导入相关模块
from fastapi_app.utils.test_data_saver import get_test_data_saver
from fastapi_app.services.ai_flight_service import get_ai_flight_service


async def test_data_saving():
    """测试数据保存功能"""
    print("[TEST] 开始测试数据保存功能...")
    
    # 获取服务实例
    test_saver = get_test_data_saver()
    ai_service = get_ai_flight_service()
    
    print(f"[OK] 测试数据保存已启用: {test_saver.enable_save}")
    print(f"[DIR] 数据保存目录: {test_saver.data_dir}")
    
    # 模拟搜索参数
    search_params = {
        'departure_code': 'LHR',
        'destination_code': 'PEK',
        'depart_date': '2025-10-01',
        'return_date': None,
        'adults': 1,
        'seat_class': 'BUSINESS',
        'language': 'zh',
        'currency': 'CNY',
        'user_preferences': '希望找到最便宜的商务舱航班'
    }
    
    print("\n[STAGE] 模拟保存各阶段数据...")
    
    # 模拟Google Flights数据
    google_data = [
        {
            "airline": "英国航空",
            "flightNumber": "BA038",
            "price": "¥15,200",
            "departureTime": "21:10",
            "arrivalTime": "14:50+1",
            "duration": "10小时40分钟",
            "seat_class": "商务舱"
        },
        {
            "airline": "维珍航空",
            "flightNumber": "VS250",
            "price": "¥18,650",
            "departureTime": "19:45",
            "arrivalTime": "13:25+1",
            "duration": "10小时40分钟",
            "seat_class": "商务舱"
        }
    ]
    
    # 模拟Kiwi数据
    kiwi_data = [
        {
            "id": "kiwi_003",
            "source": "kiwi_flights_api",
            "price": 14800,
            "currency": "CNY",
            "departure_airport": "LHR",
            "arrival_airport": "PEK",
            "carrier_name": "国航",
            "is_hidden_city": False,
            "route_path": "LHR → PEK",
            "seat_class": "business"
        },
        {
            "id": "kiwi_004",
            "source": "kiwi_flights_api",
            "price": 13950,
            "currency": "CNY",
            "departure_airport": "LHR",
            "arrival_airport": "PEK",
            "carrier_name": "海南航空",
            "is_hidden_city": True,
            "route_path": "LHR → PEK → SHA",
            "seat_class": "business"
        }
    ]
    
    # 模拟AI推荐数据
    ai_data = [
        {
            "airline": "阿联酋航空",
            "flightNumber": "EK002",
            "price": "¥12,750",
            "route_path": "LHR → DXB → PEK",
            "is_hidden_city": True,
            "ai_recommended": True,
            "hidden_destination_code": "DXB",
            "seat_class": "商务舱",
            "total_duration": "13小时25分钟"
        }
    ]
    
    # 保存各阶段数据
    google_file = test_saver.save_stage_data(
        "google_flights", google_data, search_params,
        {"stage": "1", "description": "Google Flights测试数据"}
    )
    print(f"  [OK] Google Flights数据已保存: {Path(google_file).name if google_file else 'None'}")
    
    kiwi_file = test_saver.save_stage_data(
        "kiwi_flights", kiwi_data, search_params,
        {"stage": "2", "description": "Kiwi测试数据"}
    )
    print(f"  [OK] Kiwi数据已保存: {Path(kiwi_file).name if kiwi_file else 'None'}")
    
    ai_stage_file = test_saver.save_stage_data(
        "ai_recommended", ai_data, search_params,
        {"stage": "3", "description": "AI推荐测试数据"}
    )
    print(f"  [OK] AI推荐数据已保存: {Path(ai_stage_file).name if ai_stage_file else 'None'}")
    
    # 保存AI输入数据
    ai_input_file = test_saver.save_ai_input_data(
        google_data, kiwi_data, ai_data, search_params,
        user_preferences="希望找到最便宜的商务舱航班",
        ai_prompt="这是一个测试AI提示词，用于LHR到PEK的商务舱航班搜索..."
    )
    print(f"  [OK] AI输入数据已保存: {Path(ai_input_file).name if ai_input_file else 'None'}")
    
    # 模拟AI输出数据
    ai_output = {
        "success": True,
        "ai_analysis_report": "# 航班搜索分析报告\n\n## LHR → PEK 商务舱航班分析\n\n找到了3个优质的商务舱选择...",
        "flights": [],
        "summary": {
            "route": "LHR → PEK",
            "seat_class": "BUSINESS", 
            "total_flights": 5,
            "cheapest_price": 12750,
            "most_expensive_price": 18650,
            "markdown_format": True
        }
    }
    
    ai_output_file = test_saver.save_ai_output_data(
        ai_output, search_params,
        {"processing_method": "test", "model_used": "test-model"}
    )
    print(f"  [OK] AI输出数据已保存: {Path(ai_output_file).name if ai_output_file else 'None'}")
    
    # 列出保存的文件
    print(f"\n[FILES] 已保存的测试文件:")
    saved_files = test_saver.list_saved_files()
    for i, file_path in enumerate(saved_files, 1):
        file_size = file_path.stat().st_size
        print(f"  {i}. {file_path.name} ({file_size:,} 字节)")
    
    print(f"\n[DONE] 测试完成！共保存了 {len(saved_files)} 个文件")
    print(f"[DIR] 数据目录: {test_saver.data_dir.absolute()}")


async def test_with_real_search():
    """使用真实搜索测试数据保存（可选）"""
    print("\n[REAL] 测试真实搜索的数据保存功能...")
    
    try:
        # 注意：这需要配置有效的AI API密钥
        ai_service = get_ai_flight_service()
        
        result = await ai_service.search_flights_ai_enhanced(
            departure_code="LHR",
            destination_code="PEK", 
            depart_date="2025-10-01",
            return_date=None,
            adults=1,
            seat_class="BUSINESS",
            language="zh",
            currency="CNY",
            user_preferences="测试搜索，寻找性价比高的商务舱航班"
        )
        
        print("[OK] 真实搜索测试完成")
        print(f"[RESULT] 搜索成功: {result.get('success', False)}")
        
        # 再次列出文件
        test_saver = get_test_data_saver()
        saved_files = test_saver.list_saved_files()
        print(f"[FILES] 当前共有 {len(saved_files)} 个保存文件")
        
    except Exception as e:
        print(f"[SKIP] 真实搜索测试跳过: {e}")


if __name__ == "__main__":
    print("=" * 60)
    print("[START] 测试数据保存功能")
    print("=" * 60)
    
    # 运行基础测试
    asyncio.run(test_data_saving())
    
    # 询问是否运行真实搜索测试
    print("\n" + "=" * 60)
    response = input("是否运行真实搜索测试？(需要配置AI API密钥) [y/N]: ").strip().lower()
    if response in ['y', 'yes']:
        asyncio.run(test_with_real_search())
    
    print("\n[END] 所有测试完成！")