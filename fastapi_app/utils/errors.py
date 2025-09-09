#!/usr/bin/env python3
"""
标准化错误处理模块
"""

from enum import Enum
from typing import Any

from fastapi import HTTPException, status
from pydantic import BaseModel


class ErrorCode(Enum):
    """标准错误代码枚举"""

    # 权限相关错误
    PERMISSION_DENIED = "PERMISSION_DENIED"
    INSUFFICIENT_LEVEL = "INSUFFICIENT_LEVEL"
    AUTHENTICATION_REQUIRED = "AUTHENTICATION_REQUIRED"

    # 配额相关错误
    QUOTA_EXCEEDED = "QUOTA_EXCEEDED"
    QUOTA_LIMIT_REACHED = "QUOTA_LIMIT_REACHED"
    INVALID_QUOTA_TYPE = "INVALID_QUOTA_TYPE"

    # 用户等级相关错误
    INVALID_USER_LEVEL = "INVALID_USER_LEVEL"
    LEVEL_UPGRADE_REQUIRED = "LEVEL_UPGRADE_REQUIRED"
    LEVEL_NOT_FOUND = "LEVEL_NOT_FOUND"

    # 搜索相关错误
    INVALID_SEARCH_PARAMS = "INVALID_SEARCH_PARAMS"
    SEARCH_SERVICE_UNAVAILABLE = "SEARCH_SERVICE_UNAVAILABLE"
    AI_SERVICE_UNAVAILABLE = "AI_SERVICE_UNAVAILABLE"

    # 系统相关错误
    INTERNAL_ERROR = "INTERNAL_ERROR"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"

    # 数据相关错误
    DATA_NOT_FOUND = "DATA_NOT_FOUND"
    INVALID_DATA_FORMAT = "INVALID_DATA_FORMAT"
    DATABASE_ERROR = "DATABASE_ERROR"


class ErrorDetail(BaseModel):
    """错误详情模型"""

    code: str = ""
    message: str = ""
    field: str | None = None
    details: dict[str, Any] | None = None


class StandardErrorResponse(BaseModel):
    """标准错误响应模型"""

    success: bool = False
    error_code: str
    message: str
    details: dict[str, Any] | None = None

    # 用户等级相关信息
    current_level: str | None = None
    required_level: str | None = None
    upgrade_url: str | None = "/pricing"

    # 配额相关信息
    quota_info: dict[str, Any] | None = None

    # 建议操作
    suggested_actions: list[str] | None = None

    # 支持信息
    support_info: dict[str, str] | None = None


class UserLevelError:
    """用户等级相关错误工具类"""

    @staticmethod
    def insufficient_level(current_level: str, required_level: str, feature_name: str = "此功能") -> HTTPException:
        """用户等级不足错误"""
        return HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=StandardErrorResponse(
                error_code=ErrorCode.INSUFFICIENT_LEVEL.value,
                message=f"{feature_name}需要 {required_level} 及以上等级",
                current_level=current_level,
                required_level=required_level,
                suggested_actions=[f"升级到 {required_level} 等级", "查看等级权益对比", "联系客服了解升级优惠"],
                support_info={"pricing_url": "/pricing", "contact_url": "/contact"},
            ).model_dump(),
        )

    @staticmethod
    def invalid_level(level_name: str) -> HTTPException:
        """无效用户等级错误"""
        return HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=StandardErrorResponse(
                error_code=ErrorCode.INVALID_USER_LEVEL.value,
                message=f"无效的用户等级: {level_name}",
                details={"invalid_level": level_name},
                suggested_actions=["检查等级名称是否正确", "查看可用的用户等级列表"],
            ).model_dump(),
        )


