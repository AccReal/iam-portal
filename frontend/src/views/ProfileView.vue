<template>
  <div>
    <a-typography-title :level="3">Профиль</a-typography-title>

    <a-row :gutter="24">
      <!-- Левая колонка: информация о пользователе -->
      <a-col :xs="24" :lg="10">
        <a-card title="Информация о пользователе" style="margin-bottom: 24px">
          <a-skeleton v-if="loading" active />
          <template v-else-if="profile">
            <div style="text-align: center; margin-bottom: 24px">
              <a-avatar :size="96" style="background-color: #1890ff; font-size: 36px">
                {{ initials }}
              </a-avatar>
              <div style="margin-top: 12px; font-size: 18px; font-weight: 600">
                {{ profile.full_name }}
              </div>
              <a-tag :color="roleColor" style="margin-top: 4px">{{ roleLabel }}</a-tag>
            </div>

            <a-descriptions bordered :column="1" size="small">
              <a-descriptions-item label="Email">{{ profile.email }}</a-descriptions-item>
              <a-descriptions-item label="Телефон">{{ profile.phone || '—' }}</a-descriptions-item>
              <a-descriptions-item label="Статус">
                <a-tag :color="profile.is_active && !profile.is_blocked ? 'green' : 'red'">
                  {{ profile.is_blocked ? 'Заблокирован' : (profile.is_active ? 'Активен' : 'Неактивен') }}
                </a-tag>
              </a-descriptions-item>
              <a-descriptions-item label="MFA">
                <a-tag :color="profile.mfa_enabled ? 'green' : 'default'">
                  {{ profile.mfa_enabled ? 'Включена' : 'Отключена' }}
                </a-tag>
              </a-descriptions-item>
              <a-descriptions-item label="Регистрация">
                {{ formatDate(profile.created_at) }}
              </a-descriptions-item>
            </a-descriptions>
          </template>
        </a-card>
      </a-col>

      <!-- Правая колонка: действия -->
      <a-col :xs="24" :lg="14">
        <!-- Смена пароля -->
        <a-card title="Смена пароля" style="margin-bottom: 24px">
          <a-form layout="vertical" @finish="onChangePassword">
            <a-form-item label="Текущий пароль" required>
              <a-input-password v-model:value="pwdForm.old_password" placeholder="Введите текущий пароль" />
            </a-form-item>

            <a-form-item label="Новый пароль" required>
              <a-input-password
                v-model:value="pwdForm.new_password"
                placeholder="Введите новый пароль"
                @input="onNewPasswordInput"
              />
            </a-form-item>

            <div v-if="pwdValidation" style="margin-bottom: 16px">
              <div style="display: flex; justify-content: space-between; margin-bottom: 4px; font-size: 12px">
                <span>Надёжность:</span>
                <span :style="{ fontWeight: 'bold', color: strengthColor }">
                  {{ pwdValidation.strength }}
                </span>
              </div>
              <a-progress :percent="pwdValidation.score" :stroke-color="strengthColor" :show-info="false" size="small" />
              <div v-if="pwdValidation.feedback.length" style="margin-top: 8px; font-size: 12px; color: #666">
                <div v-for="(fb, i) in pwdValidation.feedback" :key="i">• {{ fb }}</div>
              </div>
            </div>

            <a-form-item label="Подтверждение нового пароля" required>
              <a-input-password
                v-model:value="pwdForm.confirm_password"
                placeholder="Повторите новый пароль"
              />
              <div v-if="pwdForm.confirm_password && pwdForm.confirm_password !== pwdForm.new_password"
                   style="color: #ff4d4f; font-size: 12px; margin-top: 4px">
                Пароли не совпадают
              </div>
            </a-form-item>

            <a-button type="primary" html-type="submit" :loading="changingPassword" :disabled="!canChangePassword">
              Сменить пароль
            </a-button>
            <a-button style="margin-left: 8px" @click="generateSuggestion" :loading="generating">
              Сгенерировать надёжный
            </a-button>
          </a-form>

          <a-alert
            v-if="suggestedPassword"
            type="info"
            show-icon
            style="margin-top: 16px"
          >
            <template #message>
              Сгенерированный пароль:
              <a-typography-text code copyable>{{ suggestedPassword }}</a-typography-text>
            </template>
          </a-alert>
        </a-card>

        <!-- MFA -->
        <a-card title="Многофакторная аутентификация (MFA)">

          <!-- MFA not enabled, no active setup -->
          <template v-if="!profile?.mfa_enabled && mfaStep === 'idle'">
            <a-alert type="warning" show-icon style="margin-bottom: 16px">
              <template #message>MFA отключена</template>
              <template #description>
                Включите TOTP для защиты аккаунта. Вам понадобится Google Authenticator, Яндекс.Ключ или Authy.
              </template>
            </a-alert>
            <a-button type="primary" :loading="settingUpMfa" @click="onSetupMfa">
              Настроить MFA (TOTP)
            </a-button>
          </template>

          <!-- Step 1: scan QR -->
          <template v-else-if="mfaStep === 'qr' && mfaSetup">
            <a-alert type="info" show-icon style="margin-bottom: 16px">
              <template #message>Шаг 1 из 2 — Отсканируйте QR-код</template>
              <template #description>
                Откройте приложение-аутентификатор и отсканируйте код. Затем нажмите «Далее».
              </template>
            </a-alert>

            <div style="text-align: center; margin-bottom: 16px">
              <img :src="`data:image/png;base64,${mfaSetup.qr_image}`" alt="QR code"
                   style="width: 200px; height: 200px; border: 1px solid #f0f0f0; border-radius: 8px" />
            </div>

            <a-descriptions bordered :column="1" size="small" style="margin-bottom: 16px">
              <a-descriptions-item label="Секрет">
                <a-typography-text code copyable>{{ mfaSetup.secret }}</a-typography-text>
              </a-descriptions-item>
              <a-descriptions-item label="Метод">TOTP · 30 сек · 6 цифр</a-descriptions-item>
            </a-descriptions>

            <a-space>
              <a-button type="primary" @click="mfaStep = 'confirm'">Далее — ввести код</a-button>
              <a-button @click="cancelMfaSetup">Отмена</a-button>
            </a-space>
          </template>

          <!-- Step 2: verify code -->
          <template v-else-if="mfaStep === 'confirm'">
            <a-alert type="info" show-icon style="margin-bottom: 16px">
              <template #message>Шаг 2 из 2 — Введите код из приложения</template>
              <template #description>Подтвердите, что QR-код добавлен корректно.</template>
            </a-alert>

            <a-form @finish="onConfirmMfa" layout="vertical" :disabled="confirmingMfa">
              <a-form-item label="Код подтверждения (6 цифр)">
                <a-input
                  v-model:value="mfaConfirmCode"
                  placeholder="000000"
                  :maxlength="6"
                  size="large"
                  style="letter-spacing: 4px; font-size: 20px; width: 160px"
                />
              </a-form-item>
              <a-space>
                <a-button type="primary" html-type="submit" :loading="confirmingMfa"
                          :disabled="mfaConfirmCode.length !== 6">
                  Подтвердить и включить
                </a-button>
                <a-button @click="mfaStep = 'qr'">Назад</a-button>
              </a-space>
            </a-form>

            <a-alert v-if="mfaConfirmError" :message="mfaConfirmError" type="error" show-icon
                     closable style="margin-top: 12px" @close="mfaConfirmError = ''" />
          </template>

          <!-- MFA enabled -->
          <template v-else-if="profile?.mfa_enabled">
            <a-alert type="success" show-icon style="margin-bottom: 16px">
              <template #message>MFA включена (TOTP)</template>
              <template #description>
                Ваш аккаунт защищён двухфакторной аутентификацией.
              </template>
            </a-alert>

            <a-space wrap>
              <a-button :loading="settingUpMfa" @click="onSetupMfa">
                Переконфигурировать
              </a-button>

              <!-- Disable MFA — show code input -->
              <a-button v-if="!showDisableForm" danger @click="showDisableForm = true">
                Отключить MFA
              </a-button>
            </a-space>

            <!-- Disable form: requires TOTP code -->
            <div v-if="showDisableForm" style="margin-top: 16px; display: flex; align-items: center; gap: 12px; flex-wrap: wrap">
              <span style="font-size: 13px; color: #374151">Код из приложения:</span>
              <a-input
                v-model:value="disableCode"
                placeholder="000000"
                :maxlength="6"
                :disabled="disablingMfa"
                style="width: 120px; letter-spacing: 3px; font-size: 16px"
                @pressEnter="disableCode.length === 6 && onDisableMfa()"
              />
              <a-button
                danger
                :loading="disablingMfa"
                :disabled="disableCode.length !== 6 || disablingMfa"
                @click="onDisableMfa"
              >
                Подтвердить отключение
              </a-button>
              <a-button :disabled="disablingMfa" @click="showDisableForm = false; disableCode = ''; disableMfaError = ''">
                Отмена
              </a-button>
            </div>
            <a-alert v-if="disableMfaError" :message="disableMfaError" type="error" show-icon
                     closable style="margin-top: 12px" @close="disableMfaError = ''" />
          </template>

        </a-card>
      </a-col>
    </a-row>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { usersApi } from '@/api/users'
