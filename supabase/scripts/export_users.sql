-- Export profiles to JSON lines via psql (use with -A -t)
-- Each row prints as a single JSON object suitable for GoTrue import after wrapping
WITH src AS (
  SELECT
    p.id::text            AS id,
    p.email               AS email,
    p.created_at          AS created_at,
    ('{"provider":"email","providers":["email"]}'::jsonb) AS app_metadata,
    jsonb_build_object(
      'username', p.username,
      'is_admin', coalesce(p.is_admin, false)
    )                    AS user_metadata
  FROM public.profiles p
  WHERE p.email IS NOT NULL
)
SELECT row_to_json(src)
FROM src;

