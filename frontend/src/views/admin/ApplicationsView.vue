<template>
  <div>
    <a-typography-title :level="3">Управление приложениями</a-typography-title>

    <a-card>
      <!-- Панель инструментов -->
      <a-row :gutter="16" style="margin-bottom: 16px" align="middle">
        <a-col :xs="24" :sm="12" :md="10" :lg="8">
          <a-select
            v-model:value="filterType"
            placeholder="Все типы"
            style="width: 100%"
            @change="onFilterChange"
          >
            <a-select-option value="">Все типы</a-select-option>
            <a-select-option value="oauth">OAuth 2.0</a-select-option>
            <a-select-option value="saml">SAML</a-select-option>
            <a-select-option value="vault">Vault</a-select-option>
          </a-select>
        </a-col>
        <a-col :xs="24" :sm="12" :md="14" :lg="16" style="text-align: right">
          <a-space>
            <a-button @click="loadApplications" :loading="loading">
              <template #icon><ReloadOutlined /></template>
              Обновить
            </a-button>
            <a-button type="primary" @click="openCreate">
              <template #icon><PlusOutlined /></template>
              Добавить приложение
            </a-button>
          </a-space>
        </a-col>
      </a-row>

      <!-- Список приложений (карточки) -->
      <a-spin :spinning="loading">
        <a-row :gutter="[16, 16]">
          <a-col
            v-for="app in filteredApplications"
            :key="app.id"
            :xs="24"
            :sm="24"
            :md="12"
            :lg="8"
            :xl="6"
          >
            <a-card
              :hoverable="true"
              :class="{ 'app-card-inactive': !app.is_active }"
            >
              <template #title>
                <a-space>
                  <span v-if="app.icon">{{ app.icon }}</span>
                  <span v-else>🌐</span>
                  <span>{{ app.name }}</span>
                </a-space>
              </template>
              <template #extra>
                <a-tag :color="getTypeColor(app.integration_type)">
                  {{ getTypeLabel(app.integration_type) }}
                </a-tag>
              </template>

              <div style="min-height: 80px">
                <p style="color: #666; margin-bottom: 8px">
                  {{ app.description || 'Нет описания' }}
                </p>
                <p v-if="app.app_url" style="font-size: 12px; color: #999; margin-bottom: 8px">
                  <LinkOutlined /> {{ app.app_url }}
                </p>
                <p style="margin-bottom: 8px">
                  <a-tag :color="app.is_active ? 'green' : 'default'">
                    {{ app.is_active ? '✅ Активно' : '⏸️ Неактивно' }}
                  </a-tag>
                  <a-tag v-if="app.is_honeypot" color="orange">
                    🍯 Honeypot
                  </a-tag>
                </p>
              </div>

              <template #actions>
                <a-tooltip title="Редактировать">
                  <EditOutlined @click="openEdit(app)" />
                </a-tooltip>
                <a-tooltip v-if="app.integration_type === 'vault'" title="Управление учётными данными">
                  <KeyOutlined @click="openVaultCredentials(app)" />
                </a-tooltip>
                <a-tooltip :title="app.is_active ? 'Деактивировать' : 'Активировать'">
                  <a-popconfirm
                    :title="`${app.is_active ? 'Деактивировать' : 'Активировать'} ${app.name}?`"
                    @confirm="toggleActive(app)"
                  >
                    <PoweroffOutlined v-if="app.is_active" style="color: #ff4d4f" />
                    <CheckCircleOutlined v-else style="color: #52c41a" />
                  </a-popconfirm>
                </a-tooltip>
                <a-tooltip title="Удалить">
                  <a-popconfirm
                    :title="`Удалить ${app.name}?`"
                    @confirm="deleteApp(app)"
                  >
                    <DeleteOutlined style="color: #ff4d4f" />
                  </a-popconfirm>
                </a-tooltip>
              </template>
            </a-card>
          </a-col>
        </a-row>

        <a-empty v-if="!loading && filteredApplications.length === 0" description="Нет приложений" />
      </a-spin>

      <!-- Пагинация -->
      <div v-if="total > perPage" style="margin-top: 16px; text-align: right">
        <a-pagination
          v-model:current="page"
          v-model:page-size="perPage"
          :total="total"
          :page-size-options="['12', '24', '48']"
          show-size-changer
          :show-total="(t: number) => `Всего: ${t}`"
          @change="loadApplications"
          @show-size-change="onPageSizeChange"
        />
      </div>
    </a-card>

    <!-- Модалка создания/редактирования -->
    <a-modal
      v-model:open="modalOpen"
      :title="editingId ? 'Редактировать приложение' : 'Создать приложение'"
      :confirm-loading="saving"
      :ok-text="editingId ? 'Сохранить' : 'Создать'"
      cancel-text="Отмена"
      @ok="onSave"
      :destroy-on-close="true"
      width="600px"
    >
      <a-form layout="vertical" :model="form">
        <a-form-item label="Название" required>
          <a-input v-model:value="form.name" placeholder="CRM System" />
        </a-form-item>

        <a-form-item label="Описание">
          <a-textarea
            v-model:value="form.description"
            placeholder="Система управления клиентами"
            :rows="3"
          />
        </a-form-item>

        <a-form-item label="URL приложения">
          <a-input v-model:value="form.app_url" placeholder="https://crm.company.ru" />
        </a-form-item>

        <a-form-item label="Иконка (emoji)">
          <a-input v-model:value="form.icon" placeholder="🌐" maxlength="2" />
        </a-form-item>

        <a-form-item label="Тип интеграции" required>
          <a-select
            v-model:value="form.integration_type"
            placeholder="Выберите тип"
            :disabled="!!editingId"
          >
            <a-select-option value="oauth">OAuth 2.0</a-select-option>
            <a-select-option value="saml">SAML</a-select-option>
            <a-select-option value="vault">Vault (хранилище паролей)</a-select-option>
          </a-select>
          <div style="font-size: 12px; color: #999; margin-top: 4px">
            OAuth/SAML — для SSO интеграции. Vault — для хранения учётных данных.
          </div>
        </a-form-item>

        <a-form-item
          v-if="form.integration_type === 'oauth'"
          label="Redirect URIs"
        >
          <a-select
            v-model:value="form.redirect_uris"
            mode="tags"
            placeholder="https://app.example.com/callback"
            style="width: 100%"
          />
          <div style="font-size: 12px; color: #999; margin-top: 4px">
            Разрешённые URL для перенаправления после авторизации
          </div>
        </a-form-item>

        <a-form-item v-if="editingId">
          <a-checkbox v-model:checked="form.is_active">
            Приложение активно
          </a-checkbox>
        </a-form-item>

        <a-form-item>
          <a-checkbox v-model:checked="form.is_honeypot">
            Honeypot (ловушка для обнаружения атак)
          </a-checkbox>
        </a-form-item>
      </a-form>
    </a-modal>

    <!-- Модалка с OAuth credentials -->
    <a-modal
      v-model:open="credentialsModalOpen"
      title="OAuth учётные данные"
      :footer="null"
      width="600px"
    >
      <a-alert type="success" show-icon style="margin-bottom: 16px">
        <template #message>Приложение создано</template>
        <template #description>
          Сохраните client_secret — он показывается только один раз.
        </template>
      </a-alert>

      <a-descriptions bordered :column="1">
        <a-descriptions-item label="Client ID">
          <a-typography-text copyable>{{ newCredentials.client_id }}</a-typography-text>
        </a-descriptions-item>
        <a-descriptions-item label="Client Secret">
          <a-typography-text copyable code>{{ newCredentials.client_secret }}</a-typography-text>
        </a-descriptions-item>
      </a-descriptions>

      <div style="margin-top: 16px; text-align: right">
        <a-button type="primary" @click="credentialsModalOpen = false">
          Закрыть
        </a-button>
      </div>
    </a-modal>

    <!-- Модалка управления vault credentials -->
    <a-modal
      v-model:open="vaultModalOpen"
      :title="`Учётные данные: ${currentVaultApp?.name || ''}`"
      :footer="null"
      width="800px"
    >
      <a-alert type="info" show-icon style="margin-bottom: 16px">
        <template #message>Управление учётными данными</template>
        <template #description>
          Здесь отображаются сохранённые учётные данные пользователей для этого приложения.
          Учётные данные шифруются с помощью AES-256-GCM.
        </template>
      </a-alert>

      <a-table
        :columns="vaultColumns"
        :data-source="vaultCredentials"
        :loading="loadingVault"
        :pagination="false"
        size="small"
        row-key="id"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'created_at'">
            {{ formatDate(record.created_at) }}
          </template>
          <template v-else-if="column.key === 'actions'">
            <a-popconfirm
              title="Удалить учётные данные?"
              @confirm="deleteVaultCredential(record)"
            >
              <a-button size="small" type="link" danger>
                <template #icon><DeleteOutlined /></template>
              </a-button>
            </a-popconfirm>
          </template>
        </template>
      </a-table>

      <a-empty v-if="!loadingVault && vaultCredentials.length === 0" description="Нет сохранённых учётных данных" />

      <div style="margin-top: 16px; text-align: right">
        <a-button @click="vaultModalOpen = false">
          Закрыть
        </a-button>
      </div>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { message } from 'ant-design-vue'
