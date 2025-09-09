-- Rename legacy tables to legacy_* namespace (non-destructive)
-- Purpose: make old tables read-only/hidden from app paths while preserving data
-- Safe to run multiple times (guards check existence and avoid double-rename)

do $$
begin
  -- user_subscriptions -> legacy_user_subscriptions
  if exists (
    select 1 from information_schema.tables where table_schema='public' and table_name='user_subscriptions'
  ) and not exists (
    select 1 from information_schema.tables where table_schema='public' and table_name='legacy_user_subscriptions'
  ) then
    execute 'alter table public.user_subscriptions rename to legacy_user_subscriptions';
  end if;

  -- user_levels -> legacy_user_levels
  if exists (
    select 1 from information_schema.tables where table_schema='public' and table_name='user_levels'
  ) and not exists (
    select 1 from information_schema.tables where table_schema='public' and table_name='legacy_user_levels'
  ) then
    execute 'alter table public.user_levels rename to legacy_user_levels';
  end if;

  -- user_level_limits -> legacy_user_level_limits
  if exists (
    select 1 from information_schema.tables where table_schema='public' and table_name='user_level_limits'
  ) and not exists (
    select 1 from information_schema.tables where table_schema='public' and table_name='legacy_user_level_limits'
  ) then
    execute 'alter table public.user_level_limits rename to legacy_user_level_limits';
  end if;

  -- user_level_permissions -> legacy_user_level_permissions
  if exists (
    select 1 from information_schema.tables where table_schema='public' and table_name='user_level_permissions'
  ) and not exists (
    select 1 from information_schema.tables where table_schema='public' and table_name='legacy_user_level_permissions'
  ) then
    execute 'alter table public.user_level_permissions rename to legacy_user_level_permissions';
  end if;

  -- permissions -> legacy_permissions
  if exists (
    select 1 from information_schema.tables where table_schema='public' and table_name='permissions'
  ) and not exists (
    select 1 from information_schema.tables where table_schema='public' and table_name='legacy_permissions'
  ) then
    execute 'alter table public.permissions rename to legacy_permissions';
  end if;

  -- user_usage_stats -> legacy_user_usage_stats
  if exists (
    select 1 from information_schema.tables where table_schema='public' and table_name='user_usage_stats'
  ) and not exists (
    select 1 from information_schema.tables where table_schema='public' and table_name='legacy_user_usage_stats'
  ) then
    execute 'alter table public.user_usage_stats rename to legacy_user_usage_stats';
  end if;

  -- api_usage_logs -> legacy_api_usage_logs
  if exists (
    select 1 from information_schema.tables where table_schema='public' and table_name='api_usage_logs'
  ) and not exists (
    select 1 from information_schema.tables where table_schema='public' and table_name='legacy_api_usage_logs'
  ) then
    execute 'alter table public.api_usage_logs rename to legacy_api_usage_logs';
  end if;

  -- ip_rate_limits -> legacy_ip_rate_limits
  if exists (
    select 1 from information_schema.tables where table_schema='public' and table_name='ip_rate_limits'
  ) and not exists (
    select 1 from information_schema.tables where table_schema='public' and table_name='legacy_ip_rate_limits'
  ) then
    execute 'alter table public.ip_rate_limits rename to legacy_ip_rate_limits';
  end if;

  -- search_logs -> legacy_search_logs
  if exists (
    select 1 from information_schema.tables where table_schema='public' and table_name='search_logs'
  ) and not exists (
    select 1 from information_schema.tables where table_schema='public' and table_name='legacy_search_logs'
  ) then
    execute 'alter table public.search_logs rename to legacy_search_logs';
  end if;

  -- users_full_backup -> legacy_users_full_backup
  if exists (
    select 1 from information_schema.tables where table_schema='public' and table_name='users_full_backup'
  ) and not exists (
    select 1 from information_schema.tables where table_schema='public' and table_name='legacy_users_full_backup'
  ) then
    execute 'alter table public.users_full_backup rename to legacy_users_full_backup';
  end if;

  -- Optional: profiles -> legacy_profiles (commented out by default, as this may be used by Supabase Auth)
  -- if exists (
  --   select 1 from information_schema.tables where table_schema='public' and table_name='profiles'
  -- ) and not exists (
  --   select 1 from information_schema.tables where table_schema='public' and table_name='legacy_profiles'
  -- ) then
  --   execute 'alter table public.profiles rename to legacy_profiles';
  -- end if;
end
$$;

