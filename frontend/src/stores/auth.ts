import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export interface User {
  id: string
  email: string
  full_name: string
  role: string
  mfa_enabled: boolean
}

interface IamDesktopBridge {
  isDesktop: boolean
  saveSession: (s: { access_token: string; refresh_token: string | null; user: User | null }) => Promise<{ ok: boolean; error?: string }>
  clearSession: () => Promise<{ ok: boolean }>
  loadSession: () => Promise<unknown>
}
declare global {
  interface Window { iamDesktop?: IamDesktopBridge }
}

export const useAuthStore = defineStore('auth', () => {
  const accessToken = ref<string | null>(localStorage.getItem('access_token'))
  const refreshToken = ref<string | null>(localStorage.getItem('refresh_token'))
  const user = ref<User | null>(null)
  const mfaSessionId = ref<string | null>(null)
  const mfaMethod = ref<string | null>(null)
  const mfaSetupRequired = ref<boolean>(false)

  const isAuthenticated = computed(() => !!accessToken.value)

  function pushToDesktop() {
    if (window.iamDesktop?.isDesktop && accessToken.value) {
      window.iamDesktop.saveSession({
        access_token: accessToken.value,
        refresh_token: refreshToken.value,
        user: user.value,
      }).catch((err) => console.error('[iamDesktop.saveSession]', err))
    }
  }

  function setTokens(access: string, refresh: string) {
    accessToken.value = access
    refreshToken.value = refresh
    localStorage.setItem('access_token', access)
    localStorage.setItem('refresh_token', refresh)
    pushToDesktop()
  }

  function setUser(u: User) {
    user.value = u
    pushToDesktop()
  }

  function setMfaSession(sessionId: string, method: string) {
    mfaSessionId.value = sessionId
    mfaMethod.value = method
  }

  function completeMfaSetup() {
    mfaSetupRequired.value = false
    if (user.value) {
      user.value = { ...user.value, mfa_enabled: true }
    }
  }

  function logout() {
    accessToken.value = null
    refreshToken.value = null
    user.value = null
    mfaSessionId.value = null
    mfaSetupRequired.value = false
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    if (window.iamDesktop?.isDesktop) {
      window.iamDesktop.clearSession().catch((err) => console.error('[iamDesktop.clearSession]', err))
    }
  }

  return {
    accessToken, refreshToken, user, mfaSessionId, mfaMethod, mfaSetupRequired,
    isAuthenticated, setTokens, setUser, setMfaSession, completeMfaSetup, logout,
  }
})
