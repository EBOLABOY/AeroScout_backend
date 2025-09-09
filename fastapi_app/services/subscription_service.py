#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
订阅与配额服务（基于 Supabase）

职责：
- 获取可用套餐、获取用户当前订阅
- 根据套餐配额执行用量检查与计数
- 简单的管理员分配/变更用户套餐（不依赖第三方支付）
"""
from __future__ import annotations

from datetime import datetime, date, timezone, timedelta
from typing import Optional, Dict, Any, List, Tuple
from loguru import logger

from fastapi_app.config.supabase_config import get_supabase_client


ACTIVE_STATUSES = {"trialing", "active", "past_due", "paused"}


class SubscriptionService:
    def __init__(self):
        self.client = get_supabase_client(use_service_key=True)
        if self.client:
            logger.info("SubscriptionService 初始化完成")
        else:
            logger.error("SubscriptionService 初始化失败：无法创建 Supabase 客户端")

    # -------- Plans --------
    async def list_plans(self, only_active: bool = True) -> List[Dict[str, Any]]:
        try:
            query = self.client.table("plans").select("*")
            if only_active:
                query = query.eq("is_active", True)
            result = query.order("sort_order").execute()
            return result.data or []
        except Exception as e:
            logger.error(f"获取套餐失败: {e}")
            return []

    async def get_plan_by_slug(self, slug: str) -> Optional[Dict[str, Any]]:
        try:
            result = self.client.table("plans").select("*").eq("slug", slug).limit(1).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            logger.error(f"根据 slug 获取套餐失败: {e}")
            return None

    async def get_plan_by_id(self, plan_id: str) -> Optional[Dict[str, Any]]:
        try:
            result = self.client.table("plans").select("*").eq("id", plan_id).limit(1).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            logger.error(f"根据 id 获取套餐失败: {e}")
            return None

    # -------- Subscriptions --------
    async def get_active_subscription(self, user_id: str) -> Optional[Dict[str, Any]]:
        try:
            result = (
                self.client
                .table("subscriptions")
                .select("*")
                .eq("user_id", user_id)
                .in_("status", list(ACTIVE_STATUSES))
                .order("created_at", desc=True)
                .limit(1)
                .execute()
            )
            sub = result.data[0] if result.data else None
            if sub:
                plan = await self.get_plan_by_id(sub["plan_id"]) if sub.get("plan_id") else None
                sub["plan"] = plan
            return sub
        except Exception as e:
            logger.error(f"获取用户订阅失败: {e}")
            return None

    async def assign_subscription(self, user_id: str, plan_slug: str, trial_days: int = 0, period_days: int = 31, cancel_at_period_end: bool = False) -> Optional[Dict[str, Any]]:
        """
        直接为用户分配订阅（管理员/系统使用）。
        默认创建当期周期为 ~1 月。
        """
        try:
            plan = await self.get_plan_by_slug(plan_slug)
            if not plan:
                logger.warning(f"套餐不存在: {plan_slug}")
                return None

            # 结束其它活跃订阅
            try:
                self.client.table("subscriptions").update({"status": "canceled", "canceled_at": datetime.now(timezone.utc).isoformat()}).eq("user_id", user_id).in_("status", list(ACTIVE_STATUSES)).execute()
            except Exception:
                pass

            now = datetime.now(timezone.utc)
            trial_end = (now.replace(tzinfo=timezone.utc) if trial_days <= 0 else now + timedelta(days=trial_days))
            period_end = now + timedelta(days=max(1, period_days))

            data = {
                "user_id": user_id,
                "plan_id": plan["id"],
                "status": "trialing" if trial_days > 0 else "active",
                "start_at": now.isoformat(),
                "current_period_start": now.isoformat(),
                "current_period_end": period_end.isoformat(),
                "cancel_at_period_end": bool(cancel_at_period_end),
                "trial_end": trial_end.isoformat() if trial_days > 0 else None,
            }
            result = self.client.table("subscriptions").insert(data).execute()
            sub = result.data[0] if result.data else None
            if sub:
                sub["plan"] = plan
            return sub
        except Exception as e:
            logger.error(f"分配订阅失败: {e}")
            return None

    async def cancel_subscription(self, user_id: str, immediate: bool = False) -> bool:
        """取消用户订阅。immediate=True 立即取消，否则仅标记到期取消。"""
        try:
            now = datetime.now(timezone.utc).isoformat()
            if immediate:
                self.client.table("subscriptions").update({
                    "status": "canceled",
                    "canceled_at": now,
                    "cancel_at_period_end": True
                }).eq("user_id", user_id).in_("status", list(ACTIVE_STATUSES)).execute()
            else:
                self.client.table("subscriptions").update({
                    "cancel_at_period_end": True
                }).eq("user_id", user_id).in_("status", list(ACTIVE_STATUSES)).execute()
            return True
        except Exception as e:
            logger.error(f"取消订阅失败: {e}")
            return False

    # -------- Expiration cycle (auto-downgrade) --------
    async def check_and_expire_subscriptions(self, remind_days: int = 3, send_reminders: bool = False) -> Dict[str, int]:
        """
        扫描订阅并执行自动降级/取消，以及（可选）到期提醒。

        - 若 cancel_at_period_end=True 且已到期 => 置为 canceled
        - 否则已到期的活跃/trialing/past_due => 置为 expired
        - 可选：对未来 remind_days 内到期的活跃订阅发送提醒
        """
        stats = {"canceled": 0, "expired": 0, "reminded": 0}
        now = datetime.now(timezone.utc)

        try:
            # 1) 到期且标记期末取消 => 取消
            try:
                res_cancel = (
                    self.client.table("subscriptions").update({
                        "status": "canceled",
                        "canceled_at": now.isoformat(),
                        "updated_at": now.isoformat()
                    })
                    .lte("current_period_end", now.isoformat())
                    .eq("cancel_at_period_end", True)
                    .in_("status", ["trialing", "active", "past_due"])  # paused 保留
                    .execute()
                )
                stats["canceled"] = len(res_cancel.data or [])
            except Exception as e:
                logger.error(f"批量取消失败: {e}")

            # 2) 其他到期 => 过期
            try:
                res_expire = (
                    self.client.table("subscriptions").update({
                        "status": "expired",
                        "updated_at": now.isoformat()
                    })
                    .lte("current_period_end", now.isoformat())
                    .eq("cancel_at_period_end", False)
                    .in_("status", ["trialing", "active", "past_due"])  # paused 保留
                    .execute()
                )
                stats["expired"] = len(res_expire.data or [])
            except Exception as e:
                logger.error(f"批量过期失败: {e}")

            # 3) 提醒即将到期
            if send_reminders and remind_days > 0:
                try:
                    upcoming = now + timedelta(days=remind_days)
                    res_due = (
                        self.client.table("subscriptions").select("*")
                        .gt("current_period_end", now.isoformat())
                        .lte("current_period_end", upcoming.isoformat())
                        .in_("status", ["trialing", "active", "past_due"])  # 即将到期
                        .execute()
                    )
                    subs = res_due.data or []
                    if subs:
                        try:
                            from fastapi_app.services.notification_service import get_notification_service
                        except Exception:
                            get_notification_service = None
                        notified = 0
                        for sub in subs:
                            user_id = sub.get("user_id")
                            # 查用户邮箱
                            email = None
                            try:
                                ures = self.client.table("users").select("email,username").eq("id", user_id).limit(1).execute()
                                if ures.data:
                                    email = (ures.data[0] or {}).get("email")
                                    username = (ures.data[0] or {}).get("username") or "用户"
                                else:
                                    username = "用户"
                            except Exception:
                                username = "用户"

                            if email and get_notification_service:
                                try:
                                    svc = get_notification_service()
                                    plan_info = await self.get_plan_by_id(sub.get("plan_id"))
                                    plan_name = plan_info.get("name") if plan_info else "订阅"
                                    end_at = sub.get("current_period_end")
                                    subject = "【Ticketradar】订阅即将到期提醒"
                                    html = f"<p>您好，{username}：</p><p>您的 {plan_name} 将于 {end_at} 到期。</p><p>为避免服务中断，请及时续费。</p>"
                                    text = f"您好，{username}：\n您的 {plan_name} 将于 {end_at} 到期。为避免服务中断，请及时续费。"
                                    ok = await svc.send_email_notification(email, subject, html, text)
                                    if ok:
                                        notified += 1
                                except Exception as e:
                                    logger.warning(f"发送到期提醒失败: {e}")
                        stats["reminded"] = notified
                except Exception as e:
                    logger.error(f"查询即将到期订阅失败: {e}")

        except Exception as e:
            logger.error(f"订阅到期检测失败: {e}")

        logger.info(f"订阅到期处理: canceled={stats['canceled']}, expired={stats['expired']}, reminded={stats['reminded']}")
        return stats

    # -------- Quotas & Usage --------
    async def get_user_quotas(self, user_id: str) -> Dict[str, Any]:
        sub = await self.get_active_subscription(user_id)
        if sub and sub.get("plan"):
            return sub["plan"].get("quotas", {}) or {}
        # fallback: free defaults
        return {"daily_flight_searches": 20, "max_active_monitor_tasks": 1}

    def _today(self) -> date:
        return datetime.now(timezone.utc).date()

    async def get_usage(self, user_id: str, metric: str, window: str = "daily") -> int:
        try:
            today = self._today()
            result = (
                self.client.table("usage_counters").select("*")
                .eq("user_id", user_id).eq("metric", metric).eq("time_window", window)
                .eq("period_start", today.isoformat())
                .limit(1).execute()
            )
            row = result.data[0] if result.data else None
            return int(row["count"]) if row else 0
        except Exception as e:
            logger.error(f"获取用量失败: {e}")
            return 0

    async def increment_usage(self, user_id: str, metric: str, window: str = "daily", by: int = 1) -> int:
        today = self._today()
        try:
            # upsert-like: try update, if 0 then insert
            upd = self.client.table("usage_counters").update({
                "count": self.client.rpc("sql", {"q": "count + 1"}) if False else None  # placeholder, will do read-modify-write below
            })
        except Exception:
            pass
        # simple read-modify-write
        current = await self.get_usage(user_id, metric, window)
        new_count = max(0, current) + max(1, by)
        try:
            # try update
            result = (
                self.client.table("usage_counters").update({
                    "count": new_count,
                    "updated_at": datetime.now(timezone.utc).isoformat()
                })
                .eq("user_id", user_id).eq("metric", metric).eq("time_window", window)
                .eq("period_start", today.isoformat()).execute()
            )
            if not result.data:
                # insert
                self.client.table("usage_counters").insert({
                    "user_id": user_id,
                    "metric": metric,
                    "time_window": window,
                    "period_start": today.isoformat(),
                    "count": new_count
                }).execute()
            return new_count
        except Exception as e:
            logger.error(f"递增用量失败: {e}")
            return current

    async def enforce_quota(self, user_id: str, metric: str, window: str = "daily", increment: int = 1) -> Tuple[bool, Dict[str, Any]]:
        quotas = await self.get_user_quotas(user_id)
        limit_key = None
        if metric == "flight_searches":
            limit_key = "daily_flight_searches" if window == "daily" else None
        # future: map more metrics

        if limit_key is None or limit_key not in quotas:
            # no limit configured -> allow and still record
            count = await self.increment_usage(user_id, metric, window, by=increment)
            return True, {"limit": None, "used": count}

        limit = int(quotas.get(limit_key) or 0)
        used = await self.get_usage(user_id, metric, window)
        if used + increment > limit:
            return False, {"limit": limit, "used": used}

        used = await self.increment_usage(user_id, metric, window, by=increment)
        return True, {"limit": limit, "used": used}

    async def get_active_monitor_tasks(self, user_id: str) -> int:
        try:
            result = self.client.table("monitor_tasks").select("id", count="exact").eq("user_id", user_id).eq("is_active", True).execute()
            return int(result.count or 0)
        except Exception as e:
            logger.error(f"统计活跃监控任务失败: {e}")
            return 0


_subscription_service: Optional[SubscriptionService] = None


async def get_subscription_service() -> SubscriptionService:
    global _subscription_service
    if _subscription_service is None:
        _subscription_service = SubscriptionService()
    return _subscription_service
