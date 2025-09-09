-- Subscription system schema
-- Safe to run multiple times (IF NOT EXISTS guards)

-- Enable required extensions (ignored if already enabled)
create extension if not exists pgcrypto;

-- users table (app-managed auth)
create table if not exists public.users (
  id uuid primary key,
  username text not null unique,
  email text not null unique,
  password_hash text not null,
  is_active boolean not null default true,
  is_verified boolean not null default false,
  email_verified boolean not null default false,
  is_admin boolean not null default false,
  full_name text,
  phone text,
  avatar_url text,
  notification_enabled boolean default true,
  email_notifications_enabled boolean default false,
  pushplus_token text,
  created_at timestamptz not null default now()
);

-- monitor tasks (subset of columns used by the app)
create table if not exists public.monitor_tasks (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.users(id) on delete cascade,
  task_name text not null,
  departure_code text not null,
  destination_code text not null,
  depart_date date not null,
  return_date date,
  seat_class text default 'economy',
  trip_type text default 'round_trip',
  max_stops int default 2,
  is_active boolean not null default true,
  price_threshold numeric,
  check_interval int default 30,
  notification_enabled boolean default true,
  email_notification boolean default false,
  pushplus_notification boolean default true,
  pushplus_token text,
  blacklist_cities text,
  blacklist_countries text,
  last_check timestamptz,
  last_notification timestamptz,
  total_checks int not null default 0,
  total_notifications int not null default 0,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- password reset tokens
create table if not exists public.password_reset_tokens (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.users(id) on delete cascade,
  token text not null unique,
  token_hash text,
  is_used boolean not null default false,
  expires_at timestamptz,
  used_at timestamptz,
  created_at timestamptz not null default now()
);

-- invite codes (used by admin endpoints)
create table if not exists public.invite_codes (
  id uuid primary key default gen_random_uuid(),
  code text not null unique,
  description text,
  max_uses int not null default 1,
  used_count int not null default 0,
  expires_at timestamptz,
  is_active boolean not null default true,
  created_by uuid references public.users(id) on delete set null,
  created_at timestamptz not null default now()
);

-- plans: available subscription plans
create table if not exists public.plans (
  id uuid primary key default gen_random_uuid(),
  slug text not null unique,              -- e.g., 'free', 'pro'
  name text not null,
  price_cents int not null default 0,
  currency text not null default 'CNY',
  billing_interval text not null default 'month', -- 'month' or 'year'
  features jsonb not null default '{}'::jsonb,
  quotas jsonb not null default '{}'::jsonb,      -- e.g., {"daily_flight_searches": 20, "max_active_monitor_tasks": 1}
  is_active boolean not null default true,
  sort_order int not null default 0,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- subscriptions: user active subscription
create table if not exists public.subscriptions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.users(id) on delete cascade,
  plan_id uuid not null references public.plans(id),
  status text not null default 'active', -- trialing, active, past_due, canceled, paused, expired
  start_at timestamptz not null default now(),
  current_period_start timestamptz not null default now(),
  current_period_end timestamptz,
  cancel_at_period_end boolean not null default false,
  canceled_at timestamptz,
  trial_end timestamptz,
  provider text,         -- e.g. 'stripe'
  provider_ref text,     -- external subscription id
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- allow only one non-canceled active subscription per user
create index if not exists idx_subscriptions_user_active
  on public.subscriptions(user_id)
  where status in ('trialing','active','past_due','paused');

-- usage counters (for quota enforcement)
create table if not exists public.usage_counters (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.users(id) on delete cascade,
  metric text not null,              -- e.g., 'flight_searches'
  time_window text not null,         -- 'daily' | 'monthly'
  period_start date not null,        -- start day of the window
  count int not null default 0,
  updated_at timestamptz not null default now(),
  created_at timestamptz not null default now(),
  unique(user_id, metric, time_window, period_start)
);

-- Seed default plans (idempotent upserts)
insert into public.plans (slug, name, price_cents, currency, billing_interval, features, quotas, is_active, sort_order)
values
  (
    'free', '免费版', 0, 'CNY', 'month',
    jsonb_build_object(
      'ai_model', 'GLM-4.5'
    ),
    jsonb_build_object(
      'daily_flight_searches', 20,
      'max_active_monitor_tasks', 1
    ),
    true, 0
  ),
  (
    'pro', '专业版', 3900, 'CNY', 'month',
    jsonb_build_object(
      'ai_model', 'gemini-2.5-pro'
    ),
    jsonb_build_object(
      'daily_flight_searches', 200,
      'max_active_monitor_tasks', 5
    ),
    true, 10
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
