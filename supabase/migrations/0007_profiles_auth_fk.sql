-- Ensure profiles.id is UUID and references auth.users(id)
do $$
begin
  -- convert id to uuid if not already
  begin
    alter table public.profiles alter column id type uuid using id::uuid;
  exception when others then
    null;
  end;

  -- add primary key if missing
  if not exists (
    select 1 from pg_constraint where conrelid='public.profiles'::regclass and contype='p'
  ) then
    alter table public.profiles add primary key (id);
  end if;

  -- add foreign key to auth.users if missing
  if not exists (
    select 1 from pg_constraint where conname='profiles_id_fkey'
  ) then
    alter table public.profiles add constraint profiles_id_fkey foreign key (id) references auth.users(id) on delete cascade;
  end if;
end $$;

-- Optionally drop password_hash column if exists (managed by Supabase Auth)
alter table if exists public.profiles drop column if exists password_hash;

