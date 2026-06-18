#!/usr/bin/env bash
#
# deploy.sh — разворачивает IAM Portal на сервере одной командой.
#
# Использование (на сервере, в папке проекта):
#     sudo bash deploy.sh
#
# Можно явно задать домен:
#     sudo bash deploy.sh my-domain.example.com
#
# Без аргумента домен берётся автоматически как <публичный-IP>.sslip.io
# (бесплатный wildcard-DNS, не требует регистрации) — на него Caddy получит
# настоящий Let's Encrypt сертификат, поэтому HTTPS будет валидным.
#
# Что делает:
#   1) ставит Docker (если его нет);
#   2) определяет домен;
#   3) генерирует .env с уникальными секретами (если его ещё нет);
#   4) поднимает все контейнеры с авто-HTTPS;
#   5) бэкенд сам прогоняет миграции и сидинг (SEED_DATA=true).

set -euo pipefail
cd "$(dirname "$0")"

COMPOSE="docker compose -f docker-compose.yml -f docker-compose.prod.yml"

echo "=================================================="
echo "  IAM Portal — деплой на сервер"
echo "=================================================="

# --- 1. Docker --------------------------------------------------------------
if ! command -v docker >/dev/null 2>&1; then
	echo ">> Docker не найден — устанавливаю..."
	curl -fsSL https://get.docker.com | sh
fi
if ! docker compose version >/dev/null 2>&1; then
	echo "!! Плагин 'docker compose' недоступен. Установите Docker посвежее." >&2
	exit 1
fi

# --- 2. Домен ---------------------------------------------------------------
if [ -n "${1:-}" ]; then
	DOMAIN="$1"
else
	IP="$(curl -fsS https://api.ipify.org 2>/dev/null || true)"
	[ -z "$IP" ] && IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
	if [ -z "$IP" ]; then
		echo "!! Не удалось определить публичный IP. Запустите: sudo bash deploy.sh <домен>" >&2
		exit 1
	fi
	DOMAIN="$(echo "$IP" | tr '.' '-').sslip.io"
fi
echo ">> Домен: https://$DOMAIN"

# --- 3. .env ----------------------------------------------------------------
if [ ! -f .env ]; then
	echo ">> Генерирую .env с уникальными секретами..."
	JWT="$(openssl rand -hex 32)"
	VAULT="$(openssl rand -hex 32)"
	OIDC_KEY="$(openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:2048 2>/dev/null)"

	cat > .env <<EOF
# === Сгенерировано deploy.sh — НЕ коммитить ===

# Публичный домен
DOMAIN=$DOMAIN
ACME_EMAIL=admin@$DOMAIN

# Database
DATABASE_URL=postgresql+asyncpg://iam_user:iam_password@db:5432/iam_db
DATABASE_URL_SYNC=postgresql://iam_user:iam_password@db:5432/iam_db

# Redis
REDIS_URL=redis://redis:6379/0

# JWT
JWT_SECRET_KEY=$JWT
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
REFRESH_TOKEN_EXPIRE_DAYS=7

# Password Vault
VAULT_MASTER_KEY=$VAULT

# MFA
MFA_ISSUER=IAM Portal
MFA_REQUIRED=false

# App
APP_NAME=Единый портал доступа
DEBUG=false

# Browser-facing URLs (один домен на портал + OIDC)
APP_FRONTEND_URL=https://$DOMAIN
CORS_ORIGINS=https://$DOMAIN

# OIDC / IdP — issuer = публичный домен; INTERNAL/EXTERNAL пустые => = issuer
OIDC_ISSUER=https://$DOMAIN
OIDC_INTERNAL_BASE=
OIDC_EXTERNAL_BASE=
OIDC_KEY_ID=iam-key-1
OIDC_ID_TOKEN_TTL=3600
OIDC_ACCESS_TOKEN_TTL=3600
OIDC_REFRESH_TOKEN_TTL=86400

# Публичные URL сервисов (используются seed.py для redirect_uris)
ODOO_PUBLIC_URL=https://odoo.$DOMAIN
NEXTCLOUD_PUBLIC_URL=https://nextcloud.$DOMAIN
GRAFANA_PUBLIC_URL=https://grafana.$DOMAIN
CRM_PUBLIC_URL=https://crm.$DOMAIN
INVENTREE_PUBLIC_URL=https://inventree.$DOMAIN
MAIL_PUBLIC_URL=https://mail.$DOMAIN

# RSA-ключ подписи OIDC ID-токенов (RS256)
OIDC_PRIVATE_KEY="$OIDC_KEY"
EOF
	echo ">> .env создан."
else
	echo ">> .env уже существует — использую его."
	DOMAIN="$(grep -E '^DOMAIN=' .env | head -1 | cut -d= -f2-)"
fi

export DOMAIN

# --- 4. Odoo: подставить публичный домен в статический OIDC-конфиг аддона ---
ODOO_XML="demo-apps/odoo-addons/iam_sso/data/oauth_provider.xml"
if [ -f "$ODOO_XML" ]; then
	sed -i "s#http://localhost:8000#https://$DOMAIN#g" "$ODOO_XML"
fi

# --- 5. Исполняемый бит у entrypoint ---------------------------------------
# bind-mount ./backend:/app перекрывает права из образа — гарантируем +x,
# иначе контейнер падает с "exec: ./entrypoint.sh: permission denied".
chmod +x backend/entrypoint.sh 2>/dev/null || true

# --- 6. Поднять всё ---------------------------------------------------------
echo ">> Собираю и запускаю контейнеры (первый раз — несколько минут)..."
$COMPOSE up -d --build

echo ""
echo "=================================================="
echo "  Готово!"
echo "=================================================="
echo "  Портал:     https://$DOMAIN"
echo "  Логин:      admin@company.ru"
echo "  Пароль:     Test123456!@"
echo ""
echo "  Сервисы (вход через портал по SSO):"
echo "    Odoo        https://odoo.$DOMAIN"
echo "    Nextcloud   https://nextcloud.$DOMAIN"
echo "    Grafana     https://grafana.$DOMAIN"
echo "    CRM         https://crm.$DOMAIN"
echo "    Склад       https://inventree.$DOMAIN"
echo "    Почта       https://mail.$DOMAIN"
echo ""
echo "  Первые 1-2 минуты Caddy получает SSL-сертификаты — если сразу"
echo "  не открылось, подождите чуть-чуть и обновите страницу."
echo "  Статус:  $COMPOSE ps"
echo "  Логи:    $COMPOSE logs -f caddy"
echo "=================================================="