import { passwordApi } from '@/api/password'
import { useAuthStore } from '@/stores/auth'

interface Profile {
  id: string
  email: string
  full_name: string
  phone?: string
  role?: string
  mfa_enabled: boolean
  mfa_method?: string
  is_active: boolean
  is_blocked: boolean
  created_at: string
}

const authStore = useAuthStore()

const profile = ref<Profile | null>(null)
const loading = ref(true)

const pwdForm = ref({ old_password: '', new_password: '', confirm_password: '' })
const pwdValidation = ref<any>(null)
const changingPassword = ref(false)
const suggestedPassword = ref('')
const generating = ref(false)
let pwdTimer: ReturnType<typeof setTimeout> | null = null

const mfaSetup = ref<{ secret: string; qr_image: string; qr_uri: string } | null>(null)
const mfaStep = ref<'idle' | 'qr' | 'confirm'>('idle')
const mfaConfirmCode = ref('')
const mfaConfirmError = ref('')
const settingUpMfa = ref(false)
const confirmingMfa = ref(false)
const disablingMfa = ref(false)
const showDisableForm = ref(false)
const disableCode = ref('')
const disableMfaError = ref('')

const initials = computed(() => {
  if (!profile.value?.full_name) return '?'
  const parts = profile.value.full_name.trim().split(/\s+/)
  return parts.slice(0, 2).map(p => p[0]?.toUpperCase() || '').join('')
})

