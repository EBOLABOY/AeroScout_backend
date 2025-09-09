"""
FastAPI版本的监控任务数据模型
基于Pydantic模型，适配原有监控任务结构
"""

from datetime import date, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, validator


class TripType(str, Enum):
    """行程类型枚举"""

    ONE_WAY = "one_way"
    ROUND_TRIP = "round_trip"


class MonitorTaskStatus(str, Enum):
    """监控任务状态枚举"""

    ACTIVE = "active"
    INACTIVE = "inactive"
    PAUSED = "paused"
    COMPLETED = "completed"


class MonitorTaskCreate(BaseModel):
    """创建监控任务请求"""

    name: str = Field(..., min_length=1, max_length=100, description="任务名称")
    description: str | None = Field(None, max_length=500, description="任务描述")
    departure_city: str = Field(..., min_length=1, max_length=50, description="出发城市名称")
    departure_code: str = Field(..., min_length=3, max_length=10, description="出发城市代码")
    destination_city: str | None = Field(None, max_length=50, description="目的地城市（可选）")
    destination_code: str | None = Field(None, max_length=10, description="目的地代码")
    depart_date: date = Field(..., description="出发日期")
    return_date: date | None = Field(None, description="返程日期")
    trip_type: TripType = Field(default=TripType.ROUND_TRIP, description="行程类型")
    price_threshold: float = Field(default=1000.0, ge=0, description="价格阈值")
    check_interval: int = Field(default=30, ge=5, le=1440, description="检查间隔（分钟）")
    notification_enabled: bool = Field(default=True, description="是否启用通知")
    email_notification: bool = Field(default=False, description="是否启用邮件通知")
    pushplus_notification: bool = Field(default=True, description="是否启用PushPlus通知")
    pushplus_token: str | None = Field(None, max_length=255, description="PushPlus令牌")
    blacklist_cities: str | None = Field(None, description="黑名单城市，逗号分隔")
    blacklist_countries: str | None = Field(None, description="黑名单国家，逗号分隔")
    exclude_domestic: bool = Field(default=True, description="是否排除境内航线")

    @validator('departure_code', 'destination_code')
    def validate_airport_codes(cls, v):
        """验证机场代码格式"""
        if v is not None and (not v.isalpha() or len(v) < 3):
            raise ValueError('机场代码必须是至少3位字母')
        return v.upper() if v else v

    @validator('return_date')
    def validate_return_date(cls, v, values):
        """验证返程日期"""
        if v is not None and 'depart_date' in values:
            if v <= values['depart_date']:
                raise ValueError('返程日期必须晚于出发日期')
        return v


class MonitorTaskUpdate(BaseModel):
    """更新监控任务请求"""

    name: str | None = Field(None, min_length=1, max_length=100, description="任务名称")
    description: str | None = Field(None, max_length=500, description="任务描述")
    is_active: bool | None = Field(None, description="是否激活")
    price_threshold: float | None = Field(None, ge=0, description="价格阈值")
    check_interval: int | None = Field(None, ge=5, le=1440, description="检查间隔（分钟）")
    notification_enabled: bool | None = Field(None, description="是否启用通知")
    email_notification: bool | None = Field(None, description="是否启用邮件通知")
    pushplus_notification: bool | None = Field(None, description="是否启用PushPlus通知")
    pushplus_token: str | None = Field(None, max_length=255, description="PushPlus令牌")
    blacklist_cities: str | None = Field(None, description="黑名单城市，逗号分隔")
    blacklist_countries: str | None = Field(None, description="黑名单国家，逗号分隔")
    exclude_domestic: bool | None = Field(None, description="是否排除境内航线")


