<template>
  <div>
    <a-typography-title :level="3">Управление ролями</a-typography-title>

    <a-card>
      <!-- Панель инструментов -->
      <a-row :gutter="16" style="margin-bottom: 16px" align="middle">
        <a-col :xs="24" :sm="12" :md="16" :lg="18">
          <a-space :wrap="true">
            <a-button @click="loadRoles" :loading="loading">
              <template #icon><ReloadOutlined /></template>
              Обновить
            </a-button>
          </a-space>
        </a-col>
        <a-col :xs="24" :sm="12" :md="8" :lg="6" style="text-align: right">
          <a-button type="primary" @click="openCreate" class="mobile-full-width">
            <template #icon><PlusOutlined /></template>
            Создать роль
          </a-button>
        </a-col>
      </a-row>

      <!-- Таблица ролей -->
      <a-table
        :columns="columns"
        :data-source="roles"
        :loading="loading"
        :pagination="false"
        row-key="id"
        size="middle"
        :scroll="{ x: 'max-content' }"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'name'">
            <a-space>
              <a-tag :color="getRoleColor(record.name)">{{ record.name }}</a-tag>
              <span style="font-weight: 500">{{ record.description || '—' }}</span>
            </a-space>
          </template>

          <template v-else-if="column.key === 'user_count'">
            <a-badge :count="record.user_count" :number-style="{ backgroundColor: '#52c41a' }" />
          </template>

          <template v-else-if="column.key === 'actions'">
            <a-space :size="4">
              <a-tooltip title="Редактировать">
                <a-button size="small" type="link" @click="openEdit(record)">
                  <template #icon><EditOutlined /></template>
                </a-button>
              </a-tooltip>

              <a-tooltip title="Управление правами">
                <a-button size="small" type="link" @click="openPermissions(record)">
                  <template #icon><SafetyOutlined /></template>
                </a-button>
              </a-tooltip>

              <a-tooltip title="Удалить">
                <a-popconfirm
                  :title="`Удалить роль ${record.name}?`"
                  :disabled="record.user_count > 0"
                  @confirm="deleteRole(record)"
                >
                  <a-button 
                    size="small" 
                    type="link" 
                    danger
                    :disabled="record.user_count > 0"
                  >
                    <template #icon><DeleteOutlined /></template>
                  </a-button>
                </a-popconfirm>
              </a-tooltip>
            </a-space>
          </template>
        </template>
      </a-table>
    </a-card>

    <!-- Модалка создания/редактирования роли -->
    <a-modal
      v-model:open="modalOpen"
      :title="editingId ? 'Редактировать роль' : 'Создать роль'"
      :confirm-loading="saving"
      :ok-text="editingId ? 'Сохранить' : 'Создать'"
      cancel-text="Отмена"
      @ok="onSave"
      :destroy-on-close="true"
    >
      <a-form layout="vertical" :model="form">
        <a-form-item label="Название роли" required>
          <a-input 
            v-model:value="form.name" 
            placeholder="manager" 
            :disabled="!!editingId"
          />
          <div style="font-size: 12px; color: #999; margin-top: 4px">
            Используйте латиницу в нижнем регистре (например: manager, accountant)
          </div>
        </a-form-item>

        <a-form-item label="Описание">
          <a-textarea
            v-model:value="form.description"
            placeholder="Менеджер с доступом к CRM"
            :rows="3"
          />
        </a-form-item>
      </a-form>
    </a-modal>

    <!-- Модалка управления правами -->
    <a-modal
      v-model:open="permissionsModalOpen"
      :title="`Права роли: ${currentRole?.name || ''}`"
      :confirm-loading="savingPermissions"
      ok-text="Сохранить"
      cancel-text="Отмена"
      @ok="onSavePermissions"
      :destroy-on-close="true"
      width="800px"
    >
      <a-spin :spinning="loadingPermissions">
        <div v-if="!loadingPermissions && permissionMatrix.length > 0">
          <a-alert
            message="Матрица прав доступа"
            description="Отметьте разрешения, которые должны быть у этой роли"
            type="info"
            show-icon
            style="margin-bottom: 16px"
          />

          <a-table
            :columns="permissionColumns"
            :data-source="permissionMatrix"
            :pagination="false"
            size="small"
            row-key="resource"
          >
            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'resource'">
                <strong>{{ record.resource }}</strong>
              </template>
              <template v-else-if="column.key !== 'resource'">
                <a-checkbox
                  v-model:checked="record[column.key]"
                  @change="onPermissionChange(record.resource, column.key, record[column.key])"
                />
              </template>
            </template>
          </a-table>
        </div>
        <a-empty v-else-if="!loadingPermissions" description="Нет доступных разрешений" />
      </a-spin>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import {
  PlusOutlined, ReloadOutlined, EditOutlined, DeleteOutlined, SafetyOutlined,
} from '@ant-design/icons-vue'
import { rolesApi } from '@/api/roles'
import { useErrorHandler } from '@/composables/useErrorHandler'
import { useLoading } from '@/composables/useLoading'