class QuotaError:
    """配额相关错误工具类"""

    @staticmethod
    def quota_exceeded(quota_type: str, used: int, limit: int, reset_time: str = "明日00:00") -> HTTPException:
        """配额已用完错误"""
        return HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=StandardErrorResponse(
                error_code=ErrorCode.QUOTA_EXCEEDED.value,
                message=f"今日{quota_type}配额已用完",
                quota_info={
                    "quota_type": quota_type,
                    "used_today": used,
                    "daily_limit": limit,
                    "remaining": max(0, limit - used),
                    "reset_time": reset_time,
                },
                suggested_actions=["等待配额重置", "升级到更高等级获得更多配额", "查看等级权益对比"],
                support_info={"pricing_url": "/pricing", "reset_time": reset_time},
            ).model_dump(),
        )

    @staticmethod
    def quota_limit_reached(quota_type: str, current_level: str, next_level: str) -> HTTPException:
        """配额限制已达到错误"""
        return HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=StandardErrorResponse(
                error_code=ErrorCode.QUOTA_LIMIT_REACHED.value,
                message=f"{current_level}等级的{quota_type}配额限制已达到",
                current_level=current_level,
                required_level=next_level,
                suggested_actions=[f"升级到 {next_level} 等级获得更多配额", "等待配额重置", "查看详细使用统计"],
                support_info={"pricing_url": "/pricing", "stats_url": "/auth/stats/daily"},
            ).model_dump(),
        )


class SearchError:
    """搜索相关错误工具类"""

    @staticmethod
    def invalid_params(param_errors: dict[str, str]) -> HTTPException:
        """无效搜索参数错误"""
        return HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=StandardErrorResponse(
                error_code=ErrorCode.INVALID_SEARCH_PARAMS.value,
                message="搜索参数无效",
                details={"param_errors": param_errors},
                suggested_actions=[
                    "检查机场代码格式（3位字母）",
                    "确认日期格式正确（YYYY-MM-DD）",
                    "验证乘客数量在有效范围内",
                ],
            ).model_dump(),
        )

    @staticmethod
    def service_unavailable(service_name: str) -> HTTPException:
        """搜索服务不可用错误"""
        return HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=StandardErrorResponse(
                error_code=ErrorCode.SEARCH_SERVICE_UNAVAILABLE.value,
                message=f"{service_name}服务暂时不可用",
                suggested_actions=["稍后重试", "尝试使用基础搜索功能", "联系客服报告问题"],
                support_info={"contact_url": "/contact", "status_url": "/status"},
            ).model_dump(),
        )

    @staticmethod
    def ai_service_unavailable() -> HTTPException:
        """AI服务不可用错误"""
        return HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=StandardErrorResponse(
                error_code=ErrorCode.AI_SERVICE_UNAVAILABLE.value,
                message="AI搜索服务暂时不可用",
                suggested_actions=["使用基础搜索功能", "稍后重试AI搜索", "查看服务状态页面"],
                support_info={"fallback_url": "/api/flights/search", "status_url": "/status"},
            ).model_dump(),
        )


class SystemError:
    """系统错误工具类"""

    @staticmethod
    def internal_error(error_id: str | None = None) -> HTTPException:
        """内部系统错误"""
        return HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=StandardErrorResponse(
                error_code=ErrorCode.INTERNAL_ERROR.value,
                message="系统内部错误",
                details={"error_id": error_id} if error_id else None,
                suggested_actions=["稍后重试", "如问题持续请联系客服"],
                support_info={"contact_url": "/contact", "error_id": error_id},
            ).model_dump(),
        )

    @staticmethod
    def database_error() -> HTTPException:
        """数据库错误"""
        return HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=StandardErrorResponse(
                error_code=ErrorCode.DATABASE_ERROR.value,
                message="数据库服务暂时不可用",
                suggested_actions=["稍后重试", "联系客服报告问题"],
                support_info={"contact_url": "/contact"},
            ).model_dump(),
        )


def create_upgrade_prompt(current_level: str, feature_name: str) -> dict[str, Any]:
    """创建升级提示信息"""
    level_hierarchy = ['guest', 'user', 'plus', 'pro', 'max', 'vip']

    try:
        current_index = level_hierarchy.index(current_level.lower())
        if current_index < len(level_hierarchy) - 1:
            next_level = level_hierarchy[current_index + 1]
        else:
            next_level = 'vip'
    except ValueError:
        next_level = 'plus'

    return {
        "current_level": current_level,
        "recommended_level": next_level,
        "feature_name": feature_name,
        "upgrade_benefits": f"升级到{next_level}等级可使用{feature_name}功能",
        "pricing_url": "/pricing",
    }
