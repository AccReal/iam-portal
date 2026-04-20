import { ref } from 'vue'

/**
 * Composable for managing loading states
 */
export function useLoading(initialState = false) {
  const loading = ref(initialState)
  const error = ref<string | null>(null)

  /**
   * Execute an async operation with loading state
   */
  async function withLoading<T>(
    operation: () => Promise<T>,
    errorHandler?: (error: unknown) => void
  ): Promise<T | null> {
    loading.value = true
    error.value = null

    try {
      const result = await operation()
      return result
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Unknown error'
      if (errorHandler) {
        errorHandler(err)
      }
      return null
    } finally {
      loading.value = false
    }
  }

  /**
   * Set loading state manually
   */
  function setLoading(state: boolean): void {
    loading.value = state
  }

  /**
   * Set error manually
   */
  function setError(err: string | null): void {
    error.value = err
  }

  /**
   * Clear error
   */
  function clearError(): void {
    error.value = null
  }

  return {
    loading,
    error,
    withLoading,
    setLoading,
    setError,
    clearError,
  }
}