const roleLabel = computed(() => {
  const map: Record<string, string> = {
    admin: 'Администратор',
    manager: 'Менеджер',
    accountant: 'Бухгалтер',
    user: 'Пользователь',
  }
  return map[profile.value?.role || ''] || profile.value?.role || '—'
})

const roleColor = computed(() => {
  const map: Record<string, string> = {
    admin: 'red', manager: 'blue', accountant: 'gold', user: 'default',
  }
  return map[profile.value?.role || ''] || 'default'
})

const strengthColor = computed(() => {
  if (!pwdValidation.value) return '#d9d9d9'
  const level = pwdValidation.value.strength_level
  return ['#ff4d4f', '#fa8c16', '#fadb14', '#52c41a', '#1890ff'][level] || '#d9d9d9'
})

const canChangePassword = computed(() => {
  return pwdForm.value.old_password &&
         pwdForm.value.new_password &&
         pwdForm.value.new_password === pwdForm.value.confirm_password &&
         (pwdValidation.value?.score ?? 0) >= 40
})

function formatDate(iso: string) {
  if (!iso) return '—'
  return new Date(iso).toLocaleDateString('ru-RU', {
    year: 'numeric', month: 'long', day: 'numeric',
  })
}

async function loadProfile() {
  loading.value = true
  try {
    const { data } = await usersApi.getMe()
    profile.value = data
    authStore.setUser({
      id: data.id, email: data.email, full_name: data.full_name,
      role: data.role, mfa_enabled: data.mfa_enabled,
    })
  } catch (e: any) {
    message.error('Не удалось загрузить профиль')
  } finally {
    loading.value = false
  }
}

