#!/usr/bin/env python3
"""
航班搜索功能测试脚本
测试北京到深圳2025年11月20日的航班查询
"""

import requests
import json
import time
import sys
from datetime import datetime

# 配置
BASE_URL = "https://apiticketradar.izlx.de"
# BASE_URL = "http://localhost"  # 本地测试时使用

class FlightSearchTester:
    def __init__(self, base_url=BASE_URL):
        self.base_url = base_url
        self.session = requests.Session()
        self.session.verify = False  # 忽略SSL证书验证
        self.token = None
        
    def log(self, message):
        """打印带时间戳的日志"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] {message}")
        
    def test_health_check(self):
        """测试健康检查"""
        self.log("🔍 测试健康检查...")
        try:
            response = self.session.get(f"{self.base_url}/health", timeout=10)
            if response.status_code == 200:
                self.log("✅ 主健康检查通过")
                print(f"   响应: {response.json()}")
            else:
                self.log(f"❌ 主健康检查失败: {response.status_code}")
                
            # 测试航班服务健康检查
            response = self.session.get(f"{self.base_url}/api/flights/health", timeout=10)
            if response.status_code == 200:
                self.log("✅ 航班服务健康检查通过")
                print(f"   响应: {response.json()}")
                return True
            else:
                self.log(f"❌ 航班服务健康检查失败: {response.status_code}")
                return False
                
        except Exception as e:
            self.log(f"❌ 健康检查异常: {e}")
            return False
    
    def try_login(self):
        """尝试登录获取token（如果需要）"""
        self.log("🔐 尝试获取认证token...")
        
        # 先检查是否需要认证
        try:
            # 尝试访问需要认证的端点
            response = self.session.get(f"{self.base_url}/api/flights/airports", timeout=10)
            if response.status_code == 401:
                self.log("⚠️ 需要认证，尝试登录...")
                # 这里可以添加登录逻辑
                # 暂时返回False，表示没有token
                return False
            elif response.status_code == 200:
                self.log("✅ 无需认证或已认证")
                return True
            else:
                self.log(f"⚠️ 认证状态未知: {response.status_code}")
                return False
                
        except Exception as e:
            self.log(f"❌ 认证检查异常: {e}")
            return False
    
    def test_flight_search(self):
        """测试航班搜索功能"""
        self.log("🛫 开始测试航班搜索...")
        
        # 搜索参数
        search_params = {
            "departure_code": "PEK",
            "destination_code": "SZX", 
            "depart_date": "2025-11-20",
            "adults": 1,
            "children": 0,
            "infants_in_seat": 0,
            "infants_on_lap": 0,
            "seat_class": "economy",
            "max_stops": "any",
            "sort_by": "cheapest",
            "language": "zh",
            "currency": "CNY",
            "user_preferences": "我想要性价比高的航班，时间比较灵活"
        }
        
        try:
            # 发起异步搜索请求
            self.log(f"📤 发送搜索请求: 北京(PEK) → 深圳(SZX), 日期: 2025-11-20")
            
            headers = {"Content-Type": "application/json"}
            if self.token:
                headers["Authorization"] = f"Bearer {self.token}"
            
            # 构建URL参数
            url = f"{self.base_url}/api/flights/search/ai-enhanced/async"
            
            response = self.session.post(
                url,
                params=search_params,
                headers=headers,
                timeout=30
            )
            
            self.log(f"📥 搜索响应状态: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                self.log("✅ 搜索请求成功提交")
                print(f"   响应数据: {json.dumps(result, ensure_ascii=False, indent=2)}")
                
                # 如果返回了任务ID，可以查询任务状态
                if result.get('data', {}).get('task_id'):
                    task_id = result['data']['task_id']
                    self.log(f"📋 获得任务ID: {task_id}")
                    return self.check_task_status(task_id)
                else:
                    return True
                    
            elif response.status_code == 401:
                self.log("❌ 认证失败，需要登录")
                print(f"   响应: {response.text}")
                return False
            else:
                self.log(f"❌ 搜索请求失败: {response.status_code}")
                print(f"   响应: {response.text}")
                return False
                
        except Exception as e:
            self.log(f"❌ 搜索请求异常: {e}")
            return False
    
    def check_task_status(self, task_id):
        """检查异步任务状态"""
        self.log(f"⏳ 检查任务状态: {task_id}")
        
        max_attempts = 10
        for attempt in range(max_attempts):
            try:
                headers = {}
                if self.token:
                    headers["Authorization"] = f"Bearer {self.token}"
                
                response = self.session.get(
                    f"{self.base_url}/api/flights/search/status/{task_id}",
                    headers=headers,
                    timeout=10
                )
                
                if response.status_code == 200:
                    result = response.json()
                    status = result.get('data', {}).get('status', 'unknown')
                    
                    self.log(f"📊 任务状态: {status} (尝试 {attempt + 1}/{max_attempts})")
                    
                    if status == 'completed':
                        self.log("✅ 任务完成！")
                        print(f"   结果: {json.dumps(result, ensure_ascii=False, indent=2)}")
                        return True
                    elif status == 'failed':
                        self.log("❌ 任务失败")
                        print(f"   错误: {result.get('data', {}).get('error', '未知错误')}")
                        return False
                    elif status in ['pending', 'running']:
                        self.log(f"⏳ 任务进行中，等待5秒后重试...")
                        time.sleep(5)
                        continue
                    else:
                        self.log(f"⚠️ 未知任务状态: {status}")
                        time.sleep(3)
                        continue
                else:
                    self.log(f"❌ 状态查询失败: {response.status_code}")
                    return False
                    
            except Exception as e:
                self.log(f"❌ 状态查询异常: {e}")
                time.sleep(3)
                continue
        
        self.log("⏰ 任务状态检查超时")
        return False
    
    def run_full_test(self):
        """运行完整测试"""
        self.log("🚀 开始航班搜索功能测试")
        self.log("=" * 50)
        
        # 1. 健康检查
        if not self.test_health_check():
            self.log("❌ 健康检查失败，终止测试")
            return False
        
        self.log("-" * 30)
        
        # 2. 认证检查
        auth_ok = self.try_login()
        if not auth_ok:
            self.log("⚠️ 认证可能有问题，但继续测试...")
        
        self.log("-" * 30)
        
        # 3. 航班搜索测试
        search_ok = self.test_flight_search()
        
        self.log("=" * 50)
        if search_ok:
            self.log("🎉 测试完成！航班搜索功能正常")
            return True
        else:
            self.log("💥 测试失败！航班搜索功能异常")
            return False

def main():
    """主函数"""
    print("🛫 航班搜索功能测试脚本")
    print("测试路线: 北京(PEK) → 深圳(SZX)")
    print("测试日期: 2025-11-20")
    print("=" * 60)
    
    # 创建测试器
    tester = FlightSearchTester()
    
    # 运行测试
    success = tester.run_full_test()
    
    # 退出
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
