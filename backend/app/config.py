from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql+asyncpg://iam_user:iam_password@db:5432/iam_db"
    DATABASE_URL_SYNC: str = "postgresql://iam_user:iam_password@db:5432/iam_db"

    # Redis
    REDIS_URL: str = "redis://redis:6379/0"

    # JWT
    JWT_SECRET_KEY: str = "change-me-to-a-random-secret-key-at-least-32-chars"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Encryption
    VAULT_MASTER_KEY: str = "change-me-to-a-random-32-byte-hex-key"

    # MFA
    MFA_ISSUER: str = "IAM Portal"
    MFA_REQUIRED: bool = True  # Force TOTP setup for all users on first login

    # SMSC.ru SMS gateway (https://smsc.ru)
    SMSC_LOGIN: str = ""
    SMSC_PASSWORD: str = ""
    # If False, SMS MFA method is hidden and only TOTP is available
    SMSC_ENABLED: bool = False

    # SMTP Email
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = "noreply@iam-portal.ru"
    SMTP_TLS: bool = True
    EMAIL_ENABLED: bool = False

    # Frontend URL (used for password-reset links in emails)
    APP_FRONTEND_URL: str = "http://localhost:3000"

    # CORS
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:5173"

    # App
    APP_NAME: str = "Единый портал доступа"
    DEBUG: bool = True

    # OIDC / IdP
    OIDC_ISSUER: str = "http://localhost:8000"
    # Internal base URL used for server-side endpoints in discovery doc (token, userinfo, jwks).
    # Leave empty to use OIDC_ISSUER. Set to e.g. http://host.docker.internal:8000 in Docker
    # so that OIDC relying parties (Nextcloud, Odoo) can reach the token endpoint server-side
    # while the authorization_endpoint stays on localhost (cookie domain).
    OIDC_INTERNAL_BASE: str = ""
    # Browser-visible base URL for authorization_endpoint.
    # Must be reachable by the user's browser and match the cookie domain (localhost).
    # Leave empty to use OIDC_ISSUER.
    OIDC_EXTERNAL_BASE: str = ""
    # PEM-encoded RSA-2048 private key (base64-encode the PEM, or keep as multiline).
    # If empty in dev, an ephemeral key is generated on startup (do NOT use in prod).
    OIDC_PRIVATE_KEY: str = ""
    OIDC_KEY_ID: str = "iam-key-1"
    # Optional: previous key PEM for rotation — both are published in JWKS
    OIDC_PREVIOUS_KEY: str = ""
    OIDC_PREVIOUS_KEY_ID: str = "iam-key-0"
    OIDC_ID_TOKEN_TTL: int = 3600         # 1 hour (seconds)
    OIDC_ACCESS_TOKEN_TTL: int = 3600     # 1 hour
    OIDC_REFRESH_TOKEN_TTL: int = 86400   # 24 hours (sliding window)

    class Config:
        env_file = ".env"
        extra = "allow"


settings = Settings()
