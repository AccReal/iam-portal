<template>
  <div class="login-page">
    <div class="login-container">
      <div class="login-header">
        <div class="logo-icon">
          <SafetyCertificateOutlined style="font-size: 48px; color: #1890ff" />
        </div>
        <h1 class="login-title">Портал доступа</h1>
        <p class="login-subtitle">Единая система управления доступом</p>
      </div>

      <a-card class="login-card" :bordered="false">
        <a-tabs v-model:activeKey="activeTab" centered>
          <a-tab-pane key="login" tab="Вход" />
          <a-tab-pane key="register" tab="Регистрация" />
        </a-tabs>

        <!-- Login Form -->
        <a-form
          v-if="activeTab === 'login'"
          :model="loginForm"
          @finish="handleLogin"
          layout="vertical"
          :disabled="loading"
        >
          <a-form-item
            name="email"
            :rules="[
              { required: true, message: 'Введите email' },
              { type: 'email', message: 'Некорректный формат email' },
            ]"
          >
            <a-input
              v-model:value="loginForm.email"
              placeholder="Email"
              size="large"
            >
              <template #prefix><MailOutlined /></template>
            </a-input>
          </a-form-item>

          <a-form-item
            name="password"
            :rules="[{ required: true, message: 'Введите пароль' }]"
          >
            <a-input-password
              v-model:value="loginForm.password"
              placeholder="Пароль"
              size="large"
            >
              <template #prefix><LockOutlined /></template>
            </a-input-password>
          </a-form-item>

          <a-form-item>
            <a-button
              type="primary"
              html-type="submit"
              :loading="loading"
              block
              size="large"
            >
              Войти
            </a-button>
          </a-form-item>
        </a-form>

        <!-- Register Form -->
        <a-form
          v-else
          :model="registerForm"
          @finish="handleRegister"
          layout="vertical"
          :disabled="loading"
        >
          <a-form-item
            name="full_name"
            :rules="[{ required: true, message: 'Введите ФИО' }]"
          >
            <a-input
              v-model:value="registerForm.full_name"
              placeholder="ФИО"
              size="large"
            >
              <template #prefix><UserOutlined /></template>
            </a-input>
          </a-form-item>

          <a-form-item
            name="email"
            :rules="[
              { required: true, message: 'Введите email' },
              { type: 'email', message: 'Некорректный формат email' },
            ]"
          >
            <a-input
              v-model:value="registerForm.email"
              placeholder="Email"
              size="large"
            >
              <template #prefix><MailOutlined /></template>
            </a-input>
          </a-form-item>

          <a-form-item
            name="phone"
          >
            <a-input
              v-model:value="registerForm.phone"
              placeholder="Телефон (необязательно)"
              size="large"
            >
              <template #prefix><PhoneOutlined /></template>
            </a-input>
          </a-form-item>

          <a-form-item
            name="password"
            :rules="[
              { required: true, message: 'Введите пароль' },
              { min: 12, message: 'Минимум 12 символов' },
            ]"
          >
            <a-input-password
              v-model:value="registerForm.password"
              placeholder="Пароль (мин. 12 символов)"
              size="large"
            >
              <template #prefix><LockOutlined /></template>
            </a-input-password>
          </a-form-item>

          <a-form-item
            name="confirmPassword"
            :rules="[
              { required: true, message: 'Подтвердите пароль' },
              { validator: validateConfirmPassword },
            ]"
          >
            <a-input-password
              v-model:value="registerForm.confirmPassword"
              placeholder="Подтвердите пароль"
              size="large"
            >
              <template #prefix><LockOutlined /></template>
            </a-input-password>
          </a-form-item>

          <a-form-item>
            <a-button
              type="primary"
              html-type="submit"
              :loading="loading"
              block
              size="large"
            >
              Зарегистрироваться
            </a-button>
          </a-form-item>
        </a-form>

        <a-alert
          v-if="errorMessage"
          :message="errorMessage"
          type="error"
          show-icon
          closable
          style="margin-top: 16px"
          @close="errorMessage = ''"
        />
      </a-card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import {
  SafetyCertificateOutlined,
  MailOutlined,
  LockOutlined,
  UserOutlined,
  PhoneOutlined,
} from '@ant-design/icons-vue'
import { useAuthStore } from '@/stores/auth'
import { authApi } from '@/api/auth'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()