import {
  PlusOutlined, ReloadOutlined, EditOutlined, DeleteOutlined,
  PoweroffOutlined, CheckCircleOutlined, LinkOutlined, KeyOutlined,
} from '@ant-design/icons-vue'
import { applicationsApi } from '@/api/applications'

interface Application {
  id: string
  name: string
  description: string | null
  app_url: string | null
  icon: string | null
  integration_type: 'oauth' | 'saml' | 'vault'
  client_id: string | null
  is_active: boolean
  is_honeypot: boolean
  created_at: string
}

interface VaultCredential {
  id: string
  user_id: string
  user_email: string
  user_name: string
  created_at: string
}

const applications = ref<Application[]>([])
const loading = ref(false)
const total = ref(0)
const page = ref(1)
const perPage = ref(12)
const filterType = ref('')

const modalOpen = ref(false)
const saving = ref(false)
const editingId = ref<string | null>(null)
const form = ref<any>({
  name: '',
  description: '',
  app_url: '',
  icon: '',
  integration_type: '',
  redirect_uris: [],
  is_active: true,
  is_honeypot: false,
})

const credentialsModalOpen = ref(false)
const newCredentials = ref<any>({
  client_id: '',
  client_secret: '',
})

const vaultModalOpen = ref(false)
const loadingVault = ref(false)
const currentVaultApp = ref<Application | null>(null)
const vaultCredentials = ref<VaultCredential[]>([])

