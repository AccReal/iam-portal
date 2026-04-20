<template>
  <div v-if="loading" class="loading-overlay">
    <a-spin size="large" :tip="tip" />
  </div>
</template>

<script setup lang="ts">
interface Props {
  loading: boolean
  tip?: string
}

withDefaults(defineProps<Props>(), {
  tip: 'Загрузка...',
})
</script>

<style scoped>
.loading-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(255, 255, 255, 0.8);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  z-index: 9999;
}
</style>