function onNewPasswordInput() {
  if (pwdTimer) clearTimeout(pwdTimer)
  if (!pwdForm.value.new_password) {
    pwdValidation.value = null
    return
  }
  pwdTimer = setTimeout(async () => {
    try {
      const { data } = await passwordApi.validate(pwdForm.value.new_password)
      pwdValidation.value = data
    } catch {
      pwdValidation.value = null
    }
  }, 350)
}

async function onChangePassword() {
  if (!canChangePassword.value) return
  changingPassword.value = true
  try {
    await usersApi.changePassword(pwdForm.value.old_password, pwdForm.value.new_password)
    message.success('Пароль успешно изменён')
    pwdForm.value = { old_password: '', new_password: '', confirm_password: '' }
    pwdValidation.value = null
    suggestedPassword.value = ''
  } catch (e: any) {
    message.error(e.response?.data?.detail || 'Ошибка при смене пароля')
  } finally {
    changingPassword.value = false
  }
}

async function generateSuggestion() {
  generating.value = true
  try {
    const { data } = await passwordApi.generate({
      length: 16,
      include_uppercase: true,
      include_digits: true,
      include_special: true,
      exclude_similar: true,
      count: 1,
    })
    suggestedPassword.value = data.passwords[0]
    pwdForm.value.new_password = suggestedPassword.value
    pwdForm.value.confirm_password = suggestedPassword.value
    onNewPasswordInput()
  } catch (e: any) {
    message.error('Не удалось сгенерировать пароль')
  } finally {
    generating.value = false
  }
}

async function onSetupMfa() {
  settingUpMfa.value = true
  try {
    const { data } = await usersApi.setupMfa()
    mfaSetup.value = data
    mfaStep.value = 'qr'
    mfaConfirmCode.value = ''
    mfaConfirmError.value = ''
  } catch (e: any) {
    message.error(e.response?.data?.detail || 'Ошибка настройки MFA')
  } finally {
    settingUpMfa.value = false
  }
}

function cancelMfaSetup() {
  mfaStep.value = 'idle'
  mfaSetup.value = null
  mfaConfirmCode.value = ''
  mfaConfirmError.value = ''
}

async function onConfirmMfa() {
  if (mfaConfirmCode.value.length !== 6) return
  confirmingMfa.value = true
  mfaConfirmError.value = ''
  try {
    await usersApi.confirmMfa(mfaConfirmCode.value)
    if (profile.value) {
      profile.value.mfa_enabled = true
      profile.value.mfa_method = 'totp'
    }
    mfaStep.value = 'idle'
    mfaSetup.value = null
    mfaConfirmCode.value = ''
    message.success('MFA успешно включена')
  } catch (e: any) {
    mfaConfirmError.value = e.response?.data?.detail || 'Неверный код. Попробуйте снова.'
    mfaConfirmCode.value = ''
  } finally {
    confirmingMfa.value = false
  }
}

async function onDisableMfa() {
  disablingMfa.value = true
  disableMfaError.value = ''
  try {
    await usersApi.disableMfaWithCode(disableCode.value)
    if (profile.value) {
      profile.value.mfa_enabled = false
      profile.value.mfa_method = undefined
    }
    showDisableForm.value = false
    disableCode.value = ''
    mfaSetup.value = null
    message.success('MFA успешно отключена')
  } catch (e: any) {
    const status = e.response?.status
    const detail = e.response?.data?.detail || 'Ошибка отключения MFA'
    disableMfaError.value = detail
    if (status === 422) {
      disableMfaError.value = detail // wrong TOTP code
    } else if (status === 403) {
      disableMfaError.value = detail // policy: MFA required
    } else if (status === 401) {
      disableMfaError.value = 'Сессия истекла. Обновите страницу и войдите заново.'
    } else {
      disableMfaError.value = detail
    }
  } finally {
    disablingMfa.value = false
  }
}

onMounted(loadProfile)
</script>