function resolveNext(): string | null {
  const next = route.query.next as string | undefined
  if (!next) return null
  // Allow same-origin redirects and trusted OIDC callback origins
  const trusted = [
    window.location.origin,       // http://localhost:3000
    'https://localhost:8444',      // IAM backend HTTPS proxy (OIDC authorize)
    'http://localhost:8000',       // IAM backend direct
  ]
  if (next.startsWith('/') || trusted.some(o => next.startsWith(o + '/'))) return next
  return null
}

function navigateAfterLogin(mfaSetupRequired: boolean) {
  const next = resolveNext()
  if (next && !mfaSetupRequired) {
    window.location.href = next
  } else {
    router.push(mfaSetupRequired ? { name: 'setup-totp' } : { name: 'dashboard' })
  }
}

const activeTab = ref('login')
const loading = ref(false)
const errorMessage = ref('')

const loginForm = reactive({
  email: '',
  password: '',
})

const registerForm = reactive({
  full_name: '',
  email: '',
  phone: '',
  password: '',
  confirmPassword: '',
})

function validateConfirmPassword(_rule: unknown, value: string) {
  if (value && value !== registerForm.password) {
    return Promise.reject('Пароли не совпадают')
  }
  return Promise.resolve()
}

async function handleLogin() {
  loading.value = true
  errorMessage.value = ''

  try {
    const { data } = await authApi.login(loginForm.email, loginForm.password)

    if (data.mfa_required) {
      authStore.setMfaSession(data.session_id, data.mfa_method)
      const next = resolveNext()
      router.push({ name: 'mfa', query: next ? { next } : undefined })
      return
    }

    // No MFA step — direct login
    authStore.setTokens(data.access_token, data.refresh_token)
    authStore.setUser(data.user)
    authStore.mfaSetupRequired = data.mfa_setup_required ?? false
    navigateAfterLogin(data.mfa_setup_required ?? false)
  } catch (error: any) {
    const status = error.response?.status
    const detail = error.response?.data?.detail

    if (status === 423) {
      errorMessage.value = detail || 'Аккаунт временно заблокирован. Попробуйте позже.'
    } else if (status === 429) {
      errorMessage.value = 'Слишком много попыток входа. Подождите 5 минут.'
    } else if (status === 401) {
      errorMessage.value = detail || 'Неверный email или пароль'
    } else {
      errorMessage.value = 'Ошибка сервера. Попробуйте позже.'
    }
  } finally {
    loading.value = false
  }
}

async function handleRegister() {
  loading.value = true
  errorMessage.value = ''

  try {
    const { data } = await authApi.register(
      registerForm.email,
      registerForm.password,
      registerForm.full_name,
      registerForm.phone || undefined,
    )

    authStore.setTokens(data.access_token, data.refresh_token)
    authStore.setUser(data.user)
    authStore.mfaSetupRequired = data.mfa_setup_required ?? false
    navigateAfterLogin(data.mfa_setup_required ?? false)
  } catch (error: any) {
    const status = error.response?.status
    const detail = error.response?.data?.detail

    if (status === 409) {
      errorMessage.value = detail || 'Пользователь с таким email уже существует'
    } else {
      errorMessage.value = detail || 'Ошибка регистрации. Попробуйте позже.'
    }
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  padding: 24px;
}

.login-container {
  width: 100%;
  max-width: 420px;
}

.login-header {
  text-align: center;
  margin-bottom: 32px;
}

.logo-icon {
  margin-bottom: 16px;
}

.login-title {
  color: #fff;
  font-size: 28px;
  font-weight: 700;
  margin: 0 0 8px 0;
}

.login-subtitle {
  color: rgba(255, 255, 255, 0.8);
  font-size: 14px;
  margin: 0;
}

.login-card {
  border-radius: 12px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.15);
}
</style>
