<template>
  <a-layout style="min-height: 100vh">
    <!-- Mobile menu toggle button -->
    <button 
      v-if="isMobile" 
      class="mobile-menu-toggle" 
      @click="toggleMobileMenu"
      :style="{ display: mobileMenuOpen ? 'none' : 'block' }"
    >
      <MenuOutlined />
    </button>

    <!-- Mobile overlay -->
    <div 
      v-if="isMobile && mobileMenuOpen" 
      class="mobile-overlay" 
      @click="closeMobileMenu"
    ></div>

    <!-- Sidebar -->
    <a-layout-sider 
      v-model:collapsed="collapsed" 
      :collapsible="!isMobile"
      theme="dark"
      :class="{ 'mobile-hidden': isMobile && !mobileMenuOpen }"
      :style="{ position: isMobile ? 'fixed' : 'relative' }"
    >
      <div class="logo">
        <h2 v-if="!collapsed" style="color: white; text-align: center; padding: 16px 0; margin: 0; font-size: 14px;">
          Портал доступа
        </h2>
        <h2 v-else style="color: white; text-align: center; padding: 16px 0; margin: 0;">
          ПД
        </h2>
      </div>
      <a-menu theme="dark" mode="inline" :selected-keys="selectedKeys" @click="handleMenuClick">
        <a-menu-item key="dashboard" @click="$router.push('/')">
          <template #icon><AppstoreOutlined /></template>
          <span>Главная</span>
        </a-menu-item>
        <a-menu-item key="password-tools" @click="$router.push('/password-tools')">
          <template #icon><LockOutlined /></template>
          <span>Пароли</span>
        </a-menu-item>
        <a-menu-item key="app-launcher" @click="$router.push('/apps')">
          <template #icon><AppstoreOutlined /></template>
          <span>Приложения SSO</span>
        </a-menu-item>
        <a-menu-item key="profile" @click="$router.push('/profile')">
          <template #icon><UserOutlined /></template>
          <span>Профиль</span>
        </a-menu-item>

        <a-menu-divider v-if="isAdmin" />
        <a-sub-menu v-if="isAdmin" key="admin">
          <template #icon><SettingOutlined /></template>
          <template #title>Администрирование</template>
          <a-menu-item key="admin-dashboard" @click="$router.push('/admin')">
            <DashboardOutlined /> Дашборд
          </a-menu-item>
          <a-menu-item key="admin-users" @click="$router.push('/admin/users')">
            <TeamOutlined /> Пользователи
          </a-menu-item>
          <a-menu-item key="admin-roles" @click="$router.push('/admin/roles')">
            <SafetyOutlined /> Роли
          </a-menu-item>
          <a-menu-item key="admin-applications" @click="$router.push('/admin/applications')">
            <CloudOutlined /> Приложения
          </a-menu-item>
          <a-menu-item key="admin-audit" @click="$router.push('/admin/audit')">
            <FileTextOutlined /> Журнал
          </a-menu-item>
        </a-sub-menu>
      </a-menu>
    </a-layout-sider>

    <a-layout>
      <a-layout-header style="background: #fff; padding: 0 24px; display: flex; align-items: center; justify-content: space-between;">
        <span style="font-size: 16px; font-weight: 500;">
          {{ authStore.user?.full_name || 'Пользователь' }}
        </span>
        <a-space>
          <NotificationBell />
          <a-button type="text" danger @click="handleLogout">Выйти</a-button>
        </a-space>
      </a-layout-header>

      <a-layout-content style="margin: 24px; padding: 24px; background: #fff; border-radius: 8px; min-height: 360px;">
        <router-view />
      </a-layout-content>
    </a-layout>
  </a-layout>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  AppstoreOutlined, LockOutlined, UserOutlined, SettingOutlined,
  TeamOutlined, SafetyOutlined, CloudOutlined, FileTextOutlined,
  DashboardOutlined, MenuOutlined,
} from '@ant-design/icons-vue'
import { useAuthStore } from '@/stores/auth'
import { authApi } from '@/api/auth'
import { usersApi } from '@/api/users'
import NotificationBell from '@/components/common/NotificationBell.vue'

const collapsed = ref(false)
const mobileMenuOpen = ref(false)
const isMobile = ref(false)
const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()

const selectedKeys = computed(() => [route.name as string])
const isAdmin = computed(() => authStore.user?.role === 'admin')

// Check if mobile
function checkMobile() {
  isMobile.value = window.innerWidth < 768
  if (!isMobile.value) {
    mobileMenuOpen.value = false
  }
}

function toggleMobileMenu() {
  mobileMenuOpen.value = !mobileMenuOpen.value
}

function closeMobileMenu() {
  mobileMenuOpen.value = false
}

function handleMenuClick() {
  if (isMobile.value) {
    closeMobileMenu()
  }
}

onMounted(async () => {
  checkMobile()
  window.addEventListener('resize', checkMobile)

  if (!authStore.user) {
    try {
      const { data } = await usersApi.getMe()
      authStore.setUser(data)
    } catch {
      // Interceptor handles 401 refresh; if refresh fails it redirects to login
    }
  }
})

onUnmounted(() => {
  window.removeEventListener('resize', checkMobile)
})

async function handleLogout() {
  if (authStore.refreshToken) {
    try {
      await authApi.logout(authStore.refreshToken)
    } catch { /* ignore */ }
  }
  authStore.logout()
  router.push('/login')
}
</script>
