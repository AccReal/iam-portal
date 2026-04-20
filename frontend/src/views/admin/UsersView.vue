<template>
  <div>
    <a-typography-title :level="3">Управление пользователями</a-typography-title>

    <a-card>
      <!-- Панель инструментов -->
      <a-row :gutter="16" style="margin-bottom: 16px" align="middle">
        <a-col :xs="24" :sm="12" :md="10" :lg="8">
          <a-input-search
            v-model:value="searchQuery"
            placeholder="Поиск по имени, email, телефону..."
            allow-clear
            enter-button
            @search="onSearch"
          />
        </a-col>
        <a-col :xs="24" :sm="12" :md="14" :lg="16" style="text-align: right">
          <a-space>
            <a-button @click="loadUsers" :loading="loading">
              <template #icon><ReloadOutlined /></template>
              Обновить
            </a-button>
            <a-button type="primary" @click="openCreate">
              <template #icon><PlusOutlined /></template>
              Добавить пользователя
            </a-button>
          </a-space>
        </a-col>
      </a-row>

      <!-- Таблица -->
      <a-table
        :columns="columns"
        :data-source="users"
        :loading="loading"
        :pagination="false"
        row-key="id"
        size="middle"
        :scroll="{ x: 900 }"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'full_name'">
            <a-space>
              <a-avatar style="background-color: #1890ff">{{ initials(record.full_name) }}</a-avatar>
              <div>
                <div style="font-weight: 500">{{ record.full_name }}</div>
                <div style="font-size: 12px; color: #999">{{ record.email }}</div>
              </div>
            </a-space>
          </template>

          <template v-else-if="column.key === 'role'">
            <a-tag :color="roleColor(record.role)">{{ roleLabel(record.role) }}</a-tag>
          </template>

          <template v-else-if="column.key === 'status'">
            <a-tag v-if="record.is_blocked" color="red">Заблокирован</a-tag>
            <a-tag v-else-if="!record.is_active" color="default">Неактивен</a-tag>
            <a-tag v-else color="green">Активен</a-tag>
          </template>

          <template v-else-if="column.key === 'mfa_enabled'">
            <a-tag :color="record.mfa_enabled ? 'green' : 'default'">
              {{ record.mfa_enabled ? 'Вкл' : 'Выкл' }}
            </a-tag>
          </template>

          <template v-else-if="column.key === 'created_at'">
            {{ formatDate(record.created_at) }}
          </template>

          <template v-else-if="column.key === 'actions'">
            <a-space :size="4">
              <a-tooltip title="Редактировать">
                <a-button size="small" type="link" @click="openEdit(record)">
                  <template #icon><EditOutlined /></template>
                </a-button>
              </a-tooltip>

              <a-tooltip :title="record.is_blocked ? 'Разблокировать' : 'Заблокировать'">
                <a-popconfirm
                  :title="record.is_blocked
                    ? `Разблокировать ${record.full_name}?`
                    : `Заблокировать ${record.full_name}?`"
                  @confirm="toggleBlock(record)"
                >
                  <a-button size="small" type="link" :danger="!record.is_blocked">
                    <template #icon>
                      <UnlockOutlined v-if="record.is_blocked" />
                      <LockOutlined v-else />
                    </template>
                  </a-button>
                </a-popconfirm>
              </a-tooltip>

              <a-tooltip title="Сбросить пароль">
                <a-popconfirm
                  :title="`Сбросить пароль для ${record.full_name}?`"
                  @confirm="resetPassword(record)"
                >
                  <a-button size="small" type="link">
                    <template #icon><KeyOutlined /></template>
                  </a-button>
                </a-popconfirm>
              </a-tooltip>
            </a-space>
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
          @change="loadUsers"
          @show-size-change="onPageSizeChange"
        />
      </div>
    </a-card>

    <!-- Модалка создания/редактирования -->
    <a-modal
      v-model:open="modalOpen"
      :title="editingId ? 'Редактировать пользователя' : 'Создать пользователя'"
      :confirm-loading="saving"
      :ok-text="editingId ? 'Сохранить' : 'Создать'"
      cancel-text="Отмена"
      @ok="onSave"
      :destroy-on-close="true"
    >
      <a-form layout="vertical" :model="form">
        <a-form-item label="ФИО" required>
          <a-input v-model:value="form.full_name" placeholder="Иванов Иван Иванович" />
        </a-form-item>

        <a-form-item label="Email" required>
          <a-input
            v-model:value="form.email"
            placeholder="user@company.ru"
            :disabled="!!editingId"
          />
        </a-form-item>

        <a-form-item label="Телефон">
          <a-input v-model:value="form.phone" placeholder="+7 (999) 000-00-00" />
        </a-form-item>

        <a-form-item label="Роль">
          <a-select
            v-model:value="form.role_id"
            placeholder="Выберите роль"
            allow-clear
            :options="roleOptions"
          />
        </a-form-item>

        <a-form-item v-if="!editingId" label="Пароль">
          <a-input-password
            v-model:value="form.password"
            placeholder="Оставьте пустым — сгенерируется автоматически"
          />
          <div style="font-size: 12px; color: #999; margin-top: 4px">
            Если не указан, будет сгенерирован временный пароль.
          </div>
        </a-form-item>

        <a-form-item v-if="editingId" label="Статус">
          <a-switch v-model:checked="form.is_active" />
          <span style="margin-left: 8px">{{ form.is_active ? 'Активен' : 'Неактивен' }}</span>
        </a-form-item>
      </a-form>
    </a-modal>

    <!-- Модалка с временным паролем -->
    <a-modal
      v-model:open="pwdModalOpen"
      title="Временный пароль"
      :footer="null"
    >
      <a-alert type="success" show-icon style="margin-bottom: 16px">
        <template #message>{{ pwdModalMessage }}</template>
        <template #description>
          Сохраните пароль — он показывается один раз. Пользователю потребуется сменить его при первом входе.
        </template>
      </a-alert>
      <a-typography-text code copyable style="font-size: 16px">
        {{ tempPassword }}
      </a-typography-text>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { message } from 'ant-design-vue'
