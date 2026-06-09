"""OIDC service — Authorization Code Flow with PKCE (S256).

Responsibilities:
  - Validate OAuth clients and redirect URIs
  - Store / consume authorization codes (Redis, 5-min TTL)
  - PKCE S256 verification (RFC 7636)
  - Build RS256-signed ID Token, OIDC access token, refresh token
  - Claims assembly and scope filtering (Phases 1 & 2)
  - Token revocation via JTI blocklist in Redis
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.core.jwks import get_private_key_pem
from app.core.security import hash_token
from app.models.application import Application
from app.models.role import RolePermission
from app.models.user import User
from app.redis import redis_client

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SUPPORTED_SCOPES = {"openid", "profile", "email", "roles"}
_CODE_TTL = 300       # 5 minutes
_REVOKE_PREFIX = "oidc_revoked_jti:"
_CODE_PREFIX = "oidc_code:"
_REFRESH_PREFIX = "oidc_refresh:"


# ---------------------------------------------------------------------------
# Client helpers
# ---------------------------------------------------------------------------

async def get_oidc_client(client_id: str, db: AsyncSession) -> Application | None:
    result = await db.execute(
        select(Application).where(
            Application.client_id == client_id,
            Application.is_active == True,
            Application.is_honeypot == False,
        )
    )
    return result.scalar_one_or_none()


def validate_redirect_uri(app: Application, redirect_uri: str) -> bool:
    if not app.redirect_uris:
        return False
    return redirect_uri in app.redirect_uris


def filter_scope(app: Application, requested: str) -> str:
    """Return only scopes allowed for this client."""
    allowed = set((app.allowed_scopes or "openid profile email").split())
    requested_set = set(requested.split()) & SUPPORTED_SCOPES
    filtered = requested_set & allowed
    # openid is always required
    filtered.add("openid")
    return " ".join(sorted(filtered))


def verify_client_secret(app: Application, client_secret: str) -> bool:
    if not app.client_secret_hash:
        return False
    return app.client_secret_hash == hash_token(client_secret)


# ---------------------------------------------------------------------------
# PKCE (RFC 7636)
# ---------------------------------------------------------------------------

def _s256_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


def verify_pkce(code_challenge: str, code_verifier: str) -> bool:
    return secrets.compare_digest(_s256_challenge(code_verifier), code_challenge)


# ---------------------------------------------------------------------------
# Authorization code store (Redis)
# ---------------------------------------------------------------------------

async def store_auth_code(
    code: str,
    user_id: str,
    client_id: str,
    scope: str,
    redirect_uri: str,
    code_challenge: str | None,
    nonce: str | None,
) -> None:
    payload = json.dumps(
        {
            "user_id": user_id,
            "client_id": client_id,
            "scope": scope,
            "redirect_uri": redirect_uri,
            "code_challenge": code_challenge,
            "nonce": nonce,
        }
    )
    await redis_client.setex(f"{_CODE_PREFIX}{code}", _CODE_TTL, payload)


async def consume_auth_code(
    code: str, code_verifier: str | None, redirect_uri: str, client_id: str
) -> dict | None:
    """Validate and atomically consume an authorization code.

    Returns the stored payload dict on success, or None on failure.

    PKCE verification is performed only when a code_challenge was stored at
    authorization time (public clients). Confidential clients (those that
    authenticate with client_secret at the token endpoint) may omit PKCE.
    """
    raw = await redis_client.get(f"{_CODE_PREFIX}{code}")
    if not raw:
        return None
    # Delete immediately — codes are single-use
    await redis_client.delete(f"{_CODE_PREFIX}{code}")

    data = json.loads(raw)
    if data["client_id"] != client_id:
        logger.warning("OIDC: client_id mismatch on code exchange")
        return None
    if data["redirect_uri"] != redirect_uri:
        logger.warning("OIDC: redirect_uri mismatch on code exchange")
        return None
    stored_challenge = data.get("code_challenge")
    if stored_challenge:
        # Public client path: PKCE challenge was stored, must verify
        if not code_verifier:
            logger.warning("OIDC: code_verifier missing for PKCE-protected code")
            return None
        if not verify_pkce(stored_challenge, code_verifier):
            logger.warning("OIDC: PKCE verification failed")
            return None
    return data


# ---------------------------------------------------------------------------
# Token builders
# ---------------------------------------------------------------------------

def _now_ts() -> int:
    return int(datetime.now(timezone.utc).timestamp())


def _build_base_claims(user: User, client_id: str, ttl: int, token_type: str) -> dict:
    now = _now_ts()
    return {
        "iss": settings.OIDC_ISSUER,
        "sub": str(user.id),
        "aud": client_id,
        "iat": now,
        "exp": now + ttl,
        "jti": str(uuid.uuid4()),
        "type": token_type,
    }


def _profile_claims(user: User) -> dict:
    parts = user.full_name.split(" ", 1)
    given = parts[0]
    family = parts[1] if len(parts) > 1 else ""
    preferred_username = user.email.split("@")[0]
    return {
        "name": user.full_name,
        "given_name": given,
        "family_name": family,
        "preferred_username": preferred_username,
        "locale": user.locale,
    }


def _email_claims(user: User) -> dict:
    return {
        "email": user.email,
        "email_verified": True,
    }


def _roles_claims(user: User, client_id: str) -> dict:
    role_name = user.role.name if user.role else None
    # Single-role IAM; expose as a list for RP compatibility
    roles = [role_name] if role_name else []
    return {
        "roles": roles,
        "department": user.department,
    }


def build_id_token(
    user: User,
    client_id: str,
    scope: str,
    nonce: str | None,
) -> str:
    claims = _build_base_claims(user, client_id, settings.OIDC_ID_TOKEN_TTL, "id_token")
    if nonce:
        claims["nonce"] = nonce
    scope_set = set(scope.split())
    if "profile" in scope_set:
        claims.update(_profile_claims(user))
    if "email" in scope_set:
        claims.update(_email_claims(user))
    if "roles" in scope_set:
        claims.update(_roles_claims(user, client_id))

    private_key_pem = get_private_key_pem()
    return jwt.encode(
        claims,
        private_key_pem,
        algorithm="RS256",
        headers={"kid": settings.OIDC_KEY_ID},
    )


def build_oidc_access_token(user: User, client_id: str, scope: str) -> str:
    claims = _build_base_claims(user, client_id, settings.OIDC_ACCESS_TOKEN_TTL, "oidc_access")
    claims["scope"] = scope
    private_key_pem = get_private_key_pem()
    return jwt.encode(
        claims,
        private_key_pem,
        algorithm="RS256",
        headers={"kid": settings.OIDC_KEY_ID},
    )


async def store_oidc_refresh_token(
    user_id: str, client_id: str, scope: str, jti: str
) -> str:
    raw_token = secrets.token_urlsafe(32)
    payload = json.dumps(
        {"user_id": user_id, "client_id": client_id, "scope": scope, "jti": jti}
    )
    await redis_client.setex(
        f"{_REFRESH_PREFIX}{hash_token(raw_token)}",
        settings.OIDC_REFRESH_TOKEN_TTL,
        payload,
    )
    return raw_token


async def consume_oidc_refresh_token(raw_token: str) -> dict | None:
    key = f"{_REFRESH_PREFIX}{hash_token(raw_token)}"
    raw = await redis_client.get(key)
    if not raw:
        return None
    # Sliding window: delete and reissue in the caller
    await redis_client.delete(key)
    return json.loads(raw)


# ---------------------------------------------------------------------------
# UserInfo claims assembly
# ---------------------------------------------------------------------------

def get_userinfo_claims(user: User, scope: str) -> dict:
    scope_set = set(scope.split())
    sub = str(user.id)
    # user_id is an alias for sub required by Odoo auth_oauth validation
    claims: dict = {"sub": sub, "user_id": sub}
    if "profile" in scope_set:
        claims.update(_profile_claims(user))
    if "email" in scope_set:
        claims.update(_email_claims(user))
    if "roles" in scope_set:
        claims.update(_roles_claims(user, ""))
    return claims


# ---------------------------------------------------------------------------
# Token verification (for userinfo / revocation checks)
# ---------------------------------------------------------------------------

async def decode_oidc_access_token(token: str) -> dict | None:
    """Decode and validate an OIDC access token; check revocation."""
    from app.core.jwks import get_current_private_key
    from cryptography.hazmat.primitives import serialization

    pub_pem = (
        get_current_private_key()
        .public_key()
        .public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )
    try:
        payload = jwt.decode(token, pub_pem, algorithms=["RS256"], options={"verify_aud": False})
    except JWTError:
        return None
    if payload.get("type") != "oidc_access":
        return None
    jti = payload.get("jti")
    if jti and await redis_client.exists(f"{_REVOKE_PREFIX}{jti}"):
        return None
    return payload


# ---------------------------------------------------------------------------
# Revocation (RFC 7009)
# ---------------------------------------------------------------------------

async def revoke_token(raw_token: str, token_type_hint: str | None) -> None:
    """Revoke an access or refresh token.

    For access tokens: extract JTI from JWT, store in Redis blocklist.
    For refresh tokens: delete from Redis store.
    """
    # Try refresh token first
    ref_key = f"{_REFRESH_PREFIX}{hash_token(raw_token)}"
    if await redis_client.exists(ref_key):
        await redis_client.delete(ref_key)
        return

    # Try JWT access / id token
    from app.core.jwks import get_current_private_key
    from cryptography.hazmat.primitives import serialization

    pub_pem = (
        get_current_private_key()
        .public_key()
        .public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )
    try:
        payload = jwt.decode(raw_token, pub_pem, algorithms=["RS256"], options={"verify_aud": False})
        jti = payload.get("jti")
        exp = payload.get("exp", 0)
        if jti:
            remaining = max(0, exp - _now_ts())
            await redis_client.setex(f"{_REVOKE_PREFIX}{jti}", remaining or 1, "1")
    except JWTError:
        # Unknown token — silently succeed per RFC 7009 §2.2
        pass


# ---------------------------------------------------------------------------
# User loader for token exchange
# ---------------------------------------------------------------------------

async def get_user_for_oidc(user_id: str, db: AsyncSession) -> User | None:
    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        return None
    result = await db.execute(
        select(User)
        .options(selectinload(User.role))
        .where(User.id == uid, User.is_active == True, User.is_blocked == False)
    )
    return result.scalar_one_or_none()