class MonitorTaskResponse(BaseModel):
    """监控任务响应"""

    id: int = Field(..., description="任务ID")
    user_id: int = Field(..., description="用户ID")
    name: str = Field(..., description="任务名称")
    description: str | None = Field(None, description="任务描述")
    is_active: bool = Field(..., description="是否激活")
    departure_city: str = Field(..., description="出发城市名称")
    departure_code: str = Field(..., description="出发城市代码")
    destination_city: str | None = Field(None, description="目的地城市")
    destination_code: str | None = Field(None, description="目的地代码")
    depart_date: date = Field(..., description="出发日期")
    return_date: date | None = Field(None, description="返程日期")
    trip_type: TripType = Field(..., description="行程类型")
    price_threshold: float = Field(..., description="价格阈值")
    check_interval: int = Field(..., description="检查间隔（分钟）")
    notification_enabled: bool = Field(..., description="是否启用通知")
    email_notification: bool = Field(..., description="是否启用邮件通知")
    pushplus_notification: bool = Field(..., description="是否启用PushPlus通知")
    blacklist_cities: str | None = Field(None, description="黑名单城市")
    blacklist_countries: str | None = Field(None, description="黑名单国家")
    exclude_domestic: bool = Field(..., description="是否排除境内航线")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")
    last_check: datetime | None = Field(None, description="最后检查时间")
    last_notification: datetime | None = Field(None, description="最后通知时间")
    total_checks: int = Field(default=0, description="总检查次数")
    total_notifications: int = Field(default=0, description="总通知次数")


class MonitorTaskStats(BaseModel):
    """监控任务统计"""

    total_tasks: int = Field(..., description="总任务数")
    active_tasks: int = Field(..., description="活跃任务数")
    inactive_tasks: int = Field(..., description="非活跃任务数")
    total_checks_today: int = Field(..., description="今日总检查次数")
    total_notifications_today: int = Field(..., description="今日总通知次数")
    avg_price_threshold: float = Field(..., description="平均价格阈值")


class MonitorTaskListResponse(BaseModel):
    """监控任务列表响应"""

    success: bool = Field(..., description="请求是否成功")
    message: str = Field(..., description="响应消息")
    data: dict[str, Any] = Field(..., description="响应数据")
    total: int = Field(..., description="总数量")
    page: int = Field(..., description="当前页码")
    page_size: int = Field(..., description="每页大小")


class NotificationRecord(BaseModel):
    """通知记录"""

    id: int = Field(..., description="记录ID")
    task_id: int = Field(..., description="任务ID")
    notification_type: str = Field(..., description="通知类型")
    recipient: str = Field(..., description="接收者")
    title: str = Field(..., description="通知标题")
    content: str = Field(..., description="通知内容")
    status: str = Field(..., description="发送状态")
    sent_at: datetime = Field(..., description="发送时间")
    error_message: str | None = Field(None, description="错误信息")


class MonitorTaskExecutionResult(BaseModel):
    """监控任务执行结果"""

    task_id: int = Field(..., description="任务ID")
    execution_time: datetime = Field(..., description="执行时间")
    success: bool = Field(..., description="执行是否成功")
    flights_found: int = Field(..., description="找到的航班数")
    low_price_flights: int = Field(..., description="低价航班数")
    notification_sent: bool = Field(..., description="是否发送通知")
    error_message: str | None = Field(None, description="错误信息")
    execution_duration: float = Field(..., description="执行耗时（秒）")


class MonitorSystemStatus(BaseModel):
    """监控系统状态"""

    is_running: bool = Field(..., description="系统是否运行中")
    start_time: datetime | None = Field(None, description="启动时间")
    total_tasks: int = Field(..., description="总任务数")
    active_tasks: int = Field(..., description="活跃任务数")
    last_execution: datetime | None = Field(None, description="最后执行时间")
    next_execution: datetime | None = Field(None, description="下次执行时间")
    execution_interval: int = Field(..., description="执行间隔（分钟）")
    total_executions: int = Field(..., description="总执行次数")
    successful_executions: int = Field(..., description="成功执行次数")
    failed_executions: int = Field(..., description="失败执行次数")


class APIResponse(BaseModel):
    """通用API响应格式"""

    success: bool = Field(..., description="请求是否成功")
    message: str = Field(..., description="响应消息")
    data: Any | None = Field(None, description="响应数据")
    error: str | None = Field(None, description="错误信息")
