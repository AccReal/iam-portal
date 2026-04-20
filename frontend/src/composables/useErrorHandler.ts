import { message, notification } from 'ant-design-vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import type { AxiosError } from 'axios'

interface ErrorResponse {
  detail?: string
  message?: string
}

export function useErrorHandler() {
  const router = useRouter()
  const authStore = useAuthStore()

  /**
   * Handle API errors with appropriate user feedback
   */
  function handleError(error: unknown, context?: string): void {
    const axiosError = error as AxiosError<ErrorResponse>

    // Network error
    if (!axiosError.response) {
      notification.error({
        message: 'Ошибка сети',
        description: 'Не удалось подключиться к серверу. Проверьте подключение к интернету.',
        duration: 5,
      })
      return
    }

    const status = axiosError.response.status
    const errorMessage = axiosError.response.data?.detail || 
                        axiosError.response.data?.message || 
                        'Произошла ошибка'

    // Handle specific status codes
    switch (status) {
      case 401:
        // Unauthorized - redirect to login
        message.error('Сессия истекла. Пожалуйста, войдите снова.')
        authStore.logout()
        router.push({ name: 'login' })
        break

      case 403:
        // Forbidden - insufficient permissions
        message.error('Недостаточно прав для выполнения этого действия')
        break

      case 404:
        // Not found
        message.error('Запрашиваемый ресурс не найден')
        break

      case 422:
        // Validation error
        notification.error({
          message: 'Ошибка валидации',
          description: errorMessage,
          duration: 5,
        })
        break

      case 429:
        // Rate limit
        message.warning('Слишком много запросов. Пожалуйста, подождите.')
        break

      case 500:
      case 502:
      case 503:
        // Server errors
        notification.error({
          message: 'Ошибка сервера',
          description: 'Произошла внутренняя ошибка сервера. Попробуйте позже.',
          duration: 5,
        })
        break

      default:
        // Generic error
        const contextMessage = context ? `${context}: ${errorMessage}` : errorMessage
        message.error(contextMessage)
    }
  }

  /**
   * Handle error with retry functionality
   */
  function handleErrorWithRetry(
    error: unknown,
    retryFn: () => Promise<void>,
    context?: string
  ): void {
    const axiosError = error as AxiosError<ErrorResponse>

    // Network error - offer retry
    if (!axiosError.response) {
      notification.error({
        message: 'Ошибка сети',
        description: 'Не удалось подключиться к серверу. Попробуйте позже или нажмите "Повторить".',
        duration: 0,
      })
      return
    }

    // For other errors, use standard error handling
    handleError(error, context)
  }

  /**
   * Validate form field
   */
  function validateField(
    value: string | undefined | null,
    rules: {
      required?: boolean
      email?: boolean
      minLength?: number
      maxLength?: number
      pattern?: RegExp
      custom?: (value: string) => boolean
    }
  ): string | null {
    if (rules.required && (!value || value.trim() === '')) {
      return 'Это поле обязательно для заполнения'
    }

    if (!value) return null

    if (rules.email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)) {
      return 'Введите корректный email адрес'
    }

    if (rules.minLength && value.length < rules.minLength) {
      return `Минимальная длина: ${rules.minLength} символов`
    }

    if (rules.maxLength && value.length > rules.maxLength) {
      return `Максимальная длина: ${rules.maxLength} символов`
    }

    if (rules.pattern && !rules.pattern.test(value)) {
      return 'Значение не соответствует требуемому формату'
    }

    if (rules.custom && !rules.custom(value)) {
      return 'Значение не прошло валидацию'
    }

    return null
  }

  /**
   * Show success message
   */
  function showSuccess(msg: string): void {
    message.success(msg)
  }

  /**
   * Show warning message
   */
  function showWarning(msg: string): void {
    message.warning(msg)
  }

  /**
   * Show info message
   */
  function showInfo(msg: string): void {
    message.info(msg)
  }

  return {
    handleError,
    handleErrorWithRetry,
    validateField,
    showSuccess,
    showWarning,
    showInfo,
  }
}
