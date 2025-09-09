#!/usr/bin/env python3
"""
FastAPI应用启动脚本
"""

import asyncio
import os
import platform
import sys
from contextlib import asynccontextmanager

from loguru import logger

# Windows环境下设置事件循环策略以支持子进程
if platform.system() == "Windows":
    # 设置ProactorEventLoop以支持子进程
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    logger.info("🔧 Windows环境：已设置ProactorEventLoop策略以支持子进程")

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

# 导入配置
from fastapi_app.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时执行
    from fastapi_app.config.logging_config import setup_logging
    from fastapi_app.config.settings import LOG_LEVEL

    # 根据LOG_LEVEL环境变量配置日志
    setup_logging(level=LOG_LEVEL)

    logger.info("🚀 FastAPI应用启动中...")

    try:
        # 初始化 Supabase 服务
        from fastapi_app.services.supabase_service import get_supabase_service

        supabase_service = await get_supabase_service()
        health_ok = await supabase_service.health_check()
        if health_ok:
            logger.info("✅ Supabase 数据库连接正常")
        else:
            logger.warning("⚠️ Supabase 数据库连接异常")

        # 初始化缓存服务
        try:
            from fastapi_app.services.cache_service import get_cache_service

            cache_service = await get_cache_service()
            if cache_service:
                await cache_service.warm_up_cache()
                logger.info("✅ Redis缓存服务初始化完成")
            else:
                logger.warning("⚠️ Redis缓存服务未启用，将使用内存缓存")
        except Exception as e:
            logger.warning(f"⚠️ 缓存服务初始化失败，将不使用缓存: {e}")

        # 自动启动监控系统
        try:
            from fastapi_app.services.monitor_service import get_monitor_service

            monitor_service = get_monitor_service()
            success = await monitor_service.start_monitoring()
            if success:
                logger.info("✅ 监控系统自动启动成功")
            else:
                logger.info("ℹ️ 监控系统已在运行")
        except Exception as e:
            logger.warning(f"⚠️ 监控系统启动失败: {e}")

        # 启动订阅到期检查后台任务（按配置周期执行）
        try:
            from fastapi_app.services.subscription_service import get_subscription_service

            interval_hours = getattr(settings, 'SUBSCRIPTION_CHECK_INTERVAL_HOURS', 24) or 24
            remind_days = getattr(settings, 'SUBSCRIPTION_REMIND_DAYS', 3) or 3

            async def subscription_expiration_worker():
                try:
                    svc = await get_subscription_service()
                    # 启动时先跑一轮
                    await svc.check_and_expire_subscriptions(remind_days=remind_days, send_reminders=False)
                    while True:
                        await asyncio.sleep(int(interval_hours) * 3600)
                        await svc.check_and_expire_subscriptions(remind_days=remind_days, send_reminders=False)
                except asyncio.CancelledError:
                    logger.info("订阅到期检查任务已取消")
                except Exception as e:
                    logger.error(f"订阅到期检查任务异常: {e}")

            asyncio.create_task(subscription_expiration_worker())
            logger.info(f"⏰ 订阅到期检查任务已启动，每 {interval_hours} 小时运行一次")
        except Exception as e:
            logger.warning(f"⚠️ 启动订阅到期任务失败: {e}")

        logger.info("✅ FastAPI应用启动完成")
    except Exception as e:
        logger.error(f"❌ 应用启动初始化失败: {e}")
        raise

    yield

    # 关闭时执行
    try:
        # 停止监控系统
        try:
            from fastapi_app.services.monitor_service import get_monitor_service

            monitor_service = get_monitor_service()
            success = await monitor_service.stop_monitoring()
            if success:
                logger.info("✅ 监控系统已停止")
            else:
                logger.info("ℹ️ 监控系统未在运行")
        except Exception as e:
            logger.warning(f"⚠️ 停止监控系统失败: {e}")

        # 关闭缓存服务
        try:
            from fastapi_app.services.cache_service import close_cache_service

            await close_cache_service()
            logger.info("✅ 缓存服务已关闭")
        except Exception as e:
            logger.warning(f"⚠️ 缓存服务关闭失败: {e}")

        # Supabase 连接由客户端自动管理，无需手动关闭
        logger.info("✅ Supabase 连接已释放")
        logger.info("👋 FastAPI应用已停止")
    except Exception as e:
        logger.error(f"❌ 应用关闭清理失败: {e}")


def create_fastapi_app() -> FastAPI:
    """创建FastAPI应用"""

    # 创建FastAPI实例
    app = FastAPI(
        title="Ticketradar API",
        description="机票监控和AI旅行规划系统",
        version="2.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
        debug=settings.DEBUG,
    )

    # 配置CORS（支持SSE）
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["*"],  # 支持SSE所需的头部
    )

    # 配置受信任主机
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.TRUSTED_HOSTS)

    # 设置性能优化中间件
    from fastapi_app.middleware import setup_performance_middleware

    app = setup_performance_middleware(app)

    # 注册路由
    from fastapi_app.routers import admin, flights, monitor, subscription
    from fastapi_app.routers import auth_supabase as auth

    app.include_router(auth.router, prefix="/auth", tags=["认证"])
    app.include_router(subscription.router, prefix="/api/subscription", tags=["订阅"])
    app.include_router(monitor.router, prefix="/api/monitor", tags=["监控"])
    app.include_router(flights.router, prefix="/api/flights", tags=["航班"])
    app.include_router(admin.router, prefix="/api/admin", tags=["管理员"])

    # 所有API统一使用 /api 前缀

    # 根路径
    @app.get("/")
    async def root():
        return {
            "message": f"Ticketradar FastAPI服务 - {'调试' if settings.DEBUG else '生产'}模式",
            "version": "2.0.0",
            "docs": "/docs",
            "debug": settings.DEBUG,
        }

    # 健康检查
    @app.get("/health")
    async def health_check():
        return {"status": "healthy", "framework": "FastAPI"}

    return app


# 创建应用实例
app = create_fastapi_app()


if __name__ == "__main__":
    import uvicorn

    # 日志配置已移至lifespan上下文

    # 启动服务器
    host = os.environ.get('SERVER_HOST', '0.0.0.0')
    port = int(os.environ.get('SERVER_PORT', 38181))  # 使用38181端口

    logger.info(f"🚀 启动FastAPI服务器于 http://{host}:{port}")
    logger.info("📚 API文档: http://localhost:38181/docs")

    uvicorn.run(
        "main_fastapi:app",
        host=host,
        port=port,
        reload=settings.DEBUG,  # 仅调试模式启用自动重载
        log_level="debug" if settings.DEBUG else "info",  # 根据DEBUG设置日志级别
        reload_dirs=["./fastapi_app", "./app"] if settings.DEBUG else None,  # 仅调试模式监控目录
        reload_excludes=["*.pyc", "__pycache__", "*.log", "*.db"] if settings.DEBUG else None,
    )