import {
  PlusOutlined, ReloadOutlined, EditOutlined, LockOutlined,
  UnlockOutlined, KeyOutlined,
} from '@ant-design/icons-vue'
import { usersApi } from '@/api/users'
import { rolesApi } from '@/api/roles'

interface UserRow {
  id: string
  email: string
  full_name: string
  phone?: string
  role?: string
  role_id?: string
  is_active: boolean
  is_blocked: boolean
  mfa_enabled: boolean
  created_at: string
}

interface RoleItem {
  id: string
  name: string
  description?: string
}

const users = ref<UserRow[]>([])
const roles = ref<RoleItem[]>([])
const loading = ref(false)
const total = ref(0)
const page = ref(1)
const perPage = ref(20)
const searchQuery = ref('')

const columns = [
  { title: 'Пользователь', key: 'full_name', dataIndex: 'full_name', width: 280 },
  { title: 'Телефон', key: 'phone', dataIndex: 'phone', width: 160 },
  { title: 'Роль', key: 'role', dataIndex: 'role', width: 140 },
  { title: 'Статус', key: 'status', width: 130 },
  { title: 'MFA', key: 'mfa_enabled', width: 80 },
  { title: 'Создан', key: 'created_at', dataIndex: 'created_at', width: 130 },
  { title: 'Действия', key: 'actions', width: 150, fixed: 'right' as const },
]

const modalOpen = ref(false)
const saving = ref(false)
const editingId = ref<string | null>(null)
const form = ref<any>({
  email: '', full_name: '', phone: '', role_id: undefined,
  password: '', is_active: true,
})

const pwdModalOpen = ref(false)
const tempPassword = ref('')
const pwdModalMessage = ref('')

const roleOptions = computed(() =>
  roles.value.map(r => ({ value: r.id, label: roleLabel(r.name) }))
)

