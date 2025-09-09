-- Backfill profiles for any auth.users missing in public.profiles
insert into public.profiles (id, username, email, is_admin, created_at, updated_at)
select
  u.id,
  coalesce(u.raw_user_meta_data->>'username', split_part(u.email, '@', 1)) as username,
  u.email,
  coalesce((u.raw_user_meta_data->>'is_admin')::boolean, false) as is_admin,
  coalesce(u.created_at, now()),
  coalesce(u.updated_at, now())
from auth.users u
left join public.profiles p on p.id = u.id
where p.id is null;

