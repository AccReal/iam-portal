<?php
/**
 * Roundcube configuration — IAM Portal OAuth2 integration.
 *
 * OAuth2 flow: user is redirected to IAM → IAM auto-approves (session cookie) →
 * Roundcube exchanges code for access token → uses XOAUTH2 with Dovecot IMAP.
 *
 * Redirect URI registered in IAM: http://localhost:8093/index.php/login/oauth
 */

// --- Database (PostgreSQL via Docker service) ---
$config['db_dsnw'] = 'pgsql://roundcube:roundcube_password@roundcube-db/roundcube';

// --- IMAP (Dovecot inside Docker network) ---
$config['imap_host']       = 'dovecot:143';
$config['imap_auth_type']  = 'PLAIN';

// Use 'sub' claim as IMAP password instead of XOAUTH2.
// Dovecot accepts any password (real auth already done via IAM OAuth2).
$config['oauth_password_claim'] = 'sub';

// --- SMTP (disabled — demo only receives mail) ---
$config['smtp_host']   = '';
$config['smtp_port']   = 25;
$config['smtp_user']   = '';
$config['smtp_pass']   = '';

// --- OAuth2 / OIDC provider ---
$config['oauth_provider']      = 'generic';
$config['oauth_provider_name'] = 'IAM Portal';
$config['oauth_client_id']     = 'roundcube';
$config['oauth_client_secret'] = 'RoundcubeSecret2024';

// Browser-accessible (authorization redirect)
$config['oauth_auth_uri']     = 'http://localhost:8000/oauth/authorize';
// Server-to-server (token exchange & userinfo)
$config['oauth_token_uri']    = 'http://backend:8000/oauth/token';
$config['oauth_identity_uri'] = 'http://backend:8000/oauth/userinfo';

$config['oauth_scope']        = 'openid profile email';
$config['oauth_redirect_uri'] = 'http://localhost:8093/index.php/login/oauth';

// Map IAM claims to Roundcube identity
$config['oauth_identity_fields'] = ['email'];

// --- General settings ---
$config['product_name']    = 'Корпоративная почта';
$config['default_charset'] = 'UTF-8';
$config['language']        = 'ru_RU';
$config['support_url']     = '';

// Trust the proxy / Docker network headers
$config['use_https'] = false;
$config['force_https'] = false;

// --- Plugins ---
$config['plugins'] = [];
