## Supabase Migrations

This folder holds database migrations managed by Supabase CLI.

## Quick Start

1) Install Supabase CLI

- Using npm (no global install needed):
  - `npx supabase --version`
- Or install globally:
  - `npm install -g supabase`

2) Initialize in this repo (creates config files)

- `npx supabase init`

3) Link to your hosted project

- Find your project ref (e.g. `abcd1234`) from your dashboard URL `<ref>.supabase.co`.
- `npx supabase link --project-ref <your-project-ref>`

4) Create a baseline migration from the live schema

- `npx supabase db diff -f 0000_initial_schema`
- This generates `supabase/migrations/0000_initial_schema.sql`.

5) Workflow for schema changes

- Make changes in Supabase Studio or locally.
- Generate a migration: `npx supabase db diff -f feature_add_users_idx`
- Commit the new migration file.
- In CI/CD deploy, apply migrations before starting the app.

## Notes

- Do not hand-edit generated migrations unless necessary.
- Keep this directory committed to version control.
- Store secrets in your `.env` and never in migration SQL.

