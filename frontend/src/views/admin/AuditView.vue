<template>
  <div>
    <a-typography-title :level="3">Журнал аудита</a-typography-title>

    <a-card>
      <!-- Фильтры -->
      <a-form layout="vertical" style="margin-bottom: 16px">
        <a-row :gutter="16">
          <a-col :xs="24" :sm="12" :md="6">
            <a-form-item label="Период">
              <a-range-picker
                v-model:value="dateRange"
                format="DD.MM.YYYY"
                :placeholder="['От', 'До']"
                style="width: 100%"
                @change="onDateChange"
              />
            </a-form-item>
          </a-col>

          <a-col :xs="24" :sm="12" :md="6">
            <a-form-item label="Пользователь">
              <a-select
                v-model:value="filters.user_id"
                placeholder="Все"
                allow-clear
                show-search
                :filter-option="filterUserOption"
                :options="userOptions"
                @change="applyFilters"
              />
            </a-form-item>
          </a-col>

          <a-col :xs="24" :sm="12" :md="6">
            <a-form-item label="Действие">
              <a-select
                v-model:value="filters.action"
                placeholder="Все"
                allow-clear
                :options="actionOptions"
                @change="applyFilters"
              />
            </a-form-item>
          </a-col>

          <a-col :xs="24" :sm="12" :md="6">
            <a-form-item label="Мин. риск-скор">
              <a-input-number
                v-model:value="filters.min_risk_score"
                :min="0"
                :max="100"
                placeholder="0"
                style="width: 100%"
                @change="applyFilters"
              />
            </a-form-item>
          </a-col>
        </a-row>

        <a-row :gutter="16">
          <a-col :xs="24" :sm="12" :md="8">
            <a-form-item label="Статус">
              <a-select
                v-model:value="filters.success"
                placeholder="Все"
                allow-clear
                :options="statusOptions"
                @change="applyFilters"
              />
            </a-form-item>
          </a-col>

          <a-col :xs="24" :sm="12" :md="16">
            <a-form-item label="Поиск">
              <a-input-search
                v-model:value="filters.search"
                placeholder="Поиск по email, действию, IP, деталям..."
                allow-clear
                @search="applyFilters"
              />
            </a-form-item>
          </a-col>
        </a-row>

        <a-row>
          <a-col :span="24">
            <a-space>
              <a-button @click="applyFilters" type="primary">
                <template #icon><SearchOutlined /></template>
                Применить
              </a-button>
              <a-button @click="resetFilters">
                <template #icon><ClearOutlined /></template>
                Сбросить
              </a-button>
              <a-button @click="exportCSV" :loading="exporting">
                <template #icon><DownloadOutlined /></template>
                Экспорт CSV
              </a-button>
              <a-button @click="exportXLSX" :loading="exporting">
                <template #icon><FileExcelOutlined /></template>
                Экспорт XLSX
              </a-button>
            </a-space>
          </a-col>
        </a-row>
      </a-form>

      <!-- Таблица -->
      <a-table
        :columns="columns"
        :data-source="filteredLogs"
        :loading="loading"
        :pagination="false"
        row-key="id"
        size="middle"
        :scroll="{ x: 1200 }"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'created_at'">
            {{ formatDateTime(record.created_at) }}
          </template>

          <template v-else-if="column.key === 'user'">
            <div v-if="record.user_name">
              <div style="font-weight: 500">{{ record.user_name }}</div>
              <div style="font-size: 12px; color: #999">{{ record.user_email }}</div>
            </div>
            <span v-else style="color: #999">—</span>
          </template>

          <template v-else-if="column.key === 'action'">
            <a-tag>{{ formatAction(record.action) }}</a-tag>
          </template>

          <template v-else-if="column.key === 'success'">
            <a-tag :color="record.success ? 'green' : 'red'">
              {{ record.success ? 'Успех' : 'Ошибка' }}
            </a-tag>
          </template>

          <template v-else-if="column.key === 'risk_score'">
            <a-tag v-if="record.risk_score != null" :color="getRiskColor(record.risk_score)">
              {{ record.risk_score }}
            </a-tag>
            <span v-else style="color: #999">—</span>
          </template>

          <template v-else-if="column.key === 'actions'">
            <a-button size="small" type="link" @click="showDetails(record)">
              <template #icon><EyeOutlined /></template>
            </a-button>
          </template>
        </template>
      </a-table>

      <!-- Пагинация -->
      <div style="margin-top: 16px; text-align: right">
        <a-pagination
          v-model:current="page"
          v-model:page-size="perPage"
          :total="total"
          :page-size-options="['10', '20', '50', '100']"
          show-size-changer
          show-quick-jumper
          :show-total="(t: number) => `Всего: ${t}`"
          @change="loadLogs"
          @show-size-change="onPageSizeChange"
        />
      </div>
    </a-card>

    <!-- Модалка деталей -->
    <a-modal
      v-model:open="detailsModalOpen"
      title="Детали события"
      :footer="null"
      width="700px"
    >
      <a-descriptions v-if="selectedLog" bordered :column="1" size="small">
        <a-descriptions-item label="ID">
          {{ selectedLog.id }}
        </a-descriptions-item>
        <a-descriptions-item label="Время">
          {{ formatDateTime(selectedLog.created_at) }}
        </a-descriptions-item>
        <a-descriptions-item label="Пользователь">
          <div v-if="selectedLog.user_name">
            {{ selectedLog.user_name }} ({{ selectedLog.user_email }})
          </div>
          <span v-else style="color: #999">Системное событие</span>
        </a-descriptions-item>
        <a-descriptions-item label="Действие">
          {{ formatAction(selectedLog.action) }}
        </a-descriptions-item>
        <a-descriptions-item label="Ресурс">
          <span v-if="selectedLog.resource_type">
            {{ selectedLog.resource_type }}
            <span v-if="selectedLog.resource_id" style="color: #999">
              ({{ selectedLog.resource_id }})
            </span>
          </span>
          <span v-else style="color: #999">—</span>
        </a-descriptions-item>
        <a-descriptions-item label="IP-адрес">
          {{ selectedLog.ip_address || '—' }}
        </a-descriptions-item>
        <a-descriptions-item label="User-Agent">
          <div style="word-break: break-all; font-size: 12px">
            {{ selectedLog.user_agent || '—' }}
          </div>
        </a-descriptions-item>
        <a-descriptions-item label="Статус">
          <a-tag :color="selectedLog.success ? 'green' : 'red'">
            {{ selectedLog.success ? 'Успех' : 'Ошибка' }}
          </a-tag>
        </a-descriptions-item>
        <a-descriptions-item label="Риск-скор">
          <a-tag v-if="selectedLog.risk_score != null" :color="getRiskColor(selectedLog.risk_score)">
            {{ selectedLog.risk_score }}
          </a-tag>
          <span v-else style="color: #999">—</span>
        </a-descriptions-item>
        <a-descriptions-item label="Детали">
          <pre v-if="selectedLog.details" style="margin: 0; font-size: 12px; max-height: 300px; overflow: auto">{{ JSON.stringify(selectedLog.details, null, 2) }}</pre>
          <span v-else style="color: #999">—</span>
        </a-descriptions-item>
      </a-descriptions>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { message } from 'ant-design-vue'
