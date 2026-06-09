import axios from 'axios'
import { useAuthStore } from '@/stores/auth'
import router from '@/router'
import { message } from 'ant-design-vue'

const api = axios.create({
  baseURL: '/api/v1',
  headers: { 'Content-Type': 'application/json' },
})

api.interceptors.request.use((config) => {
  const authStore = useAuthStore()
  if (authStore.accessToken) {
    config.headers.Authorization = `Bearer ${authStore.accessToken}`
  }
  return config
})

// Single in-flight refresh promise shared across concurrent 401 handlers
let refreshingPromise: Promise<any> | null = null

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config
    const authStore = useAuthStore()

    // Handle 401 with token refresh — only one refresh at a time
    if (error.response?.status === 401 && !originalRequest._retry && authStore.refreshToken) {
      originalRequest._retry = true

      if (!refreshingPromise) {
        refreshingPromise = axios
          .post('/api/v1/auth/refresh', { refresh_token: authStore.refreshToken })
          .finally(() => { refreshingPromise = null })
      }

      try {
        const { data } = await refreshingPromise
        authStore.setTokens(data.access_token, data.refresh_token)
        originalRequest.headers.Authorization = `Bearer ${data.access_token}`
        return api(originalRequest)
      } catch {
        authStore.logout()
        router.push({ name: 'login' })
        message.error('Сессия истекла. Пожалуйста, войдите снова.')
      }
    }

    // Handle 403 Forbidden — only show generic toast if the component
    // hasn't set a custom error message (i.e., no detail field to show inline)
    if (error.response?.status === 403 && !error.response?.data?.detail) {
      message.error('Недостаточно прав для выполнения этого действия')
    }

    return Promise.reject(error)
  }
)

export default api
