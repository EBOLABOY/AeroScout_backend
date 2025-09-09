#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Export existing app users (profiles/users) to a Supabase Auth import file.

Outputs:
  - scripts/output/auth_import.json  (Gotrue users array)
  - scripts/output/auth_import.csv   (best-effort CSV)

Usage:
  python scripts/export_auth_users.py

Requirements:
  - env SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
  - pip install supabase python-dotenv bcrypt
"""
import os
import json
import csv
import uuid
from pathlib import Path
from datetime import datetime, timezone
from dotenv import load_dotenv
import bcrypt
from supabase import create_client


def iso(dt):
    if not dt:
        return None
    if isinstance(dt, str):
        return dt
    return dt.astimezone(timezone.utc).isoformat()


def main():
    repo_root = Path(__file__).resolve().parents[1]
    load_dotenv(repo_root / '.env')

    url = os.getenv('SUPABASE_URL')
    key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
    if not url or not key:
        raise SystemExit('Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY in environment')

    out_dir = repo_root / 'scripts' / 'output'
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / 'auth_import.json'
    csv_path = out_dir / 'auth_import.csv'

    client = create_client(url, key)

    # Fetch profiles first (preferred)
    profiles = client.table('profiles').select('*').execute().data or []

    # Build a map for legacy users (for missing email fallback)
    try:
        legacy_users = client.table('users').select('id,email,username,created_at,updated_at').execute().data or []
        legacy_by_id = {row['id']: row for row in legacy_users if row.get('id')}
    except Exception:
        legacy_by_id = {}

    users = []
    for p in profiles:
        uid = str(p.get('id') or '')
        if not uid:
            # generate a UUID for consistency (rare)
            uid = str(uuid.uuid4())
        email = p.get('email')
        if not email:
            legacy = legacy_by_id.get(uid)
            if legacy:
                email = legacy.get('email')
        if not email:
            # Skip profiles without email; cannot import into auth.users without email
            continue

        username = p.get('username') or (legacy_by_id.get(uid) or {}).get('username') or email.split('@')[0]
        created_at = p.get('created_at') or (legacy_by_id.get(uid) or {}).get('created_at')
        updated_at = p.get('updated_at') or (legacy_by_id.get(uid) or {}).get('updated_at') or created_at
        email_verified = bool(p.get('email_verified', False))

        # Generate a random bcrypt hash to force password reset
        random_pw = uuid.uuid4().hex
        encrypted_password = bcrypt.hashpw(random_pw.encode('utf-8'), bcrypt.gensalt(rounds=10)).decode('utf-8')

        user_obj = {
            'id': uid,
            'aud': 'authenticated',
            'role': 'authenticated',
            'email': email,
            'encrypted_password': encrypted_password,
            'email_confirmed_at': iso(datetime.now(timezone.utc)) if email_verified else None,
            'invited_at': None,
            'phone': None,
            'confirmed_at': None,
            'last_sign_in_at': None,
            'app_metadata': {
                'provider': 'email',
                'providers': ['email']
            },
            'user_metadata': {
                'username': username,
                'is_admin': bool(p.get('is_admin', False))
            },
            'created_at': created_at or iso(datetime.now(timezone.utc)),
            'updated_at': updated_at or iso(datetime.now(timezone.utc)),
            'identities': []
        }
        users.append(user_obj)

    payload = {'users': users}
    with json_path.open('w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    # CSV (best-effort subset)
    csv_fields = ['id', 'email', 'encrypted_password', 'email_confirmed_at', 'created_at', 'updated_at', 'user_metadata', 'app_metadata']
    with csv_path.open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=csv_fields)
        writer.writeheader()
        for u in users:
            writer.writerow({
                'id': u['id'],
                'email': u['email'],
                'encrypted_password': u['encrypted_password'],
                'email_confirmed_at': u['email_confirmed_at'] or '',
                'created_at': u['created_at'] or '',
                'updated_at': u['updated_at'] or '',
                'user_metadata': json.dumps(u['user_metadata'], ensure_ascii=False),
                'app_metadata': json.dumps(u['app_metadata'], ensure_ascii=False),
            })

    print(f"✅ Exported {len(users)} users")
    print(f" - JSON: {json_path}")
    print(f" - CSV : {csv_path}")


if __name__ == '__main__':
    main()