import type { Dayjs } from 'dayjs'
import {
  SearchOutlined, ClearOutlined, DownloadOutlined, FileExcelOutlined, EyeOutlined,
} from '@ant-design/icons-vue'
import { auditApi } from '@/api/audit'
import { usersApi } from '@/api/users'

interface AuditLogEntry {
  id: string
  user_id: string | null
  user_email: string | null
  user_name: string | null
  action: string
  resource_type: string | null
  resource_id: string | null
  ip_address: string | null
  user_agent: string | null
  success: boolean
  risk_score: number | null
  details: Record<string, any> | null
  created_at: string
}

interface UserOption {
  value: string
  label: string
}

const logs = ref<AuditLogEntry[]>([])
const loading = ref(false)
const exporting = ref(false)
const total = ref(0)
const page = ref(1)
const perPage = ref(20)

const dateRange = ref<[Dayjs, Dayjs] | null>(null)
const filters = ref({
  user_id: undefined as string | undefined,
  action: undefined as string | undefined,
  min_risk_score: undefined as number | undefined,
  success: undefined as boolean | undefined,
  search: '',
})

const users = ref<UserOption[]>([])
const detailsModalOpen = ref(false)
const selectedLog = ref<AuditLogEntry | null>(null)

const columns = [
  { title: 'Время', key: 'created_at', width: 150 },
  { title: 'Пользователь', key: 'user', width: 200 },
  { title: 'Действие', key: 'action', width: 150 },
  { title: 'IP', key: 'ip_address', dataIndex: 'ip_address', width: 140 },
  { title: 'Статус', key: 'success', width: 100 },
  { title: 'Риск', key: 'risk_score', width: 80 },
  { title: '', key: 'actions', width: 60, fixed: 'right' as const },
]

const actionOptions = [
  { value: 'login', label: 'Вход' },
  { value: 'logout', label: 'Выход' },
  { value: 'mfa_verify', label: 'MFA проверка' },
  { value: 'user_create', label: 'Создание пользователя' },
  { value: 'user_update', label: 'Обновление пользователя' },
  { value: 'user_block', label: 'Блокировка пользователя' },
  { value: 'user_unblock', label: 'Разблокировка пользователя' },
  { value: 'password_reset', label: 'Сброс пароля' },
  { value: 'role_create', label: 'Создание роли' },
  { value: 'role_update', label: 'Обновление роли' },
  { value: 'role_delete', label: 'Удаление роли' },
  { value: 'permission_update', label: 'Обновление прав' },
  { value: 'sso_authorize', label: 'SSO авторизация' },
  { value: 'anomaly_detected', label: 'Обнаружена аномалия' },
]

const statusOptions = [
  { value: true, label: 'Успех' },
  { value: false, label: 'Ошибка' },
]

const userOptions = computed(() => users.value)

