#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FastAPI 应用配置设置
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# 加载Backend目录的环境变量文件
backend_root = Path(__file__).parent.parent.parent
env_path = backend_root / ".env"
load_dotenv(env_path)

# 基本配置
DEBUG = os.getenv("DEBUG", "True").lower() == "true"
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-here")

# 数据库配置（本地 SQLite 作为后备）
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./ticketradar.db")

# Supabase 配置
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
SUPABASE_DATABASE_URL = os.getenv("SUPABASE_DATABASE_URL")

# 使用 Supabase 作为主数据库
USE_SUPABASE = bool(SUPABASE_URL and SUPABASE_ANON_KEY)
if USE_SUPABASE:
    DATABASE_URL = SUPABASE_DATABASE_URL or DATABASE_URL

# JWT 配置
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", SECRET_KEY)
JWT_ALGORITHM = "HS256"
JWT_ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", 30))

# Redis 配置
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# AI 服务配置 - OpenAI 格式的第三方 Gemini API
AI_API_KEY = os.getenv("AI_API_KEY")
AI_API_URL = os.getenv("AI_API_URL", "http://154.19.184.12:3000/v1")
AI_MODEL = os.getenv("AI_MODEL", "gemini-2.5-pro")

# 登录用户专用AI模型配置
AI_MODEL_AUTHENTICATED = os.getenv("AI_MODEL_AUTHENTICATED", "gemini-2.5-pro")

# 测试数据保存配置
ENABLE_TEST_DATA_SAVE = os.getenv("ENABLE_TEST_DATA_SAVE", "False").lower() == "true"
TEST_DATA_DIR = os.getenv("TEST_DATA_DIR", "./test_data")






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
if DEBUG:
    TRUSTED_HOSTS = ["*"]  # 开发模式允许所有主机
else:
    # 生产模式基础主机列表
    base_trusted_hosts = [
        "localhost", 
        "127.0.0.1", 
        "0.0.0.0", 
        "ticketradar.izlx.de",
        "app",  # Docker容器内部服务名
        "ticketradar-app",  # Docker容器名称
        "*.ticketradar-network",  # Docker网络内的主机
        "172.*",  # Docker默认网络段
        "10.*"   # 额外网络段支持
    ]
    
    # 从环境变量添加额外的受信任主机
    extra_hosts = os.getenv("EXTRA_TRUSTED_HOSTS", "")
    if extra_hosts:
        extra_hosts_list = [host.strip() for host in extra_hosts.split(",") if host.strip()]
        base_trusted_hosts.extend(extra_hosts_list)
    
    TRUSTED_HOSTS = base_trusted_hosts

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
    
    if USE_SUPABASE:
        if not SUPABASE_URL:
            errors.append("SUPABASE_URL is required when using Supabase")
        if not SUPABASE_ANON_KEY:
            errors.append("SUPABASE_ANON_KEY is required when using Supabase")
    
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
        "database": "Supabase" if USE_SUPABASE else "SQLite",
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



        # 数据库配置
        self.DATABASE_URL = DATABASE_URL
        self.USE_SUPABASE = USE_SUPABASE
        self.SUPABASE_URL = SUPABASE_URL
        self.SUPABASE_ANON_KEY = SUPABASE_ANON_KEY
        self.SUPABASE_SERVICE_ROLE_KEY = SUPABASE_SERVICE_ROLE_KEY
        self.SUPABASE_DATABASE_URL = SUPABASE_DATABASE_URL

        # AI配置
        self.AI_API_KEY = AI_API_KEY
        self.AI_API_URL = AI_API_URL
        self.AI_MODEL = AI_MODEL
        self.AI_MODEL_AUTHENTICATED = AI_MODEL_AUTHENTICATED

        # 测试数据保存配置
        self.ENABLE_TEST_DATA_SAVE = ENABLE_TEST_DATA_SAVE
        self.TEST_DATA_DIR = TEST_DATA_DIR

        # JWT配置
        self.JWT_SECRET_KEY = JWT_SECRET_KEY
        self.JWT_ALGORITHM = JWT_ALGORITHM
        self.JWT_ACCESS_TOKEN_EXPIRE_MINUTES = JWT_ACCESS_TOKEN_EXPIRE_MINUTES

        # CORS配置
        self.CORS_ORIGINS = CORS_ORIGINS

        # 其他配置
        self.REDIS_URL = REDIS_URL

        # 信任的主机列表
        self.TRUSTED_HOSTS = TRUSTED_HOSTS  # 使用配置文件中的设置，而非硬编码

# 创建全局settings实例
settings = Settings()
