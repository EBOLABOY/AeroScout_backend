"""
统一的日志配置模块
避免在多个文件中重复配置日志
"""

import os
import sys

from loguru import logger

from .settings import LOG_LEVEL


def setup_logging(
    level: str = None,
    format_string: str = None,
    enable_file_logging: bool = False,
    log_file_path: str = "logs/fastapi.log",
):
    """
    设置统一的日志配置

    Args:
        level: 日志级别，默认使用配置文件中的设置
        format_string: 日志格式，默认使用标准格式
        enable_file_logging: 是否启用文件日志
        log_file_path: 日志文件路径
    """
    # 移除默认的日志处理器
    logger.remove()

    # 使用配置文件中的日志级别
    if level is None:
        level = LOG_LEVEL

    # 默认日志格式
    if format_string is None:
        format_string = (
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}:{function}:{line}</cyan> - "
            "<level>{message}</level>"
        )

    # 添加控制台日志处理器
    logger.add(sys.stdout, format=format_string, level=level, colorize=True)

    # 添加文件日志处理器（如果启用）
    if enable_file_logging:
        try:
            # 确保日志目录存在
            os.makedirs(os.path.dirname(log_file_path), exist_ok=True)

            logger.add(
                log_file_path,
                format=format_string,
                level=level,
                rotation="10 MB",
                retention="7 days",
                compression="zip",
                encoding="utf-8",
            )

            logger.info(f"文件日志已启用: {log_file_path}")
        except (PermissionError, OSError) as e:
            logger.warning(f"文件日志创建失败，使用控制台日志: {e}")
            # 继续运行，仅使用控制台日志

    logger.info(f"日志系统初始化完成，级别: {level}")


def get_logger(name: str = None):
    """
    获取日志记录器

    Args:
        name: 日志记录器名称

    Returns:
        logger: 配置好的日志记录器
    """
    if name:
        return logger.bind(name=name)
    return logger


# 预配置的日志格式
LOG_FORMATS = {
    "simple": "{time:HH:mm:ss} | {level} | {message}",
    "detailed": (
        "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}:{function}:{line}</cyan> - "
        "<level>{message}</level>"
    ),
    "json": "{time} | {level} | {name} | {function} | {line} | {message}",
    "production": ("{time:YYYY-MM-DD HH:mm:ss} | " "{level: <8} | " "{name}:{function}:{line} - " "{message}"),
}


def setup_production_logging():
    """设置生产环境日志配置"""
    setup_logging(
        level="INFO",
        format_string=LOG_FORMATS["production"],
        enable_file_logging=True,
        log_file_path="logs/production.log",
    )

    # 为AI服务单独设置更详细的日志处理器
    # 确保AI相关错误总是被记录到单独文件
    logger.add(
        "logs/ai_service.log",
        format=LOG_FORMATS["detailed"],
        level="INFO",
        rotation="10 MB",
        retention="7 days",
        compression="zip",
        encoding="utf-8",
        filter=lambda record: "ai" in record["name"].lower() or "ai_" in record["message"].lower(),
    )


def setup_development_logging():
    """设置开发环境日志配置"""
    setup_logging(level="DEBUG", format_string=LOG_FORMATS["detailed"], enable_file_logging=False)


def setup_testing_logging():
    """设置测试环境日志配置"""
    setup_logging(level="WARNING", format_string=LOG_FORMATS["simple"], enable_file_logging=False)
