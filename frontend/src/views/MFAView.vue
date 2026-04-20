<template>
  <div class="mfa-page">
    <div class="mfa-container">
      <div class="mfa-header">
        <SafetyCertificateOutlined style="font-size: 48px; color: #1890ff" />
        <h1 class="mfa-title">Подтверждение входа</h1>
      </div>

      <a-card class="mfa-card" :bordered="false">
        <div class="mfa-info">
          <a-alert
            v-if="authStore.mfaMethod === 'sms'"
            message="Код отправлен на ваш номер телефона"
            description="Введите 6-значный код из SMS"
            type="info"
            show-icon
            style="margin-bottom: 24px"
          />
          <a-alert
            v-else
            message="Введите код из приложения-аутентификатора"
            description="Откройте Google Authenticator или Authy и введите 6-значный код"
            type="info"
            show-icon
            style="margin-bottom: 24px"
          />
        </div>

        <div>
          <div class="code-inputs" style="margin-bottom: 16px">
            <a-input
              v-for="(_, index) in 6"
              :key="index"
              :ref="(el: any) => setInputRef(el, index)"
              v-model:value="codeDigits[index]"
              class="code-input"
              :maxlength="1"
              size="large"
              :disabled="loading"
              @input="onDigitInput(index)"
              @keydown="onDigitKeydown($event, index)"
              @paste="onPaste"
            />
          </div>

          <div class="timer-section" v-if="authStore.mfaMethod === 'sms'">
            <p v-if="countdown > 0" class="timer-text">
              Код действителен: {{ formatTime(countdown) }}
            </p>
            <p v-else class="timer-expired">
              Код истёк
            </p>
            <a-button
              type="link"
              :disabled="resendCooldown > 0"
              @click="handleResend"
            >
              {{ resendCooldown > 0
                ? `Отправить повторно (${resendCooldown}с)`
                : 'Отправить код повторно'
              }}
            </a-button>
          </div>

          <a-button
            type="primary"
            :loading="loading"
            :disabled="code.length !== 6"
            block
            size="large"
            style="margin-top: 16px"
            @click="handleVerify"
          >
            Подтвердить
          </a-button>

          <a-button type="link" block style="margin-top: 8px" @click="handleBack">
            Вернуться к входу
          </a-button>
        </div>

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
import { ref, reactive, computed, onMounted, onUnmounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { SafetyCertificateOutlined } from '@ant-design/icons-vue'
import { useAuthStore } from '@/stores/auth'
import { authApi } from '@/api/auth'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()

function resolveNext(): string | null {
  const next = route.query.next as string | undefined
  if (!next) return null
  const trusted = [
    window.location.origin,
    'https://localhost:8444',
    'http://localhost:8000',
  ]
  if (next.startsWith('/') || trusted.some(o => next.startsWith(o + '/'))) return next
  return null
}

const loading = ref(false)
const errorMessage = ref('')
const codeDigits = reactive(['', '', '', '', '', ''])
const inputRefs: (HTMLInputElement | null)[] = []

const countdown = ref(300) // 5 minutes
const resendCooldown = ref(0)
let countdownTimer: number | null = null
let resendTimer: number | null = null

const code = computed(() => codeDigits.join(''))

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function setInputRef(el: any, index: number) {
  if (el) {
    inputRefs[index] = el.$el?.querySelector?.('input') || el.input || el
  }
}

function onDigitInput(index: number) {
  const val = codeDigits[index]
  if (val && /^\d$/.test(val) && index < 5) {
    inputRefs[index + 1]?.focus()
  }
  // Filter non-digits
  if (val && !/^\d$/.test(val)) {
    codeDigits[index] = ''
  }
}

function onDigitKeydown(event: KeyboardEvent, index: number) {
  if (event.key === 'Backspace' && !codeDigits[index] && index > 0) {
    inputRefs[index - 1]?.focus()
  }
}

function onPaste(event: ClipboardEvent) {
  event.preventDefault()
  const pasted = event.clipboardData?.getData('text')?.replace(/\D/g, '')?.slice(0, 6)
  if (pasted) {
    for (let i = 0; i < 6; i++) {
      codeDigits[i] = pasted[i] || ''
    }
    const focusIndex = Math.min(pasted.length, 5)
    inputRefs[focusIndex]?.focus()
  }
}

function formatTime(seconds: number): string {
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return `${m}:${s.toString().padStart(2, '0')}`
}

function startCountdown() {
  countdown.value = 300
  countdownTimer = window.setInterval(() => {
    if (countdown.value > 0) {
      countdown.value--
    } else if (countdownTimer) {
      clearInterval(countdownTimer)
    }
  }, 1000)
}

function startResendCooldown() {
  resendCooldown.value = 60
  resendTimer = window.setInterval(() => {
    if (resendCooldown.value > 0) {
      resendCooldown.value--
    } else if (resendTimer) {
      clearInterval(resendTimer)
    }
  }, 1000)
}

async function handleVerify() {
  if (code.value.length !== 6 || !authStore.mfaSessionId) return

  loading.value = true
  errorMessage.value = ''

  try {
    const { data } = await authApi.verifyMfa(authStore.mfaSessionId, code.value)
    authStore.setTokens(data.access_token, data.refresh_token)
    authStore.setUser(data.user)
    const next = resolveNext()
    if (next) {
      window.location.href = next
    } else {
      router.push({ name: 'dashboard' })
    }
  } catch (error: any) {
    const detail = error.response?.data?.detail
    if (error.response?.status === 400) {
      errorMessage.value = 'Сессия истекла. Войдите заново.'
    } else {
      errorMessage.value = detail || 'Неверный код. Попробуйте ещё раз.'
    }
    // Clear code on error
    for (let i = 0; i < 6; i++) codeDigits[i] = ''
    inputRefs[0]?.focus()
  } finally {
    loading.value = false
  }
}

async function handleResend() {
  // Re-login to get new MFA session
  errorMessage.value = ''
  startResendCooldown()
  startCountdown()
  // Clear old code
  for (let i = 0; i < 6; i++) codeDigits[i] = ''
  inputRefs[0]?.focus()
}

function handleBack() {
  authStore.logout()
  router.push({ name: 'login' })
}

onMounted(() => {
  if (!authStore.mfaSessionId) {
    router.push({ name: 'login' })
    return
  }
  startCountdown()
  inputRefs[0]?.focus()
})

onUnmounted(() => {
  if (countdownTimer) clearInterval(countdownTimer)
  if (resendTimer) clearInterval(resendTimer)
})
</script>

<style scoped>
.mfa-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  padding: 24px;
}

.mfa-container {
  width: 100%;
  max-width: 440px;
}

.mfa-header {
  text-align: center;
  margin-bottom: 32px;
}

.mfa-title {
  color: #fff;
  font-size: 24px;
  font-weight: 700;
  margin: 16px 0 0 0;
}

.mfa-card {
  border-radius: 12px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.15);
}

.code-inputs {
  display: flex;
  gap: 8px;
  justify-content: center;
}

.code-input {
  width: 48px !important;
  height: 56px !important;
  text-align: center;
  font-size: 24px;
  font-weight: 700;
}

.code-input :deep(input) {
  text-align: center;
  font-size: 24px;
  font-weight: 700;
}

.timer-section {
  text-align: center;
  margin-top: 8px;
}

.timer-text {
  color: #666;
  margin-bottom: 4px;
}

.timer-expired {
  color: #ff4d4f;
  margin-bottom: 4px;
}
</style>
