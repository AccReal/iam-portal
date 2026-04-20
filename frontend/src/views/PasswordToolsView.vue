<template>
  <div>
    <a-typography-title :level="3">Инструменты паролей</a-typography-title>

    <a-row :gutter="24">
      <!-- Generator -->
      <a-col :xs="24" :lg="12">
        <a-card title="Генератор паролей" style="margin-bottom: 24px">
          <a-form layout="vertical">
            <a-form-item label="Длина пароля">
              <a-row :gutter="12" align="middle">
                <a-col :span="16">
                  <a-slider v-model:value="genForm.length" :min="4" :max="128" />
                </a-col>
                <a-col :span="8">
                  <a-input-number v-model:value="genForm.length" :min="4" :max="128" style="width: 100%" />
                </a-col>
              </a-row>
            </a-form-item>

            <a-form-item label="Параметры">
              <a-space direction="vertical">
                <a-checkbox v-model:checked="genForm.include_uppercase">Заглавные буквы (A-Z)</a-checkbox>
                <a-checkbox v-model:checked="genForm.include_digits">Цифры (0-9)</a-checkbox>
                <a-checkbox v-model:checked="genForm.include_special">Спецсимволы (!@#$...)</a-checkbox>
                <a-checkbox v-model:checked="genForm.exclude_similar">Исключить похожие (l, 1, I, O, 0)</a-checkbox>
                <a-checkbox v-model:checked="genForm.exclude_ambiguous">Исключить неоднозначные ({}[]()/\)</a-checkbox>
              </a-space>
            </a-form-item>

            <a-form-item label="Количество">
              <a-input-number v-model:value="genForm.count" :min="1" :max="50" />
            </a-form-item>

            <a-button type="primary" :loading="generating" @click="generate" block>
              Сгенерировать
            </a-button>
          </a-form>

          <div v-if="generatedPasswords.length" style="margin-top: 16px">
            <a-divider>Результат</a-divider>
            <div v-for="(pwd, i) in generatedPasswords" :key="i" style="margin-bottom: 8px">
              <a-input :value="pwd" readonly>
                <template #addonAfter>
                  <a-button type="link" size="small" @click="copyPassword(pwd)">
                    <CopyOutlined />
                  </a-button>
                </template>
              </a-input>
            </div>
          </div>
        </a-card>
      </a-col>

      <!-- Validator -->
      <a-col :xs="24" :lg="12">
        <a-card title="Проверка надёжности пароля" style="margin-bottom: 24px">
          <a-form layout="vertical">
            <a-form-item label="Введите пароль">
              <a-input-password v-model:value="validatePassword" placeholder="Пароль для проверки" @input="onValidateInput" />
            </a-form-item>
          </a-form>

          <div v-if="validation">
            <a-divider>Результат анализа</a-divider>

            <div style="margin-bottom: 16px">
              <div style="display: flex; justify-content: space-between; margin-bottom: 4px">
                <span>Надёжность</span>
                <span :style="{ fontWeight: 'bold', color: strengthColor }">{{ validation.strength }}</span>
              </div>
              <a-progress :percent="validation.score" :stroke-color="strengthColor" :show-info="false" />
              <div style="text-align: center; margin-top: 4px; font-size: 20px; font-weight: bold;">
                {{ validation.score }} / 100
              </div>
            </div>

            <a-descriptions bordered :column="1" size="small" style="margin-bottom: 16px">
              <a-descriptions-item label="Длина">{{ validation.length }} символов</a-descriptions-item>
              <a-descriptions-item label="Время взлома">{{ validation.crack_time }}</a-descriptions-item>
              <a-descriptions-item label="Заглавные буквы">
                <a-tag :color="validation.has_uppercase ? 'green' : 'red'">{{ validation.has_uppercase ? 'Да' : 'Нет' }}</a-tag>
              </a-descriptions-item>
              <a-descriptions-item label="Строчные буквы">
                <a-tag :color="validation.has_lowercase ? 'green' : 'red'">{{ validation.has_lowercase ? 'Да' : 'Нет' }}</a-tag>
              </a-descriptions-item>
              <a-descriptions-item label="Цифры">
                <a-tag :color="validation.has_digits ? 'green' : 'red'">{{ validation.has_digits ? 'Да' : 'Нет' }}</a-tag>
              </a-descriptions-item>
              <a-descriptions-item label="Спецсимволы">
                <a-tag :color="validation.has_special ? 'green' : 'red'">{{ validation.has_special ? 'Да' : 'Нет' }}</a-tag>
              </a-descriptions-item>
            </a-descriptions>

            <div v-if="validation.feedback.length">
              <a-typography-text strong>Рекомендации:</a-typography-text>
              <ul style="margin-top: 8px; padding-left: 20px">
                <li v-for="(fb, i) in validation.feedback" :key="i">{{ fb }}</li>
              </ul>
            </div>
          </div>
        </a-card>
      </a-col>
    </a-row>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { message } from 'ant-design-vue'
import { CopyOutlined } from '@ant-design/icons-vue'
import { passwordApi } from '@/api/password'

const genForm = ref({
  length: 16,
  include_uppercase: true,
  include_digits: true,
  include_special: true,
  exclude_similar: false,
  exclude_ambiguous: false,
  count: 1,
})

const generating = ref(false)
const generatedPasswords = ref<string[]>([])
const validatePassword = ref('')
const validation = ref<any>(null)
let validateTimer: ReturnType<typeof setTimeout> | null = null

const strengthColor = computed(() => {
  if (!validation.value) return '#d9d9d9'
  const level = validation.value.strength_level
  return ['#ff4d4f', '#fa8c16', '#fadb14', '#52c41a', '#1890ff'][level] || '#d9d9d9'
})

async function generate() {
  generating.value = true
  try {
    const { data } = await passwordApi.generate(genForm.value)
    generatedPasswords.value = data.passwords
  } catch (e: any) {
    message.error(e.response?.data?.detail || 'Ошибка генерации')
  } finally {
    generating.value = false
  }
}

function copyPassword(pwd: string) {
  navigator.clipboard.writeText(pwd)
  message.success('Скопировано в буфер обмена')
}

function onValidateInput() {
  if (validateTimer) clearTimeout(validateTimer)
  if (!validatePassword.value) {
    validation.value = null
    return
  }
  validateTimer = setTimeout(async () => {
    try {
      const { data } = await passwordApi.validate(validatePassword.value)
      validation.value = data
    } catch {
      validation.value = null
    }
  }, 400)
}
</script>
