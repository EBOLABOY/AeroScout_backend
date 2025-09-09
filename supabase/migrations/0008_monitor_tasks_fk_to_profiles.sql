-- Switch monitor_tasks.user_id foreign key to reference profiles(id)
do $$
declare cname text;
begin
  select conname into cname
  from pg_constraint
  where conrelid='public.monitor_tasks'::regclass and confrelid='public.users'::regclass;
  if cname is not null then
    execute format('alter table public.monitor_tasks drop constraint %I', cname);
  end if;
  -- add fk to profiles
  if not exists (
    select 1 from pg_constraint where conrelid='public.monitor_tasks'::regclass and contype='f'
  ) then
    alter table public.monitor_tasks add constraint monitor_tasks_user_id_fkey foreign key (user_id) references public.profiles(id) on delete cascade;
  end if;
end $$;

