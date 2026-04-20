# Архитектура IAM Platform

## Обзор

IAM Platform — трёхзвенная веб-система (SPA + REST API + БД) с поддержкой асинхронных задач через Celery и интеграцией внешних приложений по протоколу SSO.

---

## Компоненты системы

```mermaid
graph TB
    subgraph Frontend ["Фронтенд (Vue 3 + TypeScript)"]
        Login["LoginView"]
        MFA["MFAView / SetupTOTPView"]
        Dashboard["DashboardView"]
        Profile["ProfileView"]
        Admin["AdminPanel\n(Users · Roles · Apps · Audit)"]
        PwdTools["PasswordToolsView"]
    end

    subgraph Backend ["Бэкенд (FastAPI)"]
        AuthAPI["POST /auth/login\nPOST /auth/mfa/verify\nPOST /auth/refresh"]
        UsersAPI["GET|POST /users\nPUT /users/{id}"]
        RolesAPI["GET|POST /roles\nPUT /roles/{id}/permissions"]
        AppsAPI["GET|POST /applications"]
        SSOAPI["POST /sso/token\nGET /sso/validate"]
        AuditAPI["GET /audit\nGET /audit/export"]
        PwdAPI["POST /password/generate\nPOST /password/check"]
    end

    subgraph Storage ["Хранилище"]
        PG[("PostgreSQL 15\nusers · roles · sessions\napplications · audit_logs\ncredentials")]
        Redis[("Redis 7\nTOTP-QR коды\nrate-limit счётчики\nCelery broker")]
    end

    subgraph Workers ["Фоновые задачи (Celery)"]
        SMS["send_sms_via_smsc\n(retry ×3)"]
        Email["send_email_notification"]
        Cleanup["cleanup_audit_logs"]
    end

    subgraph External ["Внешние приложения"]
        CRM["CRM"]
        Mail["Корпоративная почта"]
        C1["1С Бухгалтерия"]
        WH["Склад"]
    end

    Frontend -->|REST / JWT Bearer| Backend
    Backend --> Storage
    Backend --> Workers
    Workers --> Redis
    External -->|SSO токен| SSOAPI
```

---

## Модели данных

```mermaid
erDiagram
    USER {
        uuid id PK
        string email
        string password_hash
        bool mfa_enabled
        string totp_secret
        bool is_active
        bool is_blocked
        timestamp created_at
    }
    ROLE {
        uuid id PK
        string name
        json permissions
    }
    USER_ROLE {
        uuid user_id FK
        uuid role_id FK
    }
    SESSION {
        uuid id PK
        uuid user_id FK
        string refresh_token_hash
        string ip_address
        string device_fingerprint
        float risk_score
        timestamp expires_at
    }
    APPLICATION {
        uuid id PK
        string name
        string client_id
        string client_secret_hash
        bool is_active
        json allowed_roles
    }
    AUDIT_LOG {
        uuid id PK
        uuid user_id FK
        string action
        string resource
        string ip_address
        json details
        timestamp created_at
    }
    CREDENTIAL {
        uuid id PK
        uuid user_id FK
        string title
        bytes encrypted_data
        timestamp created_at
    }

    USER ||--o{ USER_ROLE : has
    ROLE ||--o{ USER_ROLE : assigned
    USER ||--o{ SESSION : owns
    USER ||--o{ AUDIT_LOG : generates
    USER ||--o{ CREDENTIAL : stores
```

---

## Потоки аутентификации

### Логин с MFA

```mermaid
sequenceDiagram
    participant U as Пользователь
    participant FE as Vue Frontend
    participant BE as FastAPI
    participant DB as PostgreSQL
    participant RD as Redis

    U->>FE: email + пароль
    FE->>BE: POST /auth/login
    BE->>DB: проверить пароль (Argon2)
    BE->>RD: проверить rate-limit
    alt MFA включён
        BE-->>FE: { mfa_required: true, temp_token }
        FE->>U: форма TOTP-кода
        U->>FE: 6-значный код
        FE->>BE: POST /auth/mfa/verify { temp_token, code }
        BE->>BE: проверить TOTP (pyotp)
    end
    BE->>DB: создать Session (fingerprint, IP, risk_score)
    BE-->>FE: { access_token, refresh_token }
    FE->>FE: сохранить токены в Pinia store
    FE->>U: редирект на Dashboard
```

### SSO-интеграция внешнего приложения

```mermaid
sequenceDiagram
    participant App as Внешнее приложение
    participant BE as FastAPI /sso
    participant DB as PostgreSQL

    App->>BE: POST /sso/token { client_id, client_secret, user_token }
    BE->>DB: проверить client_secret (hash)
    BE->>DB: проверить user_token + роль в allowed_roles
    alt доступ разрешён
        BE-->>App: { sso_token, user_info, permissions }
    else доступ запрещён
        BE-->>App: 403 Forbidden
    end
    App->>BE: GET /sso/validate { sso_token }
    BE-->>App: { valid: true, user_id, roles }
```

---

## Обнаружение аномалий

```mermaid
flowchart LR
    Login["Попытка входа"] --> RateLimit{"Rate limit\n> 5/мин?"}
    RateLimit -->|да| Block["429 Too Many Requests"]
    RateLimit -->|нет| IPCheck{"Новый IP?"}
    IPCheck -->|да| Score1["risk += 20"]
    IPCheck -->|нет| GeoCheck{"Новая\nгеолокация?"}
    GeoCheck -->|да| Score2["risk += 30"]
    Score1 & Score2 --> DeviceCheck{"Новое\nустройство?"}
    DeviceCheck -->|да| Score3["risk += 25"]
    DeviceCheck -->|нет| TimeCheck{"Необычное\nвремя?"}
    TimeCheck -->|да| Score4["risk += 15"]
    Score3 & Score4 --> Total{"risk_score\n>= 70?"}
    Total -->|да| Notify["Уведомление\nadmin + user"]
    Total -->|нет| OK["Вход разрешён"]
    Notify --> OK
```

---

## Развёртывание (Docker Compose)

```mermaid
graph LR
    subgraph dc ["docker-compose.yml"]
        FE_C["frontend\n:3000\nnginx + dist"]
        BE_C["backend\n:8000\nuvicorn"]
        W_C["celery-worker\ncelery -A app.tasks"]
        PG_C["db\n:5432\npostgres:15"]
        RD_C["redis\n:6379\nredis:7"]
    end

    FE_C -->|proxy /api| BE_C
    BE_C --> PG_C
    BE_C --> RD_C
    W_C --> RD_C
    W_C --> PG_C
```

**Переменные окружения** (`.env`):

| Переменная | Назначение |
|-----------|-----------|
| `DATABASE_URL` | asyncpg строка подключения |
| `REDIS_URL` | redis://redis:6379/0 |
| `JWT_SECRET_KEY` | ≥32 символа |
| `VAULT_MASTER_KEY` | 32-байтный hex ключ |
| `MFA_REQUIRED` | `True` — MFA обязателен |
| `SMSC_LOGIN` / `SMSC_PASSWORD` | SMS через SMSC.ru |
| `SMSC_ENABLED` | `false` — отключить SMS |
