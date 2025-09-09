# Supabase Auth Migration (Users Import)

This guide helps you migrate existing app users into Supabase Auth (auth.users) while preserving IDs for a clean foreign-key with `public.profiles(id)`.

## Prerequisites
- `.env` configured with `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_ACCESS_TOKEN` (for CLI).
- Project linked: `npx -y supabase link --project-ref <ref>`
- Python deps: `pip install supabase python-dotenv bcrypt`

## 1) Prepare database relations (run migrations)
- Ensures `profiles(id)` is UUID + FK to `auth.users(id)`
- Switches `monitor_tasks.user_id` FK to `profiles(id)`

Run:

```
npx -y supabase db push --workdir . -p "<DB_PASSWORD>"
```

This will apply:
- `supabase/migrations/0007_profiles_auth_fk.sql`
- `supabase/migrations/0008_monitor_tasks_fk_to_profiles.sql`

## 2) Export users for import

```
python scripts/export_auth_users.py
```

Outputs:
- `scripts/output/auth_import.json` (recommended)
- `scripts/output/auth_import.csv` (best-effort)

Notes:
- Users without email are skipped (Auth requires email).
- A random bcrypt `encrypted_password` is generated to enforce a reset; set up your “forgot password” flow.
- `user_metadata` includes `username` and `is_admin`.

## 3) Import into Supabase Auth

Recommended (JSON):

```
powershell -ExecutionPolicy Bypass -File scripts/auth_import.ps1 -File scripts/output/auth_import.json
```

Alternative (direct CLI):

```
npx -y supabase auth import --file scripts/output/auth_import.json --workdir .
```

If you prefer CSV, adjust the command accordingly if supported by your CLI version.

## 4) Rollback (if needed)

To delete imported users by ID list from the generated JSON:

```
powershell -ExecutionPolicy Bypass -File scripts/rollback_auth_users.ps1 -File scripts/output/auth_import.json
```

This calls the Admin API `DELETE /auth/v1/admin/users/{id}` using `SUPABASE_SERVICE_ROLE_KEY`.

## 5) Post-import
- Verify `/auth/me` returns correct data via Supabase JWT.
- Ensure your frontend now authenticates with `@supabase/supabase-js` and sends the JWT to backend.
- (Optional) Add a trigger to auto-create `profiles` for new `auth.users` (suggested after migration):
  - Create `0010_add_new_user_trigger.sql` with a `handle_new_user()` function and an `on_auth_user_created` trigger.

Happy shipping!

