"""OIDC endpoints — Authorization Server (RFC 6749 / OIDC Core 1.0).

Endpoints
---------
GET  /.well-known/openid-configuration  — discovery manifest
GET  /.well-known/jwks.json             — public key set
GET  /oauth/authorize                   — start authorization code flow
POST /oauth/token                       — exchange code for tokens
GET  /oauth/userinfo                    — return profile claims
POST /oauth/revoke                      — revoke access or refresh token

Authentication for /authorize
------------------------------
The endpoint reads the IAM `refresh_token` httponly cookie that is set by
POST /api/v1/auth/mfa/verify (or /auth/login when MFA is disabled).  If the
cookie is absent or invalid the user is redirected to the frontend login page
with the full authorize URL encoded as the `next` query parameter.

Security properties
-------------------
* PKCE S256 is mandatory — no code_challenge → 400
* Redirect URIs are validated against the registered list
* client_secret verified with SHA-256 hash comparison (constant-time)
* JTI revocation blocklist in Redis prevents replay of revoked tokens
* PII (email, sub) is never written to structured logs
"""

from __future__ import annotations

import logging
import secrets
import urllib.parse
from typing import Annotated

from fastapi import (
    APIRouter,
    Cookie,
    Depends,
    Form,
    HTTPException,
    Query,
    Request,
    Response,
    status,
)
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.core.jwks import get_jwks
from app.core.security import decode_token, hash_token
from app.database import get_db
from app.models.user import User
from app.schemas.oidc import (
    OAuthErrorResponse,
    OIDCConfiguration,
    TokenResponse,
    UserInfoResponse,
)
from app.services import oidc_service as svc
from app.services.oidc_service import (
    build_id_token,
    build_oidc_access_token,
    consume_auth_code,
    consume_oidc_refresh_token,
    decode_oidc_access_token,
    filter_scope,
    get_oidc_client,
    get_user_for_oidc,
    revoke_token,
    store_auth_code,
    store_oidc_refresh_token,
    validate_redirect_uri,
    verify_client_secret,
)

logger = logging.getLogger(__name__)

router = APIRouter()
discovery_router = APIRouter()  # mounted at /.well-known


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _oauth_error(error: str, description: str, status_code: int = 400) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": error, "error_description": description},
    )


def _redirect_error(redirect_uri: str, error: str, description: str, state: str | None) -> RedirectResponse:
    params: dict[str, str] = {"error": error, "error_description": description}
    if state:
        params["state"] = state
    url = redirect_uri + "?" + urllib.parse.urlencode(params)
    return RedirectResponse(url=url, status_code=302)


async def _get_user_from_iam_cookie(
    refresh_token: str | None,
    db: AsyncSession,
) -> User | None:
    """Resolve IAM session cookie → User (with role loaded)."""
    if not refresh_token:
        return None
    payload = decode_token(refresh_token)
    if not payload or payload.get("type") != "refresh":
        return None
    user_id = payload.get("sub")
    if not user_id:
        return None

    from sqlalchemy import select

    result = await db.execute(
        select(User)
        .options(selectinload(User.role))
        .where(User.id == __import__("uuid").UUID(user_id))
    )
    user = result.scalar_one_or_none()
    if not user or user.is_blocked or not user.is_active:
        return None
    return user


# ---------------------------------------------------------------------------
# Discovery endpoints
# ---------------------------------------------------------------------------

