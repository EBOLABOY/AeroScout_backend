-- Create trigger to automatically create a profile when a new auth user is added
-- This completes the user lifecycle automation to prevent future orphan records.

-- 1) Function: create profile on new auth.users insert
create or replace function public.handle_new_auth_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  -- Insert a matching profile; keep existing if already present
  insert into public.profiles (
    id,
    username,
    email,
    is_admin,
    created_at,
    updated_at
  ) values (
    new.id,
    coalesce(new.raw_user_meta_data->>'username', split_part(new.email, '@', 1)),
    new.email,
    coalesce((new.raw_user_meta_data->>'is_admin')::boolean, false),
    coalesce(new.created_at, now()),
    coalesce(new.updated_at, now())
  )
  on conflict (id) do nothing;

  return new;
end;
$$;

comment on function public.handle_new_auth_user() is
  'Trigger function that creates public.profiles row on new auth.users insert';

-- 2) Trigger: on auth.users AFTER INSERT
do $$
begin
  -- Drop existing trigger if present to allow re-creation
  if exists (
    select 1 from pg_trigger t
    join pg_class c on c.oid = t.tgrelid
    join pg_namespace n on n.oid = c.relnamespace
    where t.tgname = 'on_auth_user_created'
      and n.nspname = 'auth'
      and c.relname = 'users'
  ) then
    execute 'drop trigger on_auth_user_created on auth.users';
  end if;

  -- Create trigger binding to our function
  execute 'create trigger on_auth_user_created\n'
       || 'after insert on auth.users\n'
       || 'for each row execute function public.handle_new_auth_user()';
end $$;

