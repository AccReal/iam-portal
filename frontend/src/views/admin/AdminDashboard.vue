<template>
  <div>
    <a-typography-title :level="3">Дашборд администратора</a-typography-title>

    <a-card style="margin-bottom: 16px">
      <a-row :gutter="16" align="middle">
        <a-col :xs="24" :sm="12" :md="8">
          <span style="margin-right: 8px">Период:</span>
          <a-select v-model:value="selectedPeriod" style="width: 200px" @change="onPeriodChange">
            <a-select-option :value="7">Последние 7 дней</a-select-option>
            <a-select-option :value="30">Последние 30 дней</a-select-option>
            <a-select-option :value="90">Последние 90 дней</a-select-option>
          </a-select>
        </a-col>
        <a-col :xs="24" :sm="12" :md="16" style="text-align: right">
          <a-button @click="loadStats" :loading="loading">
            <template #icon><ReloadOutlined /></template>
            Обновить
          </a-button>
        </a-col>
      </a-row>
    </a-card>

    <!-- Key Metrics Cards -->
    <a-row :gutter="16" style="margin-bottom: 16px">
      <a-col :xs="24" :sm="12" :md="6">
        <a-card :loading="loading">
          <a-statistic
            title="Пользователей"
            :value="stats.total_users"
            :prefix="h(UserOutlined)"
            :value-style="{ color: '#1890ff' }"
          />
        </a-card>
      </a-col>
      <a-col :xs="24" :sm="12" :md="6">
        <a-card :loading="loading">
          <a-statistic
            title="Активных сессий"
            :value="stats.active_sessions"
            :prefix="h(UnlockOutlined)"
            :value-style="{ color: '#52c41a' }"
          />
        </a-card>
      </a-col>
      <a-col :xs="24" :sm="12" :md="6">
        <a-card :loading="loading">
          <a-statistic
            title="События сегодня"
            :value="stats.events_today"
            :prefix="h(BarChartOutlined)"
            :value-style="{ color: '#722ed1' }"
          />
        </a-card>
      </a-col>
      <a-col :xs="24" :sm="12" :md="6">
        <a-card :loading="loading">
          <a-statistic
            title="Заблокировано"
            :value="stats.blocked_users"
            :prefix="h(StopOutlined)"
            :value-style="{ color: '#ff4d4f' }"
          />
        </a-card>
      </a-col>
    </a-row>

    <!-- Login Trends Chart -->
    <a-card title="График входов" style="margin-bottom: 16px" :loading="loading">
      <Line v-if="!loading && chartData" :data="chartData" :options="chartOptions" />
      <a-empty v-else-if="!loading" description="Нет данных" />
    </a-card>

    <!-- Event Distribution and Top Risk Events -->
    <a-row :gutter="16">
      <a-col :xs="24" :md="12">
        <a-card title="Распределение событий" :loading="loading">
          <Pie v-if="!loading && pieData" :data="pieData" :options="pieOptions" />
          <a-empty v-else-if="!loading" description="Нет данных" />
        </a-card>
      </a-col>
      <a-col :xs="24" :md="12">
        <a-card title="Топ-10 рисковых событий" :loading="loading">
          <a-list
            v-if="!loading && stats.top_risk_events && stats.top_risk_events.length > 0"
            :data-source="stats.top_risk_events"
            size="small"
          >
            <template #renderItem="{ item, index }">
              <a-list-item>
                <a-list-item-meta>
                  <template #title>
                    <span style="font-weight: 500">{{ index + 1 }}. {{ item.user_email || 'Неизвестно' }}</span>
                  </template>
                  <template #description>
                    <a-space>
                      <span>{{ item.action }}</span>
                      <a-tag :color="getRiskColor(item.risk_score)">
                        Риск: {{ item.risk_score }}
                      </a-tag>
                      <span style="font-size: 12px; color: #999">
                        {{ formatDateTime(item.created_at) }}
                      </span>
                    </a-space>
                  </template>
                </a-list-item-meta>
              </a-list-item>
            </template>
          </a-list>
          <a-empty v-else-if="!loading" description="Нет событий с высоким риском" />
        </a-card>
      </a-col>
    </a-row>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed, h } from 'vue'
