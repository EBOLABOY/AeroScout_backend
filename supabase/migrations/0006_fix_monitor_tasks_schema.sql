-- Align monitor_tasks table schema to application expectations
-- Non-destructive: only adds missing columns with safe defaults

alter table if exists public.monitor_tasks
  add column if not exists task_name text,
  add column if not exists departure_code text,
  add column if not exists destination_code text,
  add column if not exists depart_date date,
  add column if not exists return_date date,
  add column if not exists seat_class text default 'economy',
  add column if not exists trip_type text default 'round_trip',
  add column if not exists max_stops int default 2,
  add column if not exists is_active boolean default true,
  add column if not exists price_threshold numeric,
  add column if not exists check_interval int default 30,
  add column if not exists notification_enabled boolean default true,
  add column if not exists email_notification boolean default false,
  add column if not exists pushplus_notification boolean default true,
  add column if not exists pushplus_token text,
  add column if not exists blacklist_cities text,
  add column if not exists blacklist_countries text,
  add column if not exists last_check timestamptz,
  add column if not exists last_notification timestamptz,
  add column if not exists total_checks int default 0,
  add column if not exists total_notifications int default 0,
  add column if not exists created_at timestamptz default now(),
  add column if not exists updated_at timestamptz default now();

