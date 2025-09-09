"""
订阅与配额的 Pydantic 模型
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class SubscriptionStatus(str, Enum):
    trialing = "trialing"
    active = "active"
    past_due = "past_due"
    canceled = "canceled"
    paused = "paused"
    expired = "expired"


class Plan(BaseModel):
    id: str
    slug: str
    name: str
    price_cents: int
    currency: str
    billing_interval: str
    features: dict[str, Any] = Field(default_factory=dict)
    quotas: dict[str, Any] = Field(default_factory=dict)
    is_active: bool


class UserSubscription(BaseModel):
    id: str
    user_id: str
    plan_id: str
    status: SubscriptionStatus
    current_period_end: str | None = None
    cancel_at_period_end: bool = False
    trial_end: str | None = None
    plan: Plan | None = None


class UsageCounter(BaseModel):
    metric: str
    window: str
    period_start: str
    count: int


class SubscriptionOverview(BaseModel):
    plan: Plan | None
    subscription: UserSubscription | None
    quotas: dict[str, Any] = Field(default_factory=dict)
    usage: dict[str, UsageCounter] = Field(default_factory=dict)