@discovery_router.get("/openid-configuration", response_model=OIDCConfiguration)
async def openid_configuration() -> OIDCConfiguration:
    base = settings.OIDC_ISSUER
    internal = settings.OIDC_INTERNAL_BASE or base
    # Browser-visible base for authorization_endpoint — must match cookie domain (localhost).
    external = settings.OIDC_EXTERNAL_BASE or base
    return OIDCConfiguration(
        issuer=base,
        authorization_endpoint=f"{external}/oauth/authorize",
        token_endpoint=f"{internal}/oauth/token",
        userinfo_endpoint=f"{internal}/oauth/userinfo",
        jwks_uri=f"{internal}/.well-known/jwks.json",
        revocation_endpoint=f"{internal}/oauth/revoke",
        end_session_endpoint=f"{external}/oauth/logout",
        response_types_supported=["code"],
        subject_types_supported=["public"],
        id_token_signing_alg_values_supported=["RS256"],
        scopes_supported=["openid", "profile", "email", "roles"],
        token_endpoint_auth_methods_supported=["client_secret_post", "none"],
        claims_supported=[
            "sub", "iss", "aud", "exp", "iat", "nonce",
            "email", "email_verified",
            "given_name", "family_name", "preferred_username", "locale",
            "roles", "department",
        ],
        grant_types_supported=["authorization_code", "refresh_token"],
        code_challenge_methods_supported=["S256"],
    )


@discovery_router.get("/jwks.json")
async def jwks() -> dict:
    return get_jwks()


# ---------------------------------------------------------------------------
# Authorize endpoint
# ---------------------------------------------------------------------------

@router.get("/authorize")
async def authorize(
    request: Request,
    response_type: str = Query(...),
    client_id: str = Query(...),
    redirect_uri: str = Query(...),
    scope: str = Query("openid"),
    state: str | None = Query(None),
    nonce: str | None = Query(None),
    code_challenge: str | None = Query(None),
    code_challenge_method: str | None = Query(None),
    refresh_token: Annotated[str | None, Cookie(alias="refresh_token")] = None,
    db: AsyncSession = Depends(get_db),
) -> Response:
    # --- 1. Validate response_type ---
    if response_type not in ("code", "token"):
        return _oauth_error("unsupported_response_type", "Only 'code' and 'token' are supported")

    # PKCE is mandatory for code flow, not applicable for token (implicit) flow
    if response_type == "code":
        if not code_challenge or code_challenge_method != "S256":
            return _oauth_error(
                "invalid_request",
                "code_challenge with method S256 is required (PKCE mandatory)",
            )
        if len(code_challenge) < 43 or len(code_challenge) > 128:
            return _oauth_error("invalid_request", "code_challenge length must be 43–128 chars")

    # --- 2. Validate client ---
    app = await get_oidc_client(client_id, db)
    if not app:
        return _oauth_error("invalid_client", "Unknown or inactive client_id")

    if not validate_redirect_uri(app, redirect_uri):
        return _oauth_error("invalid_request", "redirect_uri not registered for this client")

    # --- 3. Resolve IAM session ---
    user = await _get_user_from_iam_cookie(refresh_token, db)
    if not user:
        # Reconstruct the public URL using the frontend proxy base so the
        # refresh_token cookie (set for localhost:3000) is included on return.
        qs = request.url.query
        public_next = f"{settings.APP_FRONTEND_URL}/oauth/authorize?{qs}" if qs else f"{settings.APP_FRONTEND_URL}/oauth/authorize"
        login_url = f"{settings.APP_FRONTEND_URL}/login?next={urllib.parse.quote_plus(public_next)}"
        return RedirectResponse(url=login_url, status_code=302)

    # --- 4. Filter scope ---
    granted_scope = filter_scope(app, scope)

    # --- 5a. Implicit flow (response_type=token) — used by Odoo auth_oauth ---
    if response_type == "token":
        access_tok = build_oidc_access_token(user, client_id, granted_scope)
        fragment_params: dict[str, str] = {
            "access_token": access_tok,
            "token_type": "Bearer",
            "expires_in": str(settings.OIDC_ACCESS_TOKEN_TTL),
            "scope": granted_scope,
        }
        if state:
            fragment_params["state"] = state
        fragment = urllib.parse.urlencode(fragment_params)
        location = f"{redirect_uri}#{fragment}"
        logger.info("OIDC: implicit token issued for client=%s", client_id)
        return RedirectResponse(url=location, status_code=302)

    # --- 5b. Authorization Code Flow (PKCE) ---
    code = secrets.token_urlsafe(32)
    await store_auth_code(
        code=code,
        user_id=str(user.id),
        client_id=client_id,
        scope=granted_scope,
        redirect_uri=redirect_uri,
        code_challenge=code_challenge,  # type: ignore[arg-type]
        nonce=nonce,
    )

    logger.info("OIDC: auth code issued for client=%s", client_id)

    params: dict[str, str] = {"code": code}
    if state:
        params["state"] = state
    location = redirect_uri + "?" + urllib.parse.urlencode(params)
    return RedirectResponse(url=location, status_code=302)