const vaultColumns = [
  { title: 'Пользователь', key: 'user_name', dataIndex: 'user_name' },
  { title: 'Email', key: 'user_email', dataIndex: 'user_email' },
  { title: 'Создано', key: 'created_at', dataIndex: 'created_at' },
  { title: 'Действия', key: 'actions', width: 100, align: 'center' as const },
]

const filteredApplications = computed(() => {
  if (!filterType.value) return applications.value
  return applications.value.filter(app => app.integration_type === filterType.value)
})

function getTypeLabel(type: string) {
  const labels: Record<string, string> = {
    oauth: 'OAuth 2.0',
    saml: 'SAML',
    vault: 'Vault',
  }
  return labels[type] || type
}

function getTypeColor(type: string) {
  const colors: Record<string, string> = {
    oauth: 'blue',
    saml: 'purple',
    vault: 'green',
  }
  return colors[type] || 'default'
}

function formatDate(iso: string) {
  if (!iso) return '—'
  return new Date(iso).toLocaleDateString('ru-RU')
}

async function loadApplications() {
  loading.value = true
  try {
    const { data } = await applicationsApi.list(page.value, perPage.value)
    applications.value = data.applications
    total.value = data.total
  } catch (e: any) {
    message.error(e.response?.data?.detail || 'Не удалось загрузить приложения')
  } finally {
    loading.value = false
  }
}

function onFilterChange() {
  // Filter is applied via computed property
}

function onPageSizeChange(_cur: number, size: number) {
  perPage.value = size
  page.value = 1
  loadApplications()
}

function openCreate() {
  editingId.value = null
  form.value = {
    name: '',
    description: '',
    app_url: '',
    icon: '',
    integration_type: '',
    redirect_uris: [],
    is_active: true,
    is_honeypot: false,
  }
  modalOpen.value = true
}

