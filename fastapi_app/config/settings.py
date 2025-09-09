#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FastAPI 应用配置设置 - 纯Supabase方案
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# 加载环境变量文件
backend_root = Path(__file__).parent.parent.parent
env_path = backend_root / ".env"
load_dotenv(env_path)

# 基本配置
DEBUG = os.getenv("DEBUG", "True").lower() == "true"
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-here")

# Supabase 配置（主数据库和认证）
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
SUPABASE_DATABASE_URL = os.getenv("SUPABASE_DATABASE_URL")
SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET")

# Redis 缓存配置
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# AI 服务配置
AI_API_KEY = os.getenv("AI_API_KEY")
AI_API_URL = os.getenv("AI_API_URL", "http://154.19.184.12:3000/v1")
AI_MODEL_AUTHENTICATED = os.getenv("AI_MODEL_AUTHENTICATED", "gemini-2.5-pro")

# 数据保存配置（默认关闭）
SAVE_FLIGHT_DATA = os.getenv("SAVE_FLIGHT_DATA", "false").lower() == "true"

# 日志配置
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# 通知服务配置
NOTIFICATION_COOLDOWN = int(os.getenv("NOTIFICATION_COOLDOWN", 24))  # 小时

# 网站配置（用于Supabase回调）
SITE_URL = os.getenv("SITE_URL", "http://localhost:3000")

# 测试数据保存配置
ENABLE_TEST_DATA_SAVE = os.getenv("ENABLE_TEST_DATA_SAVE", "False").lower() == "true"
TEST_DATA_DIR = os.getenv("TEST_DATA_DIR", "./test_data")

# 订阅任务配置
SUBSCRIPTION_CHECK_INTERVAL_HOURS = int(os.getenv("SUBSCRIPTION_CHECK_INTERVAL_HOURS", "24"))
SUBSCRIPTION_REMIND_DAYS = int(os.getenv("SUBSCRIPTION_REMIND_DAYS", "3"))






# CORS 配置
CORS_ORIGINS = [
    "http://localhost:30000",
    "http://127.0.0.1:30000",
    "http://localhost:38181",
    "http://127.0.0.1:38181",
    "https://ticketradar.izlx.de",
    "http://ticketradar.izlx.de"
]

# 受信任主机
# 在Docker环境中，由于Nginx代理和容器网络的复杂性，
# 使用更宽松的策略，安全性由外层Nginx和防火墙保证
TRUSTED_HOSTS = ["*"]

# 日志配置
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# 应用信息
APP_NAME = "Ticketradar API"
APP_VERSION = "2.0.0"
APP_DESCRIPTION = "机票监控和AI旅行规划系统"

# 配置验证
def validate_config():
    """验证配置"""
    errors = []
    
    # Supabase 配置验证（必需）
    if not SUPABASE_URL:
        errors.append("SUPABASE_URL is required")
    if not SUPABASE_ANON_KEY:
        errors.append("SUPABASE_ANON_KEY is required")
    
    if not AI_API_KEY:
        errors.append("AI_API_KEY is required for AI services")
    
    if errors:
        raise ValueError(f"Configuration errors: {', '.join(errors)}")

# 在导入时验证配置
try:
    validate_config()
except ValueError as e:
    print(f"⚠️  Configuration warning: {e}")

# 配置摘要
def get_config_summary():
    """获取配置摘要"""
    return {
        "app_name": APP_NAME,
        "app_version": APP_VERSION,
        "debug": DEBUG,
        "server": "uvicorn (configured via CLI)",
        "database": "Supabase",
        "ai_service": "Gemini (OpenAI API)" if AI_API_KEY else "None",
        "cache": "Redis" if REDIS_URL else "Memory",

    }

# 创建settings对象以便导入
class Settings:
    """配置设置类"""
    def __init__(self):
        # 基本配置
        self.DEBUG = DEBUG
        self.SECRET_KEY = SECRET_KEY
        self.APP_NAME = APP_NAME
        self.APP_VERSION = APP_VERSION



        # 数据库配置（Supabase）
        self.SUPABASE_URL = SUPABASE_URL
        self.SUPABASE_ANON_KEY = SUPABASE_ANON_KEY
        self.SUPABASE_SERVICE_ROLE_KEY = SUPABASE_SERVICE_ROLE_KEY
        self.SUPABASE_DATABASE_URL = SUPABASE_DATABASE_URL
        self.SUPABASE_JWT_SECRET = SUPABASE_JWT_SECRET

        # AI配置
        self.AI_API_KEY = AI_API_KEY
        self.AI_API_URL = AI_API_URL
        self.AI_MODEL_AUTHENTICATED = AI_MODEL_AUTHENTICATED

        # 数据保存配置
        self.SAVE_FLIGHT_DATA = SAVE_FLIGHT_DATA
        self.ENABLE_TEST_DATA_SAVE = ENABLE_TEST_DATA_SAVE
        self.TEST_DATA_DIR = TEST_DATA_DIR

        # CORS配置
        self.CORS_ORIGINS = CORS_ORIGINS

        # 其他配置
        self.REDIS_URL = REDIS_URL

        # 订阅后台任务
        self.SUBSCRIPTION_CHECK_INTERVAL_HOURS = SUBSCRIPTION_CHECK_INTERVAL_HOURS
        self.SUBSCRIPTION_REMIND_DAYS = SUBSCRIPTION_REMIND_DAYS

        # 信任的主机列表
        self.TRUSTED_HOSTS = TRUSTED_HOSTS  # 使用配置文件中的设置，而非硬编码
    
    def get_config_summary(self):
        """获取配置摘要"""
        return get_config_summary()

# 创建全局settings实例
settings = Settings()
