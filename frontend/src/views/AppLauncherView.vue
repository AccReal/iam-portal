<template>
  <div class="launcher">
    <header class="launcher__header">
      <h1 class="launcher__title">Корпоративный портал</h1>
      <p class="launcher__subtitle">Выберите приложение для входа через единый аккаунт</p>
    </header>

    <div v-if="loading" class="launcher__loading" role="status" aria-live="polite">
      <span class="spinner" aria-hidden="true" />
      Загрузка приложений…
    </div>

    <div v-else-if="error" class="launcher__error" role="alert">
      {{ error }}
    </div>

    <ul v-else class="launcher__grid" role="list">
      <li
        v-for="app in accessibleApps"
        :key="app.id"
        class="app-tile"
        :class="{ 'app-tile--connecting': connectingId === app.id }"
        role="listitem"
      >
        <button
          class="app-tile__btn"
          :aria-label="`Открыть ${app.name}`"
          :disabled="connectingId !== null"
          @click="launch(app)"
          @keydown.enter="launch(app)"
          @keydown.space.prevent="launch(app)"
        >
          <span class="app-tile__icon" aria-hidden="true">{{ app.icon ?? '🔗' }}</span>
          <span class="app-tile__name">{{ app.name }}</span>
          <span class="app-tile__desc">{{ app.description }}</span>
          <span v-if="connectingId === app.id" class="app-tile__status" aria-live="polite">
            Подключение…
          </span>
        </button>
      </li>
    </ul>

    <p v-if="!loading && !error && accessibleApps.length === 0" class="launcher__empty">
      Доступных приложений нет. Обратитесь к администратору.
    </p>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { getApplications } from '@/api/applications'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface App {
  id: string
  name: string
  description: string | null
  app_url: string | null
  icon: string | null
  integration_type: string
  client_id: string | null
  redirect_uris: string[]
  allowed_scopes: string | null
}

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------

const authStore = useAuthStore()
const apps = ref<App[]>([])
const loading = ref(true)
const error = ref<string | null>(null)
const connectingId = ref<string | null>(null)

// ---------------------------------------------------------------------------
// Computed: filter apps by user role
// ---------------------------------------------------------------------------

const accessibleApps = computed<App[]>(() => {
  return apps.value.filter((app) => {
    if (!app.integration_type.includes('oauth') && app.integration_type !== 'oidc') return false
    if (!app.client_id || !app.redirect_uris.length) return false
    return true
  })
})

// ---------------------------------------------------------------------------
// PKCE helpers (RFC 7636 S256)
// ---------------------------------------------------------------------------

function generateCodeVerifier(): string {
  const array = new Uint8Array(32)
  crypto.getRandomValues(array)
  return base64url(array)
}

async function generateCodeChallenge(verifier: string): Promise<string> {
  const encoder = new TextEncoder()
  const data = encoder.encode(verifier)
  const digest = await crypto.subtle.digest('SHA-256', data)
  return base64url(new Uint8Array(digest))
}

function base64url(buffer: Uint8Array): string {
  const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_'
  let result = ''
  let i = 0
  const len = buffer.length
  while (i < len) {
    const a = buffer[i++]
    const b = i < len ? buffer[i++] : 0
    const c = i < len ? buffer[i++] : 0
    result += chars[a >> 2]
    result += chars[((a & 3) << 4) | (b >> 4)]
    result += i - 2 < len ? chars[((b & 15) << 2) | (c >> 6)] : '='
    result += i - 1 < len ? chars[c & 63] : '='
  }
  // Strip padding for base64url
  return result.replace(/=+$/, '')
}

function generateState(): string {
  const array = new Uint8Array(16)
  crypto.getRandomValues(array)
  return Array.from(array, (b) => b.toString(16).padStart(2, '0')).join('')
}

// ---------------------------------------------------------------------------
// Launch SSO flow
// ---------------------------------------------------------------------------

// Empty string = same origin (localhost:3000) → Vite proxy forwards /oauth/* to backend:8000
// This ensures the refresh_token cookie (set for :3000) is included in the request.
const OIDC_BASE = ''

