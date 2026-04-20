<template>
  <a-popover trigger="click" placement="bottomRight" @openChange="onOpen" v-model:open="popoverOpen">
    <template #content>
      <div style="width: 340px; max-height: 420px; overflow-y: auto;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
          <a-typography-text strong style="font-size: 15px">Уведомления</a-typography-text>
          <a-button v-if="unreadCount > 0" type="link" size="small" @click="markAllRead">
            Прочитать все
          </a-button>
        </div>

        <a-spin :spinning="loading">
          <a-list
            size="small"
            :data-source="notifications"
            :locale="{ emptyText: 'Нет уведомлений' }"
          >
            <template #renderItem="{ item }">
              <a-list-item
                :style="{
                  background: item.is_read ? 'transparent' : '#e6f4ff',
                  borderRadius: '6px',
                  marginBottom: '4px',
                  padding: '8px 12px',
                  cursor: item.is_read ? 'default' : 'pointer',
                }"
                @click="handleRead(item)"
              >
                <a-list-item-meta>
                  <template #avatar>
                    <a-avatar :style="{ backgroundColor: typeColor(item.type) }" size="small">
                      <template #icon>
                        <WarningOutlined v-if="item.type === 'alert'" />
                        <InfoCircleOutlined v-else-if="item.type === 'info'" />
                        <ExclamationCircleOutlined v-else-if="item.type === 'warning'" />
                        <CheckCircleOutlined v-else />
                      </template>
                    </a-avatar>
                  </template>
                  <template #title>
                    <a-typography-text :strong="!item.is_read">{{ item.title }}</a-typography-text>
                  </template>
                  <template #description>
                    <div style="font-size: 12px">{{ item.message }}</div>
                    <a-typography-text type="secondary" style="font-size: 11px">{{ formatTime(item.created_at) }}</a-typography-text>
                  </template>
                </a-list-item-meta>
              </a-list-item>
            </template>
          </a-list>
        </a-spin>
      </div>
    </template>

    <a-badge :count="unreadCount" :offset="[-2, 2]">
      <a-button type="text" shape="circle">
        <BellOutlined style="font-size: 18px" />
      </a-button>
    </a-badge>
  </a-popover>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import {
  BellOutlined, WarningOutlined, InfoCircleOutlined,
  ExclamationCircleOutlined, CheckCircleOutlined,
} from '@ant-design/icons-vue'
import { notificationsApi } from '@/api/notifications'

interface Notification {
  id: string
  type: string
  title: string
  message: string
  is_read: boolean
  created_at: string
}

const notifications = ref<Notification[]>([])
const unreadCount = ref(0)
const loading = ref(false)
const popoverOpen = ref(false)
let pollInterval: ReturnType<typeof setInterval> | null = null

function typeColor(type: string) {
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
  const diffMin = Math.floor((now.getTime() - d.getTime()) / 60000)
  if (diffMin < 1) return 'Только что'
  if (diffMin < 60) return `${diffMin} мин. назад`
  if (diffMin < 1440) return `${Math.floor(diffMin / 60)} ч. назад`
  return d.toLocaleDateString('ru-RU', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })
}

async function loadNotifications() {
  loading.value = true
  try {
    const { data } = await notificationsApi.list(false, 15)
    notifications.value = data.notifications || []
    unreadCount.value = data.unread_count ?? 0
  } catch { /* ignore */ }
  loading.value = false
}

async function loadCount() {
  try {
    const { data } = await notificationsApi.unreadCount()
    unreadCount.value = data.unread_count ?? 0
  } catch { /* ignore */ }
}

async function handleRead(item: Notification) {
  if (!item.is_read) {
    try {
      await notificationsApi.markRead(item.id)
      item.is_read = true
      unreadCount.value = Math.max(0, unreadCount.value - 1)
    } catch { /* ignore */ }
  }
}

async function markAllRead() {
  try {
    await notificationsApi.markAllRead()
    notifications.value.forEach(n => (n.is_read = true))
    unreadCount.value = 0
  } catch { /* ignore */ }
}

function onOpen(visible: boolean) {
  if (visible) loadNotifications()
}

onMounted(() => {
  loadCount()
  pollInterval = setInterval(loadCount, 30000)
})

onUnmounted(() => {
  if (pollInterval) clearInterval(pollInterval)
})
</script>
