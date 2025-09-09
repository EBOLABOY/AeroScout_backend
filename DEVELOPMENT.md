# Development Workflow

- Python: 3.12
- Dependency manager: Poetry
- Lint/format: Ruff

## Setup

1) Install Poetry

- pipx: `pipx install poetry`
- or pip: `pip install poetry`

2) Install dependencies

- `poetry install`

3) Activate virtualenv

- `poetry shell` (or run commands via `poetry run ...`)

4) Environment variables

- Copy `.env.example` to `.env` and fill values.

## Lint and format

- Check: `poetry run ruff check .`
- Fix: `poetry run ruff check . --fix`
- Format: `poetry run ruff format .`

## Run app (dev)

- `poetry run uvicorn main_fastapi:app --host 0.0.0.0 --port 38181 --reload`

## Docker (build & run)

- Build: `docker build -t ticketradar:dev .`
- Run: `docker run --env-file .env -p 8000:8000 ticketradar:dev`

## Deterministic Docker builds (Poetry -> pip)

To build using the exact versions from `poetry.lock`, export a pinned requirements file and let Docker use it automatically:

- Export: `poetry export -f requirements.txt -o requirements.lock.txt --without-hashes`
- Or: `./scripts/export-lock.sh` (Linux/macOS) or `./scripts/export-lock.ps1` (Windows)

Dockerfile prefers `requirements.lock.txt` when present; otherwise it falls back to `requirements.txt`.

## Database migrations (Supabase CLI)

We version-control schema changes via Supabase migrations. In CI/CD, migrations are applied non-interactively using a DB URL.

1) Install CLI: `npx supabase --version` (or `npm install -g supabase`)
2) Baseline: `npx supabase db diff -f 0000_initial_schema`
3) New changes: `npx supabase db diff -f <feature_name>`

Apply locally (non-interactive) using a connection string:

- Set `SUPABASE_DB_URL` in your environment
- Run: `npx supabase db push --db-url "$SUPABASE_DB_URL"`

Commit the `supabase/` directory and all migration SQL files.
