-- Migrate Supabase profiles -> app users table
-- Requires pgcrypto for bcrypt hashing (enabled in 0001)

-- 1) Insert missing users from profiles
insert into public.users (
  id,
  username,
  email,
  password_hash,
  is_active,
  is_verified,
  email_verified,
  is_admin,
  full_name,
  phone,
  avatar_url,
  notification_enabled,
  email_notifications_enabled,
  pushplus_token,
  created_at
)
select
  p.id,
  coalesce(nullif(p.username, ''), split_part(p.email, '@', 1)) as username,
  p.email,
  -- generate a random bcrypt hash; users should reset password via app flow
  crypt(gen_random_uuid()::text, gen_salt('bf', 8)) as password_hash,
  coalesce(p.is_active, true) as is_active,
  coalesce(p.email_verified, false) as is_verified,
  coalesce(p.email_verified, false) as email_verified,
  coalesce(p.is_admin, false) as is_admin,
  p.full_name,
  p.phone,
  p.avatar_url,
  coalesce(p.notification_enabled, true) as notification_enabled,
  coalesce(p.email_notifications_enabled, false) as email_notifications_enabled,
  p.pushplus_token,
  coalesce(p.created_at, now()) as created_at
from public.profiles p
left join public.users u on u.id = p.id
where u.id is null;

-- 2) Re-run legacy subscriptions migration for any users now present
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