async function launch(app: App): Promise<void> {
  if (!app.client_id || !app.redirect_uris.length) return
  connectingId.value = app.id

  try {
    const scope = app.allowed_scopes ?? 'openid profile email'
    const state = generateState()

    // Odoo auth_oauth uses implicit flow (token in fragment); detect by redirect URI.
    // Odoo parses state as JSON to find db name ("d") and provider id ("p").
    const implicitUri = app.redirect_uris.find((u) => u.includes('auth_oauth/signin'))
    if (implicitUri) {
      const odooState = JSON.stringify({ d: 'odoo', p: 4, r: '/web' })
      const params = new URLSearchParams({
        response_type: 'token',
        client_id: app.client_id,
        redirect_uri: implicitUri,
        scope,
        state: odooState,
      })
      window.location.href = `${OIDC_BASE}/oauth/authorize?${params.toString()}`
      return
    }

    // PKCE Authorization Code flow (Nextcloud user_oidc and others)
    const redirectUri = app.redirect_uris[app.redirect_uris.length - 1]
    const verifier = generateCodeVerifier()
    const challenge = await generateCodeChallenge(verifier)

    sessionStorage.setItem(`pkce_verifier_${app.client_id}`, verifier)
    sessionStorage.setItem(`oidc_state_${app.client_id}`, state)

    const params = new URLSearchParams({
      response_type: 'code',
      client_id: app.client_id,
      redirect_uri: redirectUri,
      scope,
      state,
      code_challenge: challenge,
      code_challenge_method: 'S256',
    })

    window.location.href = `${OIDC_BASE}/oauth/authorize?${params.toString()}`
  } catch (err) {
    connectingId.value = null
    error.value = 'Не удалось начать авторизацию. Попробуйте ещё раз.'
    console.error('OIDC launch error', err)
  }
}

// ---------------------------------------------------------------------------
// Data loading
// ---------------------------------------------------------------------------

onMounted(async () => {
  try {
    const data = await getApplications()
    apps.value = data
  } catch (e) {
    error.value = 'Не удалось загрузить список приложений.'
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.launcher {
  max-width: 1100px;
  margin: 0 auto;
  padding: 2rem 1rem;
}

.launcher__header {
  margin-bottom: 2rem;
}

.launcher__title {
  font-size: 1.75rem;
  font-weight: 700;
  margin: 0 0 0.25rem;
}

.launcher__subtitle {
  color: var(--color-text-secondary, #666);
  margin: 0;
}

.launcher__loading,
.launcher__error,
.launcher__empty {
  padding: 2rem;
  text-align: center;
  color: var(--color-text-secondary, #666);
}

.launcher__error {
  color: #c0392b;
}

/* Grid — responsive, no heavy framework */
.launcher__grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 1.25rem;
  list-style: none;
  margin: 0;
  padding: 0;
}

/* Tile */
.app-tile__btn {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.5rem;
  width: 100%;
  padding: 1.5rem 1rem;
  background: var(--color-surface, #fff);
  border: 1px solid var(--color-border, #e0e0e0);
  border-radius: 12px;
  cursor: pointer;
  transition: box-shadow 0.15s, transform 0.1s;
  text-align: center;
}

.app-tile__btn:hover:not(:disabled) {
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.1);
  transform: translateY(-2px);
}

.app-tile__btn:focus-visible {
  outline: 3px solid #2563eb;
  outline-offset: 2px;
}

.app-tile__btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.app-tile--connecting .app-tile__btn {
  border-color: #2563eb;
}

.app-tile__icon {
  font-size: 2.5rem;
  line-height: 1;
}

.app-tile__name {
  font-size: 1rem;
  font-weight: 600;
}

.app-tile__desc {
  font-size: 0.8rem;
  color: var(--color-text-secondary, #666);
}

.app-tile__status {
  font-size: 0.75rem;
  color: #2563eb;
  font-weight: 500;
}

.spinner {
  display: inline-block;
  width: 20px;
  height: 20px;
  border: 3px solid #e0e0e0;
  border-top-color: #2563eb;
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
  vertical-align: middle;
  margin-right: 0.5rem;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* Responsive */
@media (max-width: 480px) {
  .launcher__grid {
    grid-template-columns: 1fr 1fr;
  }
  .launcher__title {
    font-size: 1.4rem;
  }
}
</style>
