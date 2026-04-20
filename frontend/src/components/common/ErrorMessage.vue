<template>
  <div v-if="error" class="error-message" :class="{ 'error-message-with-retry': showRetry }">
    <div>
      <CloseCircleOutlined style="color: #cf1322; margin-right: 8px;" />
      <span>{{ error }}</span>
    </div>
    <a-button v-if="showRetry" type="primary" size="small" @click="handleRetry">
      Повторить
    </a-button>
  </div>
</template>

<script setup lang="ts">
import { CloseCircleOutlined } from '@ant-design/icons-vue'

interface Props {
  error: string | null
  showRetry?: boolean
}

interface Emits {
  (e: 'retry'): void
}

withDefaults(defineProps<Props>(), {
  showRetry: false,
})

const emit = defineEmits<Emits>()

function handleRetry() {
  emit('retry')
}
</script>

<style scoped>
.error-message {
  padding: 12px 16px;
  background: #fff2f0;
  border: 1px solid #ffccc7;
  border-radius: 4px;
  color: #cf1322;
  margin-bottom: 16px;
}

.error-message-with-retry {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
