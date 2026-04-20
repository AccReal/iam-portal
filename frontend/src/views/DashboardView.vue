<template>
  <div>
    <!-- Greeting -->
    <a-row :gutter="24" style="margin-bottom: 24px" align="middle">
      <a-col :flex="'auto'">
        <a-typography-title :level="3" style="margin-bottom: 4px">
          {{ greeting }}, {{ user?.full_name || 'Пользователь' }}!
        </a-typography-title>
        <a-typography-text type="secondary">
          {{ todayFormatted }} &middot; Роль: {{ roleName }}
        </a-typography-text>
      </a-col>
      <a-col>
        <a-space>
          <a-tag :color="user?.mfa_enabled ? 'green' : 'orange'">
            MFA: {{ user?.mfa_enabled ? 'Включена' : 'Отключена' }}
          </a-tag>
          <a-tag :color="user?.is_active ? 'green' : 'red'">
            {{ user?.is_active ? 'Активен' : 'Отключён' }}
          </a-tag>
        </a-space>
      </a-col>
    </a-row>

    <!-- SSO Apps grid -->
    <a-card title="Мои приложения" style="margin-bottom: 24px" :loading="loadingApps">
      <template #extra>
        <a-typography-text type="secondary">{{ apps.length }} доступно</a-typography-text>
      </template>

      <a-empty v-if="!loadingApps && apps.length === 0" description="Нет доступных приложений" />

      <a-row :gutter="[16, 16]" v-else>
        <a-col :xs="12" :sm="8" :md="6" :lg="4" v-for="app in apps" :key="app.id">
          <a-card
            hoverable
            size="small"
            @click="launchApp(app)"
            :bodyStyle="{ textAlign: 'center', padding: '16px 8px' }"
          >
            <div style="font-size: 32px; margin-bottom: 8px; color: #1890ff;">
              <component :is="getAppIcon(app.integration_type)" />
            </div>
            <a-typography-text strong :ellipsis="{ tooltip: app.name }" style="display: block">
              {{ app.name }}
            </a-typography-text>
            <a-typography-text type="secondary" style="font-size: 12px">
              {{ integrationLabel(app.integration_type) }}
            </a-typography-text>
          </a-card>
        </a-col>
      </a-row>
    </a-card>

    <a-row :gutter="24">
      <!-- Recent Activity -->
      <a-col :xs="24" :lg="14">
        <a-card title="Недавняя активность" style="margin-bottom: 24px" :loading="loadingActivity">
          <a-empty v-if="!loadingActivity && activities.length === 0" description="Нет записей активности" />
          <a-timeline v-else>
            <a-timeline-item
              v-for="item in activities"
              :key="item.id"
              :color="item.success ? 'green' : 'red'"
            >
              <div style="display: flex; justify-content: space-between; align-items: flex-start;">
                <div>
                  <a-typography-text strong>{{ actionLabel(item.action) }}</a-typography-text>
                  <br />
                  <a-typography-text type="secondary" style="font-size: 12px">
                    IP: {{ item.ip_address || 'N/A' }}
                    <a-tag v-if="item.risk_score && item.risk_score > 0" :color="riskColor(item.risk_score)" size="small" style="margin-left: 4px">
                      Риск: {{ item.risk_score }}
                    </a-tag>
                  </a-typography-text>
                </div>
                <a-typography-text type="secondary" style="font-size: 12px; white-space: nowrap">
                  {{ formatTime(item.created_at) }}
                </a-typography-text>
              </div>
            </a-timeline-item>
          </a-timeline>
        </a-card>
      </a-col>

      <!-- Notifications -->
      <a-col :xs="24" :lg="10">
        <a-card style="margin-bottom: 24px" :loading="loadingNotifications">
          <template #title>
            Уведомления
            <a-badge :count="unreadCount" :offset="[8, -4]" />
          </template>
          <template #extra>
            <a-button
              v-if="unreadCount > 0"
              type="link"
              size="small"
              @click="handleMarkAllRead"
            >
              Прочитать все
            </a-button>
          </template>

          <a-empty v-if="!loadingNotifications && notifications.length === 0" description="Нет уведомлений" />
          <a-list v-else :data-source="notifications" size="small">
            <template #renderItem="{ item }">
              <a-list-item
                :style="{ background: item.is_read ? 'transparent' : '#e6f4ff', borderRadius: '6px', marginBottom: '4px', padding: '8px 12px', cursor: 'pointer' }"
                @click="handleReadNotification(item)"
              >
                <a-list-item-meta>
                  <template #avatar>
                    <a-avatar :style="{ backgroundColor: notifTypeColor(item.type) }" size="small">
                      <template #icon>
                        <BellOutlined v-if="item.type === 'alert'" />
                        <InfoCircleOutlined v-else-if="item.type === 'info'" />
                        <WarningOutlined v-else-if="item.type === 'warning'" />
                        <CheckCircleOutlined v-else />
                      </template>
                    </a-avatar>
                  </template>
                  <template #title>
                    <a-typography-text :strong="!item.is_read">{{ item.title }}</a-typography-text>
                  </template>
                  <template #description>
                    <div>{{ item.message }}</div>
                    <a-typography-text type="secondary" style="font-size: 11px">{{ formatTime(item.created_at) }}</a-typography-text>
                  </template>
                </a-list-item-meta>
              </a-list-item>
            </template>
          </a-list>
        </a-card>
      </a-col>
    </a-row>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import {
  CloudOutlined, SafetyOutlined, KeyOutlined,
  BellOutlined, InfoCircleOutlined, WarningOutlined, CheckCircleOutlined,
} from '@ant-design/icons-vue'
import { useAuthStore } from '@/stores/auth'
import { usersApi } from '@/api/users'
import { ssoApi } from '@/api/sso'
import { notificationsApi } from '@/api/notifications'

