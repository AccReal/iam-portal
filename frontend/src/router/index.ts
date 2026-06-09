import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: () => import('@/views/LoginView.vue'),
      meta: { guest: true },
    },
    {
      path: '/mfa',
      name: 'mfa',
      component: () => import('@/views/MFAView.vue'),
      meta: { guest: true },
    },
    {
      // First-time mandatory TOTP setup — requires valid access token but blocks app access
      path: '/setup-totp',
      name: 'setup-totp',
      component: () => import('@/views/SetupTOTPView.vue'),
      meta: { requiresAuth: true, setupOnly: true },
    },
    {
      path: '/',
      component: () => import('@/components/layout/AppLayout.vue'),
      meta: { requiresAuth: true },
      children: [
        {
          path: '',
          name: 'dashboard',
          component: () => import('@/views/DashboardView.vue'),
        },
        {
          path: 'admin',
          name: 'admin-dashboard',
          component: () => import('@/views/admin/AdminDashboard.vue'),
          meta: { requiresAdmin: true },
        },
        {
          path: 'password-tools',
          name: 'password-tools',
          component: () => import('@/views/PasswordToolsView.vue'),
        },
        {
          path: 'profile',
          name: 'profile',
          component: () => import('@/views/ProfileView.vue'),
        },
        {
          path: 'apps',
          name: 'app-launcher',
          component: () => import('@/views/AppLauncherView.vue'),
        },
        {
          path: 'admin/users',
          name: 'admin-users',
          component: () => import('@/views/admin/UsersView.vue'),
          meta: { requiresAdmin: true },
        },
        {
          path: 'admin/roles',
          name: 'admin-roles',
          component: () => import('@/views/admin/RolesView.vue'),
          meta: { requiresAdmin: true },
        },
        {
          path: 'admin/applications',
          name: 'admin-applications',
          component: () => import('@/views/admin/ApplicationsView.vue'),
          meta: { requiresAdmin: true },
        },
        {
          path: 'admin/audit',
          name: 'admin-audit',
          component: () => import('@/views/admin/AuditView.vue'),
          meta: { requiresAdmin: true },
        },
      ],
    },
  ],
})

router.beforeEach((to, _from, next) => {
  const authStore = useAuthStore()

  if (to.meta.requiresAuth && !authStore.isAuthenticated) {
    return next({ name: 'login' })
  }

  if (to.meta.guest && authStore.isAuthenticated) {
    // ?relogin=true: forced re-authentication (e.g. Odoo SSO account switch).
    // Clear the in-memory session so the login form shows, then proceed.
    if (to.query.relogin === 'true') {
      authStore.logout()
      return next()
    }
    // Authenticated user visiting a guest-only page — redirect appropriately
    if (authStore.mfaSetupRequired) return next({ name: 'setup-totp' })
    return next({ name: 'dashboard' })
  }

  // Enforce mandatory TOTP setup: block all app routes except /setup-totp itself
  if (authStore.isAuthenticated && authStore.mfaSetupRequired && !to.meta.setupOnly) {
    return next({ name: 'setup-totp' })
  }

  if (to.meta.requiresAdmin && authStore.user?.role !== 'admin') {
    return next({ name: 'dashboard' })
  }

  next()
})

export default router
