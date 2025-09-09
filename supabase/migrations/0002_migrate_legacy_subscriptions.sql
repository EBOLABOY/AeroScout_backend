-- Migrate legacy level-based subscription system into unified plans/subscriptions
-- Safe/idempotent where possible

-- 1) Ensure plans exist for legacy levels (guest, user, plus, pro, vip, max)
insert into public.plans (slug, name, price_cents, currency, billing_interval, features, quotas, is_active, sort_order)
values
  ('guest', '游客', 0, 'CNY', 'month',
    jsonb_build_object('ai_model','GLM-4.5'),
    jsonb_build_object('daily_flight_searches', 3, 'max_active_monitor_tasks', 0),
    true, -20
  ),
  ('user', '用户', 0, 'CNY', 'month',
    jsonb_build_object('ai_model','GLM-4.5'),
    jsonb_build_object('daily_flight_searches', 10, 'max_active_monitor_tasks', 1),
    true, -10
  ),
  ('plus', 'PLUS会员', 2900, 'CNY', 'month',
    jsonb_build_object('ai_model','gemini-2.5-pro'),
    jsonb_build_object('daily_flight_searches', 50, 'max_active_monitor_tasks', 3),
    true, 5
  ),
  ('pro', '专业版', 3900, 'CNY', 'month',
    jsonb_build_object('ai_model','gemini-2.5-pro'),
    jsonb_build_object('daily_flight_searches', 200, 'max_active_monitor_tasks', 5),
    true, 10
  ),
  ('vip', 'VIP', 9900, 'CNY', 'month',
    jsonb_build_object('ai_model','gemini-2.5-pro'),
    jsonb_build_object('daily_flight_searches', 1000, 'max_active_monitor_tasks', 10),
    true, 20
  ),
  ('max', 'MAX', 19900, 'CNY', 'month',
    jsonb_build_object('ai_model','gemini-2.5-pro'),
    jsonb_build_object('daily_flight_searches', 1000, 'max_active_monitor_tasks', 20),
    true, 30
  )
on conflict(slug) do update set
  name = excluded.name,
  price_cents = excluded.price_cents,
  currency = excluded.currency,
  billing_interval = excluded.billing_interval,
  features = excluded.features,
  quotas = excluded.quotas,
  is_active = excluded.is_active,
  sort_order = excluded.sort_order,
  updated_at = now();

-- 2) Migrate active legacy subscriptions (user_subscriptions) into new subscriptions
-- Map legacy level -> plan via level name == plan.slug
insert into public.subscriptions (
  user_id, plan_id, status, start_at, current_period_start, current_period_end,
  cancel_at_period_end, provider, provider_ref, metadata, created_at, updated_at
)
select
  s.user_id::uuid,
  p.id as plan_id,
  'active' as status,
  coalesce(s.started_at, now()) as start_at,
  coalesce(s.started_at, now()) as current_period_start,
  s.expires_at as current_period_end,
  false as cancel_at_period_end,
  'legacy' as provider,
  concat('legacy_level_id:', s.level_id) as provider_ref,
  '{}'::jsonb as metadata,
  now(), now()
from public.user_subscriptions s
join public.user_levels l on l.id = s.level_id
join public.plans p on p.slug = l.name
join public.users u on u.id = s.user_id::uuid
left join public.subscriptions existing on existing.user_id = s.user_id::uuid and existing.plan_id = p.id
where s.is_active = true
  and existing.id is null;

-- 3) Optional: mark legacy tables as read-only by revoking DML from anon/authenticated (safe on hosted projects)
-- Note: Skip if you rely on these roles elsewhere.
do $$ begin
  perform 1;
  exception when others then
    -- ignore permission errors on shared environments
    null;
end $$;

-- 4) Keep legacy tables for 30 days, then drop/rename manually after verification.
-- -- Example commands (COMMENTED OUT by default):
-- alter table if exists public.user_subscriptions rename to legacy_user_subscriptions;
-- alter table if exists public.user_levels rename to legacy_user_levels;
-- alter table if exists public.user_level_limits rename to legacy_user_level_limits;
-- alter table if exists public.user_level_permissions rename to legacy_user_level_permissions;
-- alter table if exists public.user_usage_stats rename to legacy_user_usage_stats;
-- alter table if exists public.api_usage_logs rename to legacy_api_usage_logs;