function openEdit(app: Application) {
  editingId.value = app.id
  form.value = {
    name: app.name,
    description: app.description || '',
    app_url: app.app_url || '',
    icon: app.icon || '',
    integration_type: app.integration_type,
    redirect_uris: [],
    is_active: app.is_active,
    is_honeypot: app.is_honeypot,
  }
  modalOpen.value = true
}

async function onSave() {
  if (!form.value.name || !form.value.name.trim()) {
    message.warning('Введите название приложения')
    return
  }
  if (!form.value.integration_type) {
    message.warning('Выберите тип интеграции')
    return
  }

  saving.value = true
  try {
    const payload: any = {
      name: form.value.name,
      description: form.value.description || undefined,
      app_url: form.value.app_url || undefined,
      icon: form.value.icon || undefined,
      integration_type: form.value.integration_type,
      is_honeypot: form.value.is_honeypot,
    }

    if (form.value.integration_type === 'oauth' && form.value.redirect_uris?.length > 0) {
      payload.redirect_uris = form.value.redirect_uris
    }

    if (editingId.value) {
      payload.is_active = form.value.is_active
      await applicationsApi.update(editingId.value, payload)
      message.success('Приложение обновлено')
    } else {
      const { data } = await applicationsApi.create(payload)
      message.success('Приложение создано')

      // Show credentials if OAuth/SAML
      if (data.client_secret) {
        newCredentials.value = {
          client_id: data.client_id,
          client_secret: data.client_secret,
        }
        credentialsModalOpen.value = true
      }
    }

    modalOpen.value = false
    await loadApplications()
  } catch (e: any) {
    message.error(e.response?.data?.detail || 'Ошибка сохранения')
  } finally {
    saving.value = false
  }
}

async function toggleActive(app: Application) {
  try {
    await applicationsApi.toggleActive(app.id, !app.is_active)
    message.success(`${app.name} ${!app.is_active ? 'активировано' : 'деактивировано'}`)
    await loadApplications()
  } catch (e: any) {
    message.error(e.response?.data?.detail || 'Ошибка операции')
  }
}

async function deleteApp(app: Application) {
  try {
    await applicationsApi.delete(app.id)
    message.success(`${app.name} удалено`)
    await loadApplications()
  } catch (e: any) {
    message.error(e.response?.data?.detail || 'Ошибка удаления')
  }
}

async function openVaultCredentials(app: Application) {
  currentVaultApp.value = app
  vaultModalOpen.value = true
  await loadVaultCredentials(app.id)
}

async function loadVaultCredentials(appId: string) {
  loadingVault.value = true
  try {
    // Note: This is a placeholder. The actual API endpoint for listing
    // vault credentials by application doesn't exist yet in the backend.
    // In a real implementation, you would call something like:
    // const { data } = await applicationsApi.getVaultCredentials(appId)
    // vaultCredentials.value = data.credentials
    
    // For now, show empty list
    vaultCredentials.value = []
    message.info('API для управления vault credentials ещё не реализован в бэкенде')
  } catch (e: any) {
    message.error(e.response?.data?.detail || 'Не удалось загрузить учётные данные')
  } finally {
    loadingVault.value = false
  }
}

async function deleteVaultCredential(credential: VaultCredential) {
  try {
    // Placeholder for delete credential API call
    message.info('API для удаления vault credentials ещё не реализован в бэкенде')
    await loadVaultCredentials(currentVaultApp.value!.id)
  } catch (e: any) {
    message.error(e.response?.data?.detail || 'Ошибка удаления')
  }
}

onMounted(() => {
  loadApplications()
})
</script>

<style scoped>
.app-card-inactive {
  opacity: 0.6;
}

:deep(.ant-card-actions) {
  background: #fafafa;
}

:deep(.ant-card-actions > li) {
  margin: 8px 0;
}

:deep(.ant-card-actions > li > span) {
  font-size: 18px;
  cursor: pointer;
  transition: all 0.3s;
}

:deep(.ant-card-actions > li > span:hover) {
  color: #1890ff;
}
</style>
