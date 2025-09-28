#!/usr/bin/env python3
"""
JWT 校验实用工具（Authlib + JWKS + HS256 兼容）

最佳实践：
- 优先使用 JWKS（RS256 等非对称算法，支持密钥轮换）
- 回退 HS256（共享密钥环境）
- 可选校验 iss/aud，默认关闭 aud 校验以提升兼容性

若未安装 authlib，则自动降级为 PyJWT 方案（依然支持 JWKS）。

文件编码：UTF-8
"""

from __future__ import annotations

import json
import time
from typing import Any

import httpx
from loguru import logger

from fastapi_app.config import settings

try:  # 可选依赖：authlib
    from authlib.jose import JoseError, JsonWebKey, JsonWebToken  # type: ignore
    HAS_AUTHLIB = True
except Exception:  # 未安装 authlib 时使用 PyJWT 回退
    HAS_AUTHLIB = False
    JoseError = Exception  # type: ignore
    JsonWebKey = None  # type: ignore
    JsonWebToken = None  # type: ignore
    import jwt as pyjwt  # type: ignore


_jwt = JsonWebToken(["RS256", "HS256"]) if HAS_AUTHLIB else None  # 支持常用算法（authlib）
_jwks_keyset = None
_jwks_cached_at = 0.0


def _jwks_ttl_seconds() -> int:
    try:
        return int(getattr(settings, "SUPABASE_JWKS_TTL_SECONDS", 900) or 900)
    except Exception:
        return 900


async def _get_jwks_keyset():
    """获取并缓存 JWKS 公钥集。失败返回 None。"""
    global _jwks_keyset, _jwks_cached_at
    jwks_url: str | None = getattr(settings, "SUPABASE_JWKS_URL", None)
    if not jwks_url:
        return None

    now = time.time()
    if _jwks_keyset is not None and (now - _jwks_cached_at) < _jwks_ttl_seconds():
        return _jwks_keyset

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(jwks_url)
            resp.raise_for_status()
            jwks_data = resp.json()
        if not HAS_AUTHLIB:
            # 保留原始 JWKS JSON，供 PyJWT 回退使用
            _jwks_keyset = jwks_data
            _jwks_cached_at = now
            logger.debug("JWKS 公钥集已刷新并缓存（PyJWT 回退）")
            return jwks_data
        keyset = JsonWebKey.import_key_set(jwks_data)
        _jwks_keyset = keyset
        _jwks_cached_at = now
        logger.debug("JWKS 公钥集已刷新并缓存")
        return keyset
    except Exception as e:
        logger.warning(f"获取 JWKS 失败: {e}")
        return None


def _validate_claims(claims) -> None:
    """根据配置校验 iss/aud/exp 等。若配置未启用相应校验则跳过。"""
    verify_iss: bool = bool(getattr(settings, "JWT_VERIFY_ISSUER", False))
    verify_aud: bool = bool(getattr(settings, "JWT_VERIFY_AUDIENCE", False))
    issuer: str | None = getattr(settings, "SUPABASE_JWT_ISSUER", None)
    audience: str | None = getattr(settings, "SUPABASE_JWT_AUDIENCE", None)

    # 默认校验 exp/nbf/iat 由 authlib 内部完成；iss/aud 按需开启
    kwargs: dict[str, Any] = {}
    if verify_iss and issuer:
        kwargs["iss"] = issuer
    if verify_aud and audience:
        kwargs["aud"] = audience

    if HAS_AUTHLIB:
        claims.validate(**kwargs)


async def verify_jwt_and_get_claims(token: str) -> dict[str, Any] | None:
    """验证 JWT 并返回 claims 字典。

    按顺序尝试：
    1) RS256 + JWKS（若配置了 SUPABASE_JWKS_URL）
    2) HS256 + 共享密钥（若配置了 SUPABASE_JWT_SECRET）
    任一成功即返回 claims；全部失败返回 None。
    """
    # 如果两种方式都未配置，直接返回 None（并提示一次）
    if not getattr(settings, "SUPABASE_JWKS_URL", None) and not getattr(settings, "SUPABASE_JWT_SECRET", None):
        logger.warning("未配置 JWKS 或 HS256 密钥，无法验证 JWT")
        return None

    # 1) RS256 + JWKS
    try:
        keyset = await _get_jwks_keyset()
        if keyset is not None:
            if HAS_AUTHLIB:
                claims = _jwt.decode(token, keyset)  # type: ignore[arg-type]
                _validate_claims(claims)
                return dict(claims)
            else:
                # PyJWT 回退：根据 kid 选择 JWK 并验证
                header = pyjwt.get_unverified_header(token)  # type: ignore[attr-defined]
                kid = header.get("kid")
                keys = (keyset or {}).get("keys", [])  # type: ignore[assignment]
                jwk = None
                if kid:
                    for k in keys:
                        if k.get("kid") == kid:
                            jwk = k
                            break
                if jwk is None and keys:
                    jwk = keys[0]
                if jwk is None:
                    raise ValueError("未在 JWKS 中找到匹配的公钥")
                public_key = pyjwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(jwk))  # type: ignore[attr-defined]

                verify_iss = bool(getattr(settings, "JWT_VERIFY_ISSUER", False))
                verify_aud = bool(getattr(settings, "JWT_VERIFY_AUDIENCE", False))
                issuer = getattr(settings, "SUPABASE_JWT_ISSUER", None)
                audience = getattr(settings, "SUPABASE_JWT_AUDIENCE", None)

                options = {"verify_aud": verify_aud}
                claims = pyjwt.decode(  # type: ignore[attr-defined]
                    token,
                    key=public_key,
                    algorithms=["RS256"],
                    options=options,
                    issuer=issuer if verify_iss and issuer else None,
                    audience=audience if verify_aud and audience else None,
                )
                return dict(claims)
    except Exception as e:
        logger.debug(f"RS256/JWKS 校验失败: {e}")

    # 2) HS256 + 共享密钥
    secret: str | None = getattr(settings, "SUPABASE_JWT_SECRET", None)
    if secret:
        try:
            if HAS_AUTHLIB:
                key = JsonWebKey.import_key(secret, {"kty": "oct"})  # type: ignore[union-attr]
                claims = _jwt.decode(token, key)
                _validate_claims(claims)
                return dict(claims)
            else:
                verify_iss = bool(getattr(settings, "JWT_VERIFY_ISSUER", False))
                verify_aud = bool(getattr(settings, "JWT_VERIFY_AUDIENCE", False))
                issuer = getattr(settings, "SUPABASE_JWT_ISSUER", None)
                audience = getattr(settings, "SUPABASE_JWT_AUDIENCE", None)
                options = {"verify_aud": verify_aud}
                claims = pyjwt.decode(  # type: ignore[attr-defined]
                    token,
                    key=secret,
                    algorithms=["HS256"],
                    options=options,
                    issuer=issuer if verify_iss and issuer else None,
                    audience=audience if verify_aud and audience else None,
                )
                return dict(claims)
        except Exception as e:
            logger.debug(f"HS256 校验失败: {e}")

    return None