function roleLabel(role?: string) {
  const map: Record<string, string> = {
    admin: 'Администратор',
    manager: 'Менеджер',
    accountant: 'Бухгалтер',
    user: 'Пользователь',
  }
  return map[role || ''] || role || '—'
}

function roleColor(role?: string) {
  const map: Record<string, string> = {
    admin: 'red', manager: 'blue', accountant: 'gold', user: 'default',
  }
  return map[role || ''] || 'default'
}

function initials(name: string) {
  if (!name) return '?'
  const parts = name.trim().split(/\s+/)
  return parts.slice(0, 2).map(p => p[0]?.toUpperCase() || '').join('')
}

function formatDate(iso: string) {
  if (!iso) return '—'
  return new Date(iso).toLocaleDateString('ru-RU')
}

async function loadUsers() {
  loading.value = true
  try {
    const { data } = await usersApi.list(page.value, perPage.value, searchQuery.value || undefined)
    users.value = data.users
    total.value = data.total
  } catch (e: any) {
    message.error(e.response?.data?.detail || 'Не удалось загрузить список пользователей')
  } finally {
    loading.value = false
  }
}

async function loadRoles() {
  try {
    const { data } = await rolesApi.list()
    roles.value = data.roles
  } catch {
    // silent
  }
}

function onSearch() {
  page.value = 1
  loadUsers()
}

function onPageSizeChange(_cur: number, size: number) {
  perPage.value = size
  page.value = 1
  loadUsers()
}

function openCreate() {
  editingId.value = null
  form.value = {
    email: '', full_name: '', phone: '', role_id: undefined,
    password: '', is_active: true,
  }
  modalOpen.value = true
}

function openEdit(row: UserRow) {
  editingId.value = row.id
  form.value = {
    email: row.email,
    full_name: row.full_name,
    phone: row.phone || '',
    role_id: row.role_id,
    is_active: row.is_active,
  }
  modalOpen.value = true
}

async function onSave() {
  if (!form.value.full_name || !form.value.email) {
    message.warning('Заполните ФИО и email')
    return
  }
  saving.value = true
  try {
    if (editingId.value) {
      await usersApi.update(editingId.value, {
        full_name: form.value.full_name,
        phone: form.value.phone || null,
        role_id: form.value.role_id || null,
        is_active: form.value.is_active,
      })
      message.success('Пользователь обновлён')
    } else {
      const { data } = await usersApi.create({
        email: form.value.email,
        full_name: form.value.full_name,
        phone: form.value.phone || undefined,
        role_id: form.value.role_id || undefined,
        password: form.value.password || undefined,
      })
      message.success('Пользователь создан')
      // бекенд пишет temp_password в audit.details; если пароль не задавали — уведомим через отдельный reset
      if (!form.value.password) {
        try {
          const r = await usersApi.resetPassword(data.id)
          tempPassword.value = r.data.temp_password
          pwdModalMessage.value = 'Пользователь создан. Временный пароль:'
          pwdModalOpen.value = true
        } catch { /* ignore */ }
      }
    }
    modalOpen.value = false
    await loadUsers()
  } catch (e: any) {
    message.error(e.response?.data?.detail || 'Ошибка сохранения')
  } finally {
    saving.value = false
  }
}

async function toggleBlock(row: UserRow) {
  try {
    if (row.is_blocked) {
      await usersApi.unblock(row.id)
      message.success(`${row.full_name} разблокирован`)
    } else {
      await usersApi.block(row.id)
      message.success(`${row.full_name} заблокирован`)
    }
    await loadUsers()
  } catch (e: any) {
    message.error(e.response?.data?.detail || 'Ошибка операции')
  }
}

async function resetPassword(row: UserRow) {
  try {
    const { data } = await usersApi.resetPassword(row.id)
    tempPassword.value = data.temp_password
    pwdModalMessage.value = `Пароль сброшен для ${row.full_name}:`
    pwdModalOpen.value = true
  } catch (e: any) {
    message.error(e.response?.data?.detail || 'Не удалось сбросить пароль')
  }
}

onMounted(() => {
  loadRoles()
  loadUsers()
})
</script>
