"""Pydantic v2 schemas for OIDC / OAuth 2.0 endpoints."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------

class OIDCConfiguration(BaseModel):
    issuer: str
    authorization_endpoint: str
    token_endpoint: str
    userinfo_endpoint: str
    jwks_uri: str
    revocation_endpoint: str
    end_session_endpoint: str | None = None
    response_types_supported: list[str]
    subject_types_supported: list[str]
    id_token_signing_alg_values_supported: list[str]
    scopes_supported: list[str]
    token_endpoint_auth_methods_supported: list[str]
    claims_supported: list[str]
    grant_types_supported: list[str]
    code_challenge_methods_supported: list[str]


# ---------------------------------------------------------------------------
# Authorization endpoint
# ---------------------------------------------------------------------------

class AuthorizeParams(BaseModel):
    """Query parameters for GET /oauth/authorize."""

    response_type: Literal["code"]
    client_id: str
    redirect_uri: str
    scope: str = "openid"
    state: str | None = None
    nonce: str | None = None
    code_challenge: str = Field(..., min_length=43, max_length=128)
    code_challenge_method: Literal["S256"]

    @field_validator("scope")
    @classmethod
    def scope_must_contain_openid(cls, v: str) -> str:
        if "openid" not in v.split():
            raise ValueError("scope must include 'openid'")
        return v


# ---------------------------------------------------------------------------
# Token endpoint
# ---------------------------------------------------------------------------

class TokenRequest(BaseModel):
    """Form body for POST /oauth/token."""

    grant_type: Literal["authorization_code", "refresh_token"]
    # authorization_code grant
    code: str | None = None
    redirect_uri: str | None = None
    client_id: str | None = None
    client_secret: str | None = None
    code_verifier: str | None = None
    # refresh_token grant
    refresh_token: str | None = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["Bearer"] = "Bearer"
    expires_in: int
    id_token: str | None = None
    refresh_token: str | None = None
    scope: str | None = None


# ---------------------------------------------------------------------------
# UserInfo endpoint
# ---------------------------------------------------------------------------

class UserInfoResponse(BaseModel):
    sub: str
    # profile scope
    given_name: str | None = None
    family_name: str | None = None
    preferred_username: str | None = None
    locale: str | None = None
    # email scope
    email: str | None = None
    email_verified: bool | None = None
    # roles scope
    roles: list[str] | None = None
    department: str | None = None


# ---------------------------------------------------------------------------
# Revocation endpoint
# ---------------------------------------------------------------------------

class RevocationRequest(BaseModel):
    token: str
    token_type_hint: str | None = None
    client_id: str | None = None
    client_secret: str | None = None


# ---------------------------------------------------------------------------
# Error response (RFC 6749 §5.2)
# ---------------------------------------------------------------------------

class OAuthErrorResponse(BaseModel):
    error: str
    error_description: str | None = None