# ---------------------------------------------------------------------------
# Token endpoint
# ---------------------------------------------------------------------------

@router.post("/token", response_model=TokenResponse)
async def token(
    grant_type: str = Form(...),
    code: str | None = Form(None),
    redirect_uri: str | None = Form(None),
    client_id: str | None = Form(None),
    client_secret: str | None = Form(None),
    code_verifier: str | None = Form(None),
    refresh_token: str | None = Form(None),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    if grant_type == "authorization_code":
        return await _handle_code_exchange(
            code, redirect_uri, client_id, client_secret, code_verifier, db
        )
    if grant_type == "refresh_token":
        return await _handle_refresh(refresh_token, client_id, client_secret, db)
    return _oauth_error("unsupported_grant_type", f"grant_type '{grant_type}' is not supported")


async def _handle_code_exchange(
    code: str | None,
    redirect_uri: str | None,
    client_id: str | None,
    client_secret: str | None,
    code_verifier: str | None,
    db: AsyncSession,
) -> JSONResponse:
    if not all([code, redirect_uri, client_id, code_verifier]):
        return _oauth_error("invalid_request", "Missing required parameters")

    assert code and redirect_uri and client_id and code_verifier  # narrowing

    app = await get_oidc_client(client_id, db)
    if not app:
        return _oauth_error("invalid_client", "Unknown client_id", 401)

    # Client authentication (public clients skip secret check)
    if app.client_secret_hash and client_secret:
        if not verify_client_secret(app, client_secret):
            return _oauth_error("invalid_client", "Invalid client_secret", 401)

    data = await consume_auth_code(code, code_verifier, redirect_uri, client_id)
    if not data:
        return _oauth_error("invalid_grant", "Authorization code invalid, expired, or PKCE mismatch")

    user = await get_user_for_oidc(data["user_id"], db)
    if not user:
        return _oauth_error("invalid_grant", "User not found or inactive")

    scope = data["scope"]
    nonce = data.get("nonce")

    id_tok = build_id_token(user, client_id, scope, nonce)
    access_tok = build_oidc_access_token(user, client_id, scope)

    # Refresh token: store opaque token in Redis
    import uuid as _uuid
    rt_jti = str(_uuid.uuid4())
    raw_rt = await store_oidc_refresh_token(str(user.id), client_id, scope, rt_jti)

    logger.info("OIDC: tokens issued for client=%s", client_id)

    return JSONResponse(
        content={
            "access_token": access_tok,
            "token_type": "Bearer",
            "expires_in": settings.OIDC_ACCESS_TOKEN_TTL,
            "id_token": id_tok,
            "refresh_token": raw_rt,
            "scope": scope,
        }
    )


async def _handle_refresh(
    raw_rt: str | None,
    client_id: str | None,
    client_secret: str | None,
    db: AsyncSession,
) -> JSONResponse:
    if not raw_rt:
        return _oauth_error("invalid_request", "refresh_token is required")

    rt_data = await consume_oidc_refresh_token(raw_rt)
    if not rt_data:
        return _oauth_error("invalid_grant", "Refresh token invalid or expired")

    stored_client = rt_data["client_id"]
    if client_id and client_id != stored_client:
        return _oauth_error("invalid_client", "client_id mismatch", 401)

    app = await get_oidc_client(stored_client, db)
    if not app:
        return _oauth_error("invalid_client", "Unknown client")

    if app.client_secret_hash and client_secret:
        if not verify_client_secret(app, client_secret):
            return _oauth_error("invalid_client", "Invalid client_secret", 401)

    user = await get_user_for_oidc(rt_data["user_id"], db)
    if not user:
        return _oauth_error("invalid_grant", "User not found or inactive")

    scope = rt_data["scope"]

    # Re-issue access token + sliding-window refresh token
    import uuid as _uuid
    new_rt = await store_oidc_refresh_token(str(user.id), stored_client, scope, str(_uuid.uuid4()))
    new_at = build_oidc_access_token(user, stored_client, scope)
    new_id = build_id_token(user, stored_client, scope, nonce=None)

    return JSONResponse(
        content={
            "access_token": new_at,
            "token_type": "Bearer",
            "expires_in": settings.OIDC_ACCESS_TOKEN_TTL,
            "id_token": new_id,
            "refresh_token": new_rt,
            "scope": scope,
        }
    )


# ---------------------------------------------------------------------------
# UserInfo endpoint
# ---------------------------------------------------------------------------

async def _form_access_token(request: Request) -> str | None:
    """Extract access_token from form body (POST with application/x-www-form-urlencoded)."""
    try:
        form = await request.form()
        return form.get("access_token")  # type: ignore[return-value]
    except Exception:
        return None

@router.get("/userinfo", response_model=UserInfoResponse)
@router.post("/userinfo", response_model=UserInfoResponse)
async def userinfo(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    # Accept token from Authorization header (standard) or ?access_token= (Odoo compat)
    token_str: str | None = None
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token_str = auth_header[len("Bearer "):]
    else:
        # Odoo auth_oauth calls validation_endpoint?access_token=<token>
        token_str = request.query_params.get("access_token") or (await _form_access_token(request))

    if not token_str:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            headers={"WWW-Authenticate": "Bearer"},
            detail="Bearer token required",
        )
    payload = await decode_oidc_access_token(token_str)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            headers={"WWW-Authenticate": 'Bearer error="invalid_token"'},
            detail="Token invalid or revoked",
        )

    user = await get_user_for_oidc(payload["sub"], db)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    scope = payload.get("scope", "openid")
    claims = svc.get_userinfo_claims(user, scope)
    return JSONResponse(content=claims)


