<template>
  <div class="setup-page">
    <div class="setup-container">
      <div class="setup-header">
        <SafetyCertificateOutlined style="font-size: 48px; color: #52c41a" />
        <h1 class="setup-title">Настройка двухфакторной аутентификации</h1>
        <p class="setup-subtitle">Это обязательный шаг для защиты вашего аккаунта</p>
      </div>

      <a-card class="setup-card" :bordered="false">
        <!-- Step 1: show QR -->
        <template v-if="step === 1">
          <a-steps :current="0" size="small" style="margin-bottom: 28px">
            <a-step title="Сканирование" />
            <a-step title="Проверка" />
            <a-step title="Готово" />
          </a-steps>

          <a-alert type="info" show-icon style="margin-bottom: 20px">
            <template #message>Установите приложение-аутентификатор</template>
            <template #description>
              Google Authenticator, Яндекс Ключ, Authy или любое совместимое с TOTP приложение.
            </template>
          </a-alert>

          <div v-if="loadingQr" style="text-align: center; padding: 40px">
            <a-spin size="large" />
          </div>

          <template v-else-if="qrData">
            <div style="text-align: center; margin-bottom: 20px">
              <img
                :src="`data:image/png;base64,${qrData.qr_image}`"
                alt="TOTP QR code"
                style="width: 220px; height: 220px; border: 1px solid #f0f0f0; border-radius: 8px"
              />
            </div>

            <a-descriptions bordered :column="1" size="small" style="margin-bottom: 20px">
              <a-descriptions-item label="Секрет (ручной ввод)">
                <a-typography-text code copyable>{{ qrData.secret }}</a-typography-text>
              </a-descriptions-item>
              <a-descriptions-item label="Алгоритм">TOTP · SHA-1 · 30 сек · 6 цифр</a-descriptions-item>
            </a-descriptions>

            <a-button type="primary" block size="large" @click="step = 2">
              Я отсканировал — ввести код
            </a-button>
          </template>

          <a-alert v-if="loadError" :message="loadError" type="error" show-icon style="margin-top: 16px" />
        </template>

        <!-- Step 2: verify code -->
        <template v-else-if="step === 2">
          <a-steps :current="1" size="small" style="margin-bottom: 28px">
            <a-step title="Сканирование" />
            <a-step title="Проверка" />
            <a-step title="Готово" />
          </a-steps>

          <a-alert type="info" show-icon style="margin-bottom: 20px">
            <template #message>Введите 6-значный код из приложения</template>
            <template #description>Убедитесь, что код совпадает с текущим значением в аутентификаторе.</template>
          </a-alert>

          <div>
            <div class="code-inputs" style="margin-bottom: 24px">
              <a-input
                v-for="(_, i) in 6"
                :key="i"
                :ref="(el: any) => setRef(el, i)"
                v-model:value="codeDigits[i]"
                class="code-input"
                :maxlength="1"
                size="large"
                :disabled="confirming"
                @input="onInput(i)"
                @keydown="onKeydown($event, i)"
                @paste="onPaste"
              />
            </div>

            <a-button
              type="primary"
              block
              size="large"
              :loading="confirming"
              :disabled="code.length !== 6"
              @click="handleConfirm"
            >
              Подтвердить и включить MFA
            </a-button>
            <a-button type="link" block style="margin-top: 8px" @click="goBackToQr">
              Назад к QR-коду
            </a-button>
          </div>

          <a-alert
            v-if="confirmError"
            :message="confirmError"
            type="error"
            show-icon
            closable
            style="margin-top: 16px"
            @close="confirmError = ''"
          />
        </template>

        <!-- Step 3: success -->
        <template v-else>
          <a-steps :current="2" size="small" style="margin-bottom: 28px">
            <a-step title="Сканирование" />
            <a-step title="Проверка" />
            <a-step title="Готово" />
          </a-steps>

          <a-result
            status="success"
            title="MFA успешно настроена!"
            sub-title="Теперь при каждом входе потребуется код из приложения-аутентификатора."
          >
            <template #extra>
              <a-button type="primary" size="large" @click="goToDashboard">
                Перейти в систему
              </a-button>
            </template>
          </a-result>
        </template>
      </a-card>

      <div style="text-align: center; margin-top: 16px">
        <a-button type="link" @click="handleLogout" style="color: rgba(255,255,255,0.8)">
          Выйти из аккаунта
        </a-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { SafetyCertificateOutlined } from '@ant-design/icons-vue'
