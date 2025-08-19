"""
Supabase 配置和连接管理
统一使用 settings.py 中的配置，避免重复
"""
from typing import Optional
from supabase import create_client, Client
from loguru import logger

# 导入统一配置
from .settings import (
    SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_SERVICE_ROLE_KEY,
    SUPABASE_DATABASE_URL, USE_SUPABASE
)


class SupabaseConfig:
    """Supabase 配置类"""
    
    def __init__(self):
        # 使用统一配置
        self.supabase_url = SUPABASE_URL
        self.supabase_key = SUPABASE_ANON_KEY
        self.supabase_service_key = SUPABASE_SERVICE_ROLE_KEY
        self.database_url = SUPABASE_DATABASE_URL

        # 验证配置
        self._validate_config()
    
    def _validate_config(self):
        """验证 Supabase 配置"""
        if not USE_SUPABASE:
            logger.info("Supabase 未启用，将使用本地数据库")
        elif not self.is_configured:
            logger.warning("Supabase 配置不完整，某些功能可能无法使用")

    @property
    def is_configured(self) -> bool:
        """检查 Supabase 是否已正确配置"""
        return USE_SUPABASE
    
    def get_client(self, use_service_key: bool = False) -> Optional[Client]:
        """获取 Supabase 客户端"""
        if not self.is_configured:
            logger.error("Supabase 配置不完整")
            return None
        
        try:
            key = self.supabase_service_key if use_service_key and self.supabase_service_key else self.supabase_key
            client = create_client(self.supabase_url, key)
            logger.info("Supabase 客户端创建成功")
            return client
        except Exception as e:
            logger.error(f"创建 Supabase 客户端失败: {e}")
            return None


# 全局配置实例
supabase_config = SupabaseConfig()


def get_supabase_client(use_service_key: bool = False) -> Optional[Client]:
    """获取 Supabase 客户端实例"""
    return supabase_config.get_client(use_service_key)


def get_database_url() -> str:
    """获取数据库连接 URL"""
    if supabase_config.database_url:
        return supabase_config.database_url
    
    # 如果没有直接的数据库 URL，使用 SQLite 作为后备
    return "sqlite+aiosqlite:///./ticketradar.db"
