-- Drop legacy tables (destructive). Run only after verification and observation period.
-- Strongly recommended to take a full backup before running this migration.

-- Note: CASCADE is used to drop dependent objects (FKs, indexes) if any remain.
-- If you prefer a stricter approach, remove CASCADE and drop in dependency order.

drop table if exists public.legacy_user_level_permissions cascade;
drop table if exists public.legacy_user_level_limits cascade;
drop table if exists public.legacy_user_subscriptions cascade;
drop table if exists public.legacy_user_levels cascade;
drop table if exists public.legacy_permissions cascade;
drop table if exists public.legacy_user_usage_stats cascade;
drop table if exists public.legacy_api_usage_logs cascade;
drop table if exists public.legacy_ip_rate_limits cascade;
drop table if exists public.legacy_search_logs cascade;
drop table if exists public.legacy_users_full_backup cascade;

-- Optional: profiles archive (skip by default)
-- drop table if exists public.legacy_profiles cascade;

