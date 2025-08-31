#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
搜索日志服务
记录用户搜索行为，用于统计和分析
"""

from datetime import datetime
from typing import Dict, Any, Optional
from loguru import logger

from .supabase_service import get_supabase_service


class SearchLogService:
    """搜索日志服务"""
    
    def __init__(self):
        self.table_name = 'search_logs'
        self._table_checked = False
    
    async def _ensure_table_exists(self) -> bool:
        """确保搜索日志表存在"""
        if self._table_checked:
            return True
            
        try:
            supabase_service = await get_supabase_service()
            
            # 尝试查询表以检查是否存在
            result = supabase_service.client.table(self.table_name).select('id').limit(1).execute()
            
            if hasattr(result, 'data'):
                logger.debug("搜索日志表存在，可以正常使用")
                self._table_checked = True
                return True
                
        except Exception as e:
            if 'does not exist' in str(e) or '42P01' in str(e):
                logger.warning("搜索日志表不存在，尝试创建...")
                return await self._create_table()
            else:
                logger.warning(f"检查搜索日志表时发生错误: {e}")
                
        return False
    
    async def _create_table(self) -> bool:
        """创建搜索日志表"""
        try:
            supabase_service = await get_supabase_service()
            
            # 简化的建表SQL - 兼容性更好
            create_sql = """
            CREATE TABLE IF NOT EXISTS public.search_logs (
                id BIGSERIAL PRIMARY KEY,
                user_id TEXT,
                search_type TEXT NOT NULL,
                departure_city TEXT NOT NULL,
                arrival_city TEXT NOT NULL,
                departure_date DATE NOT NULL,
                return_date DATE,
                passenger_count INTEGER DEFAULT 1,
                results_count INTEGER DEFAULT 0,
                search_duration FLOAT DEFAULT 0.0,
                success BOOLEAN DEFAULT true,
                error_message TEXT,
                search_params TEXT,
                ip_address TEXT,
                user_agent TEXT,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            );
            
            CREATE INDEX IF NOT EXISTS idx_search_logs_created_at ON public.search_logs(created_at);
            CREATE INDEX IF NOT EXISTS idx_search_logs_user_id ON public.search_logs(user_id);
            """
            
            # 尝试通过RPC执行SQL（如果可用）
            try:
                result = supabase_service.client.rpc('exec_sql', {'sql': create_sql}).execute()
                logger.success("通过RPC成功创建搜索日志表")
                self._table_checked = True
                return True
            except Exception as rpc_error:
                logger.debug(f"RPC创建失败: {rpc_error}")
                
            # 如果RPC不可用，记录警告但不阻塞系统运行
            logger.warning("无法自动创建搜索日志表，请手动在Supabase中执行建表SQL")
            logger.info("建表SQL已保存在 create_search_logs_table.sql 文件中")
            
            return False
            
        except Exception as e:
            logger.warning(f"创建搜索日志表失败: {e}")
            return False
    
    async def log_search(
        self, 
        user_id: Optional[str], 
        search_type: str,
        departure_city: str,
        arrival_city: str,
        departure_date: str,
        return_date: Optional[str] = None,
        passenger_count: int = 1,
        results_count: int = 0,
        search_duration: float = 0.0,
        success: bool = True,
        error_message: Optional[str] = None,
        search_params: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        记录搜索日志
        
        Args:
            user_id: 用户ID (可为空，支持匿名搜索)
            search_type: 搜索类型 (basic, comprehensive, ai-enhanced)
            departure_city: 出发城市
            arrival_city: 到达城市  
            departure_date: 出发日期
            return_date: 返程日期 (往返票)
            passenger_count: 乘客数量
            results_count: 搜索结果数量
            search_duration: 搜索耗时(秒)
            success: 搜索是否成功
            error_message: 错误信息
            search_params: 搜索参数
            
        Returns:
            是否记录成功
        """
        try:
            # 检查表是否存在
            if not await self._ensure_table_exists():
                logger.debug("搜索日志表不可用，跳过日志记录")
                return False
            
            supabase_service = await get_supabase_service()
            
            # 准备搜索参数（转换为字符串以兼容简单表结构）
            params_str = None
            if search_params:
                try:
                    import json
                    params_str = json.dumps(search_params, ensure_ascii=False)
                except Exception:
                    params_str = str(search_params)
            
            log_data = {
                'user_id': user_id,
                'search_type': search_type,
                'departure_city': departure_city,
                'arrival_city': arrival_city,
                'departure_date': departure_date,
                'return_date': return_date,
                'passenger_count': passenger_count,
                'results_count': results_count,
                'search_duration': search_duration,
                'success': success,
                'error_message': error_message,
                'search_params': params_str,
                'created_at': datetime.utcnow().isoformat()
            }
            
            # 尝试插入搜索日志
            result = supabase_service.client.table(self.table_name).insert(log_data).execute()
            
            if result.data:
                logger.debug(f"搜索日志记录成功: {search_type} - {departure_city}→{arrival_city}")
                return True
            else:
                logger.debug("搜索日志记录失败: 无返回数据")
                return False
                
        except Exception as e:
            logger.debug(f"搜索日志记录失败: {e}")
            # 搜索日志记录失败不应该影响搜索功能
            return False
    
    async def get_search_stats(self, days: int = 30) -> Dict[str, Any]:
        """
        获取搜索统计数据
        
        Args:
            days: 统计天数
            
        Returns:
            搜索统计数据
        """
        try:
            if not await self._ensure_table_exists():
                logger.debug("搜索日志表不可用，返回默认统计数据")
                return {
                    'total_searches': 0,
                    'today_searches': 0,
                    'recent_searches': 0,
                    'success_rate': 0,
                    'days': days
                }
            
            supabase_service = await get_supabase_service()
            
            # 计算日期范围
            from datetime import datetime, timedelta
            start_date = (datetime.now() - timedelta(days=days)).isoformat()
            today = datetime.now().date().isoformat()
            
            # 总搜索次数
            total_result = supabase_service.client.table(self.table_name).select('id', count='exact').execute()
            total_searches = total_result.count if total_result.count else 0
            
            # 今日搜索次数
            today_result = supabase_service.client.table(self.table_name).select('id', count='exact').gte('created_at', today).execute()
            today_searches = today_result.count if today_result.count else 0
            
            # 最近N天搜索次数
            recent_result = supabase_service.client.table(self.table_name).select('id', count='exact').gte('created_at', start_date).execute()
            recent_searches = recent_result.count if recent_result.count else 0
            
            # 成功率统计
            success_result = supabase_service.client.table(self.table_name).select('id', count='exact').eq('success', True).gte('created_at', start_date).execute()
            success_searches = success_result.count if success_result.count else 0
            
            success_rate = (success_searches / recent_searches * 100) if recent_searches > 0 else 0
            
            return {
                'total_searches': total_searches,
                'today_searches': today_searches,
                'recent_searches': recent_searches,
                'success_rate': round(success_rate, 1),
                'days': days
            }
            
        except Exception as e:
            logger.debug(f"获取搜索统计失败: {e}")
            return {
                'total_searches': 0,
                'today_searches': 0,
                'recent_searches': 0,
                'success_rate': 0,
                'days': days
            }
    
    async def get_popular_routes(self, limit: int = 10, days: int = 30) -> list:
        """
        获取热门路线
        
        Args:
            limit: 返回数量限制
            days: 统计天数
            
        Returns:
            热门路线列表
        """
        try:
            if not await self._ensure_table_exists():
                return []
            
            # 由于Supabase的限制，这里返回空列表，可以在未来优化
            return []
            
        except Exception as e:
            logger.debug(f"获取热门路线失败: {e}")
            return []


# 全局实例
_search_log_service = None

async def get_search_log_service() -> SearchLogService:
    """获取搜索日志服务实例"""
    global _search_log_service
    if _search_log_service is None:
        _search_log_service = SearchLogService()
    return _search_log_service