interface RoleRow {
  id: string
  name: string
  description: string | null
  user_count: number
  created_at: string
}

interface Permission {
  id: string
  resource: string
  action: string
  description: string | null
}

interface RolePermission {
  permission_id: string
  granted: boolean
}

interface PermissionMatrixRow {
  resource: string
  [action: string]: boolean | string
}

const roles = ref<RoleRow[]>([])
const allPermissions = ref<Permission[]>([])
const { loading, withLoading } = useLoading()
const { handleError, handleErrorWithRetry, showSuccess } = useErrorHandler()

const columns = [
  { title: 'Роль', key: 'name', dataIndex: 'name', width: '40%' },
  { title: 'Пользователей', key: 'user_count', dataIndex: 'user_count', width: '20%', align: 'center' as const },
  { title: 'Создана', key: 'created_at', dataIndex: 'created_at', width: '20%' },
  { title: 'Действия', key: 'actions', width: '20%', align: 'center' as const },
]

const modalOpen = ref(false)
const saving = ref(false)
const editingId = ref<string | null>(null)
const form = ref<any>({
  name: '',
  description: '',
})

const permissionsModalOpen = ref(false)
const loadingPermissions = ref(false)
const savingPermissions = ref(false)
const currentRole = ref<RoleRow | null>(null)
const rolePermissions = ref<RolePermission[]>([])
const permissionMatrix = ref<PermissionMatrixRow[]>([])
const permissionChanges = ref<Map<string, boolean>>(new Map())

const permissionColumns = ref([
  { title: 'Ресурс', key: 'resource', dataIndex: 'resource', width: 200 },
])

function getRoleColor(name: string) {
  const colorMap: Record<string, string> = {
    admin: 'red',
    manager: 'blue',
    accountant: 'gold',
    user: 'default',
  }
  return colorMap[name] || 'purple'
}

function formatDate(iso: string) {
  if (!iso) return '—'
  return new Date(iso).toLocaleDateString('ru-RU')
}

async function loadRoles() {
  await withLoading(async () => {
    const { data } = await rolesApi.list()
    roles.value = data.roles.map((r: any) => ({
      ...r,
      user_count: r.user_count || 0,
      created_at: formatDate(r.created_at),
    }))
  }, (error) => handleErrorWithRetry(error, loadRoles, 'Загрузка ролей'))
}

async function loadAllPermissions() {
  try {
    const { data } = await rolesApi.getAllPermissions()
    allPermissions.value = data.permissions || []
  } catch (error) {
    handleError(error, 'Загрузка разрешений')
  }
}

function openCreate() {
  editingId.value = null
  form.value = {
    name: '',
    description: '',
  }
  modalOpen.value = true
}

function openEdit(row: RoleRow) {
  editingId.value = row.id
  form.value = {
    name: row.name,
    description: row.description || '',
  }
  modalOpen.value = true
}

async function onSave() {
  if (!form.value.name || !form.value.name.trim()) {
    message.warning('Введите название роли')
    return
  }

  saving.value = true
  try {
    if (editingId.value) {
      await rolesApi.update(editingId.value, {
        name: form.value.name,
        description: form.value.description || undefined,
      })
      showSuccess('Роль обновлена')
    } else {
      await rolesApi.create({
        name: form.value.name,
        description: form.value.description || undefined,
      })
      showSuccess('Роль создана')
    }
    modalOpen.value = false
    await loadRoles()
  } catch (error) {
    handleError(error, 'Сохранение роли')
  } finally {
    saving.value = false
  }
}