// Client-side filtering for search
const filteredLogs = computed(() => {
  if (!filters.value.search) return logs.value
  
  const query = filters.value.search.toLowerCase()
  return logs.value.filter(log => {
    return (
      log.user_email?.toLowerCase().includes(query) ||
      log.user_name?.toLowerCase().includes(query) ||
      log.action.toLowerCase().includes(query) ||
      log.ip_address?.toLowerCase().includes(query) ||
      JSON.stringify(log.details || {}).toLowerCase().includes(query)
    )
  })
})

function getRiskColor(score: number): string {
  if (score < 40) return 'green'
  if (score < 70) return 'orange'
  return 'red'
}

function formatAction(action: string): string {
  const option = actionOptions.find(o => o.value === action)
  return option?.label || action
}

function formatDateTime(iso: string): string {
  if (!iso) return '—'
  const date = new Date(iso)
  return date.toLocaleString('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}

function filterUserOption(input: string, option: any): boolean {
  return option.label.toLowerCase().includes(input.toLowerCase())
}

async function loadLogs() {
  loading.value = true
  try {
    const params: any = {
      page: page.value,
      per_page: perPage.value,
    }

    if (filters.value.user_id) params.user_id = filters.value.user_id
    if (filters.value.action) params.action = filters.value.action
    if (dateRange.value && dateRange.value[0]) {
      params.date_from = dateRange.value[0].startOf('day').toISOString()
    }
    if (dateRange.value && dateRange.value[1]) {
      params.date_to = dateRange.value[1].endOf('day').toISOString()
    }

    const { data } = await auditApi.list(params)
    
    // Apply client-side filters
    let filteredData = data.logs
    
    // Filter by risk score
    if (filters.value.min_risk_score != null) {
      filteredData = filteredData.filter((log: AuditLogEntry) => 
        log.risk_score != null && log.risk_score >= filters.value.min_risk_score!
      )
    }
    
    // Filter by success status
    if (filters.value.success != null) {
      filteredData = filteredData.filter((log: AuditLogEntry) => 
        log.success === filters.value.success
      )
    }
    
    logs.value = filteredData
    total.value = data.total
  } catch (e: any) {
    message.error(e.response?.data?.detail || 'Не удалось загрузить журнал аудита')
  } finally {
    loading.value = false
  }
}

async function loadUsers() {
  try {
    const { data } = await usersApi.list(1, 1000)
    users.value = data.users.map((u: any) => ({
      value: u.id,
      label: `${u.full_name} (${u.email})`,
    }))
  } catch {
    // silent
  }
}

function onDateChange() {
  applyFilters()
}

function applyFilters() {
  page.value = 1
  loadLogs()
}

function resetFilters() {
  dateRange.value = null
  filters.value = {
    user_id: undefined,
    action: undefined,
    min_risk_score: undefined,
    success: undefined,
    search: '',
  }
  page.value = 1
  loadLogs()
}

function onPageSizeChange(_cur: number, size: number) {
  perPage.value = size
  page.value = 1
  loadLogs()
}

async function exportCSV() {
  exporting.value = true
  try {
    const params: any = {}
    if (filters.value.user_id) params.user_id = filters.value.user_id
    if (filters.value.action) params.action = filters.value.action
    if (dateRange.value && dateRange.value[0]) {
      params.date_from = dateRange.value[0].startOf('day').toISOString()
    }
    if (dateRange.value && dateRange.value[1]) {
      params.date_to = dateRange.value[1].endOf('day').toISOString()
    }

    const { data } = await auditApi.exportCsv(params)
    const url = window.URL.createObjectURL(new Blob([data]))
    const link = document.createElement('a')
    link.href = url
    link.setAttribute('download', `audit_log_${new Date().toISOString().split('T')[0]}.csv`)
    document.body.appendChild(link)
    link.click()
    link.remove()
    window.URL.revokeObjectURL(url)
    message.success('Экспорт CSV завершён')
  } catch (e: any) {
    message.error(e.response?.data?.detail || 'Ошибка экспорта')
  } finally {
    exporting.value = false
  }
}

async function exportXLSX() {
  exporting.value = true
  try {
    const params: any = {}
    if (filters.value.user_id) params.user_id = filters.value.user_id
    if (filters.value.action) params.action = filters.value.action
    if (dateRange.value && dateRange.value[0]) {
      params.date_from = dateRange.value[0].startOf('day').toISOString()
    }
    if (dateRange.value && dateRange.value[1]) {
      params.date_to = dateRange.value[1].endOf('day').toISOString()
    }

    const { data } = await auditApi.exportXlsx(params)
    const url = window.URL.createObjectURL(new Blob([data]))
    const link = document.createElement('a')
    link.href = url
    link.setAttribute('download', `audit_log_${new Date().toISOString().split('T')[0]}.xlsx`)
    document.body.appendChild(link)
    link.click()
    link.remove()
    window.URL.revokeObjectURL(url)
    message.success('Экспорт XLSX завершён')
  } catch (e: any) {
    message.error(e.response?.data?.detail || 'Ошибка экспорта')
  } finally {
    exporting.value = false
  }
}

function showDetails(log: AuditLogEntry) {
  selectedLog.value = log
  detailsModalOpen.value = true
}

onMounted(() => {
  loadUsers()
  loadLogs()
})
</script>