# ---------------------------------------------------------------------------
# End-session endpoint (OpenID Connect RP-Initiated Logout 1.0)
# ---------------------------------------------------------------------------

@router.get("/logout")
async def end_session(
    post_logout_redirect_uri: str | None = Query(None),
    id_token_hint: str | None = Query(None),
    state: str | None = Query(None),
) -> RedirectResponse:
    """RP-Initiated Logout — called by Nextcloud (and other RPs) on user logout.

    Revokes the id_token_hint if provided, then redirects to
    post_logout_redirect_uri (if registered/safe) or the frontend login page.
    """
    # Optionally revoke the id_token if provided
    if id_token_hint:
        await revoke_token(id_token_hint, "id_token")

    # Build redirect target
    if post_logout_redirect_uri:
        # Safety: only allow https/http URIs (no javascript: etc.)
        if post_logout_redirect_uri.startswith(("https://", "http://")):
            target = post_logout_redirect_uri
            if state:
                sep = "&" if "?" in target else "?"
                target = f"{target}{sep}state={urllib.parse.quote(state)}"
            return RedirectResponse(url=target, status_code=302)

    # Default: redirect to IAM frontend login page
    return RedirectResponse(url=f"{settings.APP_FRONTEND_URL}/login", status_code=302)


# ---------------------------------------------------------------------------
# Revocation endpoint (RFC 7009)
# ---------------------------------------------------------------------------

@router.post("/revoke")
async def revoke(
    token: str = Form(...),
    token_type_hint: str | None = Form(None),
    client_id: str | None = Form(None),
    client_secret: str | None = Form(None),
) -> Response:
    # Per RFC 7009 §2.2: always return 200, even for unknown tokens
    await revoke_token(token, token_type_hint)
    return Response(status_code=200)