async function deleteRole(row: RoleRow) {
  if (row.user_count > 0) {
    message.warning('Невозможно удалить роль с привязанными пользователями')
    return
  }

  try {
    await rolesApi.delete(row.id)
    showSuccess(`Роль ${row.name} удалена`)
    await loadRoles()
  } catch (error) {
    handleError(error, 'Удаление роли')
  }
}

async function openPermissions(row: RoleRow) {
  currentRole.value = row
  permissionChanges.value.clear()
  permissionsModalOpen.value = true
  await loadRolePermissions(row.id)
}

async function loadRolePermissions(roleId: string) {
  loadingPermissions.value = true
  try {
    // Load role permissions
    const { data } = await rolesApi.getPermissions(roleId)
    rolePermissions.value = data.permissions || []

    // Build permission matrix
    buildPermissionMatrix()
  } catch (error) {
    handleError(error, 'Загрузка прав роли')
  } finally {
    loadingPermissions.value = false
  }
}

function buildPermissionMatrix() {
  // Group permissions by resource
  const resourceMap = new Map<string, Map<string, { id: string; granted: boolean }>>()

  // Initialize with all available permissions
  allPermissions.value.forEach(perm => {
    if (!resourceMap.has(perm.resource)) {
      resourceMap.set(perm.resource, new Map())
    }
    resourceMap.get(perm.resource)!.set(perm.action, { id: perm.id, granted: false })
  })

  // Mark granted permissions
  rolePermissions.value.forEach(rp => {
    const perm = allPermissions.value.find(p => p.id === rp.permission_id)
    if (perm && resourceMap.has(perm.resource)) {
      const actions = resourceMap.get(perm.resource)!
      if (actions.has(perm.action)) {
        actions.get(perm.action)!.granted = rp.granted
      }
    }
  })

  // Build matrix rows
  const matrix: PermissionMatrixRow[] = []
  const actionsSet = new Set<string>()

  resourceMap.forEach((actions, resource) => {
    const row: PermissionMatrixRow = { resource }
    actions.forEach((data, action) => {
      row[action] = data.granted
      actionsSet.add(action)
    })
    matrix.push(row)
  })

  permissionMatrix.value = matrix

  // Build dynamic columns
  const actionsList = Array.from(actionsSet).sort()
  permissionColumns.value = [
    { title: 'Ресурс', key: 'resource', dataIndex: 'resource', width: 200 },
    ...actionsList.map(action => ({
      title: action.charAt(0).toUpperCase() + action.slice(1),
      key: action,
      dataIndex: action,
      width: 100,
      align: 'center' as const,
    })),
  ]
}

function onPermissionChange(resource: string, action: string, granted: boolean) {
  // Find the permission ID
  const perm = allPermissions.value.find(p => p.resource === resource && p.action === action)
  if (perm) {
    permissionChanges.value.set(perm.id, granted)
  }
}

async function onSavePermissions() {
  if (!currentRole.value) return

  savingPermissions.value = true
  try {
    // Build permissions array from changes
    const permissions: Array<{ permission_id: string; granted: boolean }> = []

    permissionChanges.value.forEach((granted, permissionId) => {
      permissions.push({ permission_id: permissionId, granted })
    })

    if (permissions.length === 0) {
      message.info('Нет изменений для сохранения')
      permissionsModalOpen.value = false
      return
    }

    await rolesApi.updatePermissions(currentRole.value.id, permissions)
    showSuccess('Права роли обновлены')
    permissionsModalOpen.value = false
  } catch (error) {
    handleError(error, 'Сохранение прав')
  } finally {
    savingPermissions.value = false
  }
}

onMounted(() => {
  loadAllPermissions()
  loadRoles()
})
</script>

<style scoped>
:deep(.ant-table-small) .ant-table-tbody > tr > td {
  padding: 8px;
}
</style>
