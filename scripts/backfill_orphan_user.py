#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Backfill a missing auth.users + public.profiles for a given user_id using Service Role Key.

Usage:
  SUPABASE_URL=... SUPABASE_SERVICE_ROLE_KEY=... python scripts/backfill_orphan_user.py 7ecbc245-7eb8-47b1-9a1b-2492df95202b
"""
import os
import sys
import json
from datetime import datetime, timezone
from typing import Optional
import requests
import bcrypt


def iso(dt: Optional[datetime] = None):
    dt = dt or datetime.now(timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()


def headers_json(srk: str):
    return {"Authorization": f"Bearer {srk}", "apikey": srk, "Content-Type": "application/json"}


def get_app_user(base: str, srk: str, user_id: str):
    try:
        url = base.rstrip('/') + f"/rest/v1/users?id=eq.{user_id}&select=id,username,email,created_at,updated_at&limit=1"
        r = requests.get(url, headers=headers_json(srk), timeout=20)
        if r.status_code != 200:
            return None
        arr = r.json()
        return arr[0] if arr else None
    except Exception:
        return None


def create_auth_user(base: str, srk: str, user_id: str, email: str, username: str):
    url = base.rstrip('/') + "/auth/v1/admin/users"
    # random encrypted password to force reset flow
    rand_pw = bcrypt.hashpw(os.urandom(16), bcrypt.gensalt(rounds=10)).decode('utf-8')
    payload = {
        "id": user_id,
        "email": email,
        "encrypted_password": rand_pw,
        "email_confirmed_at": iso(),
        "app_metadata": {"provider": "email", "providers": ["email"]},
        "user_metadata": {"username": username, "is_admin": False}
    }
    r = requests.post(url, headers=headers_json(srk), json=payload, timeout=20)
    if r.status_code not in (200, 201):
        raise RuntimeError(f"auth create failed: {r.status_code} {r.text}")


def get_auth_user(base: str, srk: str, user_id: str) -> bool:
    url = base.rstrip('/') + f"/auth/v1/admin/users/{user_id}"
    r = requests.get(url, headers=headers_json(srk), timeout=20)
    return r.status_code == 200


def upsert_profile(base: str, srk: str, user_id: str, email: str, username: str):
    url = base.rstrip('/') + "/rest/v1/profiles"
    payload = [{
        "id": user_id,
        "email": email,
        "username": username,
        "is_admin": False,
        "created_at": iso(),
        "updated_at": iso()
    }]
    # Prefer upsert: need to set Prefer header
    h = headers_json(srk).copy()
    h["Prefer"] = "resolution=merge-duplicates"
    r = requests.post(url, headers=h, json=payload, timeout=20)
    if r.status_code not in (200, 201):
        raise RuntimeError(f"profiles upsert failed: {r.status_code} {r.text}")


def main():
    if len(sys.argv) < 2:
        print("Usage: backfill_orphan_user.py <user_id>")
        sys.exit(1)
    user_id = sys.argv[1]
    base = os.getenv('SUPABASE_URL')
    srk = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
    if not base or not srk:
        print('Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY')
        sys.exit(1)

    # 1) derive email/username from app users table if present; else fallback
    app_user = get_app_user(base, srk, user_id)
    email = app_user.get('email') if app_user else f"{user_id[:8]}@example.com"
    username = app_user.get('username') if app_user else user_id[:8]

    # 2) ensure auth.users exists
    if not get_auth_user(base, srk, user_id):
        create_auth_user(base, srk, user_id, email, username)
        print(f"auth.users created: {user_id}")
    else:
        print(f"auth.users already exists: {user_id}")

    # 3) upsert profiles
    upsert_profile(base, srk, user_id, email, username)
    print(f"profiles upserted: {user_id}")


if __name__ == '__main__':
    main()