import { message } from 'ant-design-vue'
import {
  ReloadOutlined, UserOutlined, UnlockOutlined,
  BarChartOutlined, StopOutlined
} from '@ant-design/icons-vue'
import { Line, Pie } from 'vue-chartjs'
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  ArcElement
} from 'chart.js'
import { auditApi } from '@/api/audit'

// Register Chart.js components
ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  ArcElement
)

interface DashboardStats {
  total_users: number
  active_sessions: number
  events_today: number
  blocked_users: number
  failed_logins_today: number
  high_risk_events_today: number
  login_trends: Array<{
    date: string
    successful: number
    failed: number
  }>
  event_distribution: Array<{
    action: string
    count: number
  }>
  top_risk_events: Array<{
    id: string
    user_email: string | null
    action: string
    risk_score: number
    created_at: string
    ip_address: string | null
    details: any
  }>
}

const loading = ref(false)
const selectedPeriod = ref(7)
const stats = ref<DashboardStats>({
  total_users: 0,
  active_sessions: 0,
  events_today: 0,
  blocked_users: 0,
  failed_logins_today: 0,
  high_risk_events_today: 0,
  login_trends: [],
  event_distribution: [],
  top_risk_events: []
})

const chartData = computed(() => {
  if (!stats.value.login_trends || stats.value.login_trends.length === 0) {
    return null
  }

  const labels = stats.value.login_trends.map(t => {
    const date = new Date(t.date)
    return date.toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit' })
  })

  return {
    labels,
    datasets: [
      {
        label: 'Успешные',
        data: stats.value.login_trends.map(t => t.successful),
        borderColor: '#52c41a',
        backgroundColor: 'rgba(82, 196, 26, 0.1)',
        tension: 0.3
      },
      {
        label: 'Неудачные',
        data: stats.value.login_trends.map(t => t.failed),
        borderColor: '#ff4d4f',
        backgroundColor: 'rgba(255, 77, 79, 0.1)',
        tension: 0.3
      }
    ]
  }
})

const chartOptions = {
  responsive: true,
  maintainAspectRatio: true,
  plugins: {
    legend: {
      position: 'top' as const
    },
    title: {
      display: false
    }
  },
  scales: {
    y: {
      beginAtZero: true,
      ticks: {
        precision: 0
      }
    }
  }
}

const pieData = computed(() => {
  if (!stats.value.event_distribution || stats.value.event_distribution.length === 0) {
    return null
  }

  const colors = [
    '#1890ff', '#52c41a', '#faad14', '#f5222d', '#722ed1',
    '#13c2c2', '#eb2f96', '#fa8c16', '#a0d911', '#2f54eb'
  ]

  return {
    labels: stats.value.event_distribution.map(e => getActionLabel(e.action)),
    datasets: [
      {
        data: stats.value.event_distribution.map(e => e.count),
        backgroundColor: colors.slice(0, stats.value.event_distribution.length),
        borderWidth: 1
      }
    ]
  }
})

const pieOptions = {
  responsive: true,
  maintainAspectRatio: true,
  plugins: {
    legend: {
      position: 'right' as const
    }
  }
}

function getActionLabel(action: string): string {
  const labels: Record<string, string> = {
    login: 'Вход',
    logout: 'Выход',
    mfa_verify: 'MFA проверка',
    user_create: 'Создание пользователя',
    user_update: 'Обновление пользователя',
    user_block: 'Блокировка',
    user_unblock: 'Разблокировка',
    password_reset: 'Сброс пароля',
    role_create: 'Создание роли',
    role_update: 'Обновление роли',
    role_delete: 'Удаление роли',
    sso_authorize: 'SSO авторизация',
    anomaly_detected: 'Аномалия обнаружена'
  }
  return labels[action] || action
}

function getRiskColor(score: number): string {
  if (score >= 70) return 'red'
  if (score >= 40) return 'orange'
  return 'green'
}

function formatDateTime(iso: string): string {
  if (!iso) return '—'
  const date = new Date(iso)
  return date.toLocaleString('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}

async function loadStats() {
  loading.value = true
  try {
    const { data } = await auditApi.getStats(selectedPeriod.value)
    stats.value = data
  } catch (e: any) {
    message.error(e.response?.data?.detail || 'Не удалось загрузить статистику')
  } finally {
    loading.value = false
  }
}

function onPeriodChange() {
  loadStats()
}

onMounted(() => {
  loadStats()
})
</script>
