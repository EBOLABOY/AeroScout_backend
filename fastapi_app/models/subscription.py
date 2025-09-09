"""
订阅与配额的 Pydantic 模型
"""
from __future__ import annotations
from typing import Optional, Dict, Any
from enum import Enum
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
    features: Dict[str, Any] = Field(default_factory=dict)
    quotas: Dict[str, Any] = Field(default_factory=dict)
    is_active: bool


class UserSubscription(BaseModel):
    id: str
    user_id: str
    plan_id: str
    status: SubscriptionStatus
    current_period_end: Optional[str] = None
    cancel_at_period_end: bool = False
    trial_end: Optional[str] = None
    plan: Optional[Plan] = None


class UsageCounter(BaseModel):
    metric: str
    window: str
    period_start: str
    count: int


class SubscriptionOverview(BaseModel):
    plan: Optional[Plan]
    subscription: Optional[UserSubscription]
    quotas: Dict[str, Any] = Field(default_factory=dict)
    usage: Dict[str, UsageCounter] = Field(default_factory=dict)

