import os
import hashlib

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import hashes, serialization

from app.config import settings


def _get_vault_key() -> bytes:
    raw = settings.VAULT_MASTER_KEY.encode()
    return hashlib.sha256(raw).digest()


_IV_LEN = 12


def encrypt_vault(plaintext: str) -> bytes:
    """Encrypt with AES-256-GCM. Returns iv||ciphertext so each value carries its own IV."""
    key = _get_vault_key()
    iv = os.urandom(_IV_LEN)
    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(iv, plaintext.encode(), None)
    return iv + ciphertext


def decrypt_vault(blob: bytes) -> str:
    """Decrypt an iv||ciphertext blob produced by encrypt_vault."""
    if len(blob) < _IV_LEN + 1:
        raise ValueError("Vault blob too short")
    key = _get_vault_key()
    iv, ciphertext = blob[:_IV_LEN], blob[_IV_LEN:]
    aesgcm = AESGCM(key)
    plaintext = aesgcm.decrypt(iv, ciphertext, None)
    return plaintext.decode()


def generate_rsa_keypair() -> tuple[bytes, bytes]:
    """Generate RSA-4096 keypair. Returns (private_pem, public_pem)."""
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=4096)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return private_pem, public_pem


def sign_data(data: bytes, private_pem: bytes) -> bytes:
    """Sign data with RSA-4096 private key."""
    private_key = serialization.load_pem_private_key(private_pem, password=None)
    return private_key.sign(
        data,
        padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH),
        hashes.SHA256(),
    )


def verify_signature(data: bytes, signature: bytes, public_pem: bytes) -> bool:
    """Verify RSA signature."""
    public_key = serialization.load_pem_public_key(public_pem)
    try:
        public_key.verify(
            signature,
            data,
            padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH),
            hashes.SHA256(),
        )
        return True
    except Exception:
        return False
