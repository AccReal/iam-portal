<template>
  <router-view />
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { authApi } from '@/api/auth'

const authStore = useAuthStore()

onMounted(async () => {
  const desktop = (window as any).iamDesktop
  if (!desktop?.isDesktop || !authStore.accessToken) return

  // Write session.json immediately with what we have (no backend call needed).
  // Demo-apps validate the token themselves via /auth/me on launch.
  const result = await desktop.saveSession({
    access_token: authStore.accessToken,
    refresh_token: authStore.refreshToken,
    user: authStore.user,
  }).catch((e: any) => ({ ok: false, error: e?.message }))

  if (!result?.ok) {
    // Token may have user info after getMe — try once then give up
    try {
      const { data } = await authApi.getMe()
      authStore.setUser(data)
    } catch { /* backend unreachable, session.json stays without user */ }
  }
})
</script>
