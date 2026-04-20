"""RSA key management and JWKS builder for the OIDC IdP.

Loads RSA private keys from env vars (PEM format).  In development, when
OIDC_PRIVATE_KEY is empty, an ephemeral RSA-2048 key is generated in memory.
Two keys are always published in the JWKS endpoint to support key rotation:
  - current key  (OIDC_KEY_ID)
  - previous key (OIDC_PREVIOUS_KEY_ID) — optional, omitted when blank
"""

from __future__ import annotations

import base64
import logging
from functools import lru_cache

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.asymmetric.rsa import (
    RSAPrivateKey,
    RSAPublicKey,
)

from app.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _b64url(n: int) -> str:
    """Encode a big-endian integer as base64url (no padding)."""
    byte_length = (n.bit_length() + 7) // 8
    return base64.urlsafe_b64encode(n.to_bytes(byte_length, "big")).rstrip(b"=").decode()


def _load_or_generate(pem: str, label: str) -> RSAPrivateKey:
    if pem.strip():
        raw = pem.strip().encode()
        key: RSAPrivateKey = serialization.load_pem_private_key(raw, password=None)  # type: ignore[assignment]
        logger.info("OIDC: loaded %s from environment", label)
        return key
    if settings.DEBUG:
        logger.warning("OIDC: %s not set — generating ephemeral key (DEV ONLY)", label)
        return rsa.generate_private_key(public_exponent=65537, key_size=2048)
    raise RuntimeError(f"OIDC_{label.upper().replace(' ', '_')} must be set in production")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def get_current_private_key() -> RSAPrivateKey:
    return _load_or_generate(settings.OIDC_PRIVATE_KEY, "private key")


@lru_cache(maxsize=1)
def get_previous_private_key() -> RSAPrivateKey | None:
    if not settings.OIDC_PREVIOUS_KEY.strip():
        return None
    return _load_or_generate(settings.OIDC_PREVIOUS_KEY, "previous key")


def _jwk_from_private(private_key: RSAPrivateKey, kid: str) -> dict:
    pub: RSAPublicKey = private_key.public_key()
    nums = pub.public_numbers()
    return {
        "kty": "RSA",
        "use": "sig",
        "alg": "RS256",
        "kid": kid,
        "n": _b64url(nums.n),
        "e": _b64url(nums.e),
    }


def get_jwks() -> dict:
    """Return JWKS payload with current (+ optional previous) public keys."""
    keys = [_jwk_from_private(get_current_private_key(), settings.OIDC_KEY_ID)]
    prev = get_previous_private_key()
    if prev is not None:
        keys.append(_jwk_from_private(prev, settings.OIDC_PREVIOUS_KEY_ID))
    return {"keys": keys}


def get_private_key_pem() -> bytes:
    """Return DER/PEM bytes of the current private key for python-jose signing."""
    return get_current_private_key().private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    )