import { useAuthStore } from '@/stores/auth'
import { usersApi } from '@/api/users'

const router = useRouter()
const authStore = useAuthStore()

const step = ref(1)
const loadingQr = ref(true)
const loadError = ref('')
const qrData = ref<{ secret: string; qr_uri: string; qr_image: string } | null>(null)

const confirming = ref(false)
const confirmError = ref('')
const codeDigits = reactive(['', '', '', '', '', ''])
const inputRefs: (HTMLInputElement | null)[] = []

const code = computed(() => codeDigits.join(''))

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function setRef(el: any, i: number) {
  if (el) inputRefs[i] = el.$el?.querySelector?.('input') || el.input || el
}

function onInput(i: number) {
  const v = codeDigits[i]
  if (v && /^\d$/.test(v) && i < 5) inputRefs[i + 1]?.focus()
  if (v && !/^\d$/.test(v)) codeDigits[i] = ''
}

function onKeydown(e: KeyboardEvent, i: number) {
  if (e.key === 'Backspace' && !codeDigits[i] && i > 0) inputRefs[i - 1]?.focus()
}

function onPaste(e: ClipboardEvent) {
  e.preventDefault()
  const pasted = e.clipboardData?.getData('text')?.replace(/\D/g, '')?.slice(0, 6)
  if (pasted) {
    for (let i = 0; i < 6; i++) codeDigits[i] = pasted[i] || ''
    inputRefs[Math.min(pasted.length, 5)]?.focus()
  }
}

async function loadQr() {
  loadingQr.value = true
  loadError.value = ''
  try {
    const { data } = await usersApi.setupMfa()
    qrData.value = data
  } catch (e: any) {
    loadError.value = e.response?.data?.detail || 'Не удалось получить QR-код. Попробуйте обновить страницу.'
  } finally {
    loadingQr.value = false
  }
}

async function handleConfirm() {
  if (code.value.length !== 6) return
  confirming.value = true
  confirmError.value = ''
  try {
    await usersApi.confirmMfa(code.value)
    authStore.completeMfaSetup()
    step.value = 3
  } catch (e: any) {
    confirmError.value = e.response?.data?.detail || 'Неверный код. Проверьте время на устройстве и попробуйте снова.'
    for (let i = 0; i < 6; i++) codeDigits[i] = ''
    inputRefs[0]?.focus()
  } finally {
    confirming.value = false
  }
}

async function goBackToQr() {
  // Regenerate secret — old one may have expired in Redis (10-min TTL)
  step.value = 1
  await loadQr()
}

function goToDashboard() {
  router.push({ name: 'dashboard' })
}

function handleLogout() {
  authStore.logout()
  router.push({ name: 'login' })
}

onMounted(loadQr)
</script>

<style scoped>
.setup-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
  padding: 24px;
}

.setup-container {
  width: 100%;
  max-width: 500px;
}

.setup-header {
  text-align: center;
  margin-bottom: 32px;
}

.setup-title {
  color: #fff;
  font-size: 22px;
  font-weight: 700;
  margin: 16px 0 8px 0;
}

.setup-subtitle {
  color: rgba(255, 255, 255, 0.85);
  margin: 0;
}

.setup-card {
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
}

.code-input :deep(input) {
  text-align: center;
  font-size: 24px;
  font-weight: 700;
}
</style>