interface App {
  id: string
  name: string
  description: string | null
  app_url: string | null
  icon: string | null
  integration_type: string
}

interface Activity {
  id: string
  action: string
  ip_address: string | null
  success: boolean
  risk_score: number | null
  created_at: string
}

interface Notification {
  id: string
  type: string
  title: string
  message: string
  is_read: boolean
  created_at: string
}

const authStore = useAuthStore()
const user = ref<any>(null)
const apps = ref<App[]>([])
const activities = ref<Activity[]>([])
const notifications = ref<Notification[]>([])
const unreadCount = ref(0)
const loadingApps = ref(true)
const loadingActivity = ref(true)
const loadingNotifications = ref(true)

const greeting = computed(() => {
  const h = new Date().getHours()
  if (h < 6) return 'Доброй ночи'
  if (h < 12) return 'Доброе утро'
  if (h < 18) return 'Добрый день'
  return 'Добрый вечер'
})

const todayFormatted = computed(() => {
  return new Date().toLocaleDateString('ru-RU', {
    weekday: 'long', year: 'numeric', month: 'long', day: 'numeric',
  })
})

const roleName = computed(() => {
  const names: Record<string, string> = {
    admin: 'Администратор', manager: 'Менеджер', accountant: 'Бухгалтер', user: 'Пользователь',
  }
  return names[user.value?.role] || user.value?.role || '—'
})

function getAppIcon(type: string) {
  switch (type) {
    case 'oauth': return CloudOutlined
    case 'saml': return SafetyOutlined
    case 'vault': return KeyOutlined
    default: return CloudOutlined
  }
}

function integrationLabel(type: string) {
  const labels: Record<string, string> = { oauth: 'OAuth 2.0', saml: 'SAML', vault: 'Хранилище' }
  return labels[type] || type
}

const actionLabels: Record<string, string> = {
  login: 'Вход в систему',
  login_failed: 'Неудачный вход',
  logout: 'Выход из системы',
  register: 'Регистрация',
  mfa_verify: 'Проверка MFA',
  mfa_setup: 'Настройка MFA',
  password_change: 'Смена пароля',
  sso_authorize: 'SSO-авторизация',
  user_created: 'Создание пользователя',
  user_updated: 'Обновление пользователя',
  user_blocked: 'Блокировка пользователя',
  user_unblocked: 'Разблокировка пользователя',
  honeypot_triggered: 'Сработала ловушка',
  anomaly_detected: 'Обнаружена аномалия',
}

function actionLabel(action: string) {
  return actionLabels[action] || action
}

function riskColor(score: number) {
  if (score >= 70) return 'red'
  if (score >= 40) return 'orange'
  return 'green'
}

function notifTypeColor(type: string) {
  switch (type) {
    case 'alert': return '#ff4d4f'
    case 'warning': return '#faad14'
    case 'info': return '#1890ff'
    default: return '#52c41a'
  }
}

function formatTime(iso: string) {
  const d = new Date(iso)
  const now = new Date()
  const diffMs = now.getTime() - d.getTime()
  const diffMin = Math.floor(diffMs / 60000)

  if (diffMin < 1) return 'Только что'
  if (diffMin < 60) return `${diffMin} мин. назад`
  if (diffMin < 1440) return `${Math.floor(diffMin / 60)} ч. назад`

  return d.toLocaleDateString('ru-RU', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })
}

onMounted(async () => {
  try {
    const { data } = await usersApi.getMe()
    user.value = data
    authStore.setUser(data)
  } catch { /* interceptor handles */ }

  // Load apps, activity, notifications in parallel
  const [appsP, activityP, notifsP] = await Promise.allSettled([
    ssoApi.getMyApps(),
    usersApi.getMyActivity(10),
    notificationsApi.list(false, 10),
  ])

  if (appsP.status === 'fulfilled') apps.value = appsP.value.data.apps || []
  loadingApps.value = false

  if (activityP.status === 'fulfilled') activities.value = activityP.value.data.activities || []
  loadingActivity.value = false

  if (notifsP.status === 'fulfilled') {
    notifications.value = notifsP.value.data.notifications || []
    unreadCount.value = notifsP.value.data.unread_count || 0
  }
  loadingNotifications.value = false
})

async function launchApp(app: App) {
  // Desktop mode — launch .exe demo apps via Electron IPC
  if ((window as any).iamDesktop?.isDesktop) {
    const result = await (window as any).iamDesktop.launchApp(app.id)
    if (!result?.ok) {
      message.warning('Приложение недоступно в демо-режиме')
    }
    return
  }

  // Web mode — open app_url in new tab.
  // OIDC apps (Odoo, Nextcloud) handle SSO themselves: they redirect to IAM,
  // IAM sees the refresh_token cookie and auto-approves without asking for credentials.
  if (app.app_url) {
    window.open(app.app_url, '_blank')
  } else {
    message.info('Приложение недоступно в веб-режиме')
  }
}

async function handleReadNotification(item: Notification) {
  if (!item.is_read) {
    try {
      await notificationsApi.markRead(item.id)
      item.is_read = true
      unreadCount.value = Math.max(0, unreadCount.value - 1)
    } catch { /* ignore */ }
  }
}

async function handleMarkAllRead() {
  try {
    await notificationsApi.markAllRead()
    notifications.value.forEach(n => (n.is_read = true))
    unreadCount.value = 0
    message.success('Все уведомления прочитаны')
  } catch { /* ignore */ }
}
</script>
