import { ref, reactive } from 'vue'

export interface ValidationRule {
  required?: boolean
  email?: boolean
  minLength?: number
  maxLength?: number
  pattern?: RegExp
  custom?: (value: string) => boolean | string
  message?: string
}

export interface FieldRules {
  [key: string]: ValidationRule[]
}

export function useFormValidation<T extends Record<string, any>>(initialValues: T) {
  const formData = reactive<T>({ ...initialValues })
  const errors = reactive<Record<string, string>>({})
  const touched = reactive<Record<string, boolean>>({})

  /**
   * Validate a single field
   */
  function validateField(fieldName: keyof T, rules: ValidationRule[]): boolean {
    const value = (formData as any)[fieldName]
    errors[fieldName as string] = ''

    for (const rule of rules) {
      // Required validation
      if (rule.required && (!value || (typeof value === 'string' && value.trim() === ''))) {
        errors[fieldName as string] = rule.message || 'Это поле обязательно для заполнения'
        return false
      }

      // Skip other validations if value is empty and not required
      if (!value || (typeof value === 'string' && value.trim() === '')) {
        continue
      }

      const stringValue = String(value)

      // Email validation
      if (rule.email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(stringValue)) {
        errors[fieldName as string] = rule.message || 'Введите корректный email адрес'
        return false
      }

      // Min length validation
      if (rule.minLength && stringValue.length < rule.minLength) {
        errors[fieldName as string] = rule.message || `Минимальная длина: ${rule.minLength} символов`
        return false
      }

      // Max length validation
      if (rule.maxLength && stringValue.length > rule.maxLength) {
        errors[fieldName as string] = rule.message || `Максимальная длина: ${rule.maxLength} символов`
        return false
      }

      // Pattern validation
      if (rule.pattern && !rule.pattern.test(stringValue)) {
        errors[fieldName as string] = rule.message || 'Значение не соответствует требуемому формату'
        return false
      }

      // Custom validation
      if (rule.custom) {
        const result = rule.custom(stringValue)
        if (result === false) {
          errors[fieldName as string] = rule.message || 'Значение не прошло валидацию'
          return false
        } else if (typeof result === 'string') {
          errors[fieldName as string] = result
          return false
        }
      }
    }

    return true
  }

  /**
   * Validate all fields
   */
  function validateForm(fieldRules: FieldRules): boolean {
    let isValid = true

    for (const [fieldName, rules] of Object.entries(fieldRules)) {
      const fieldValid = validateField(fieldName as keyof T, rules)
      if (!fieldValid) {
        isValid = false
      }
    }

    return isValid
  }

  /**
   * Mark field as touched
   */
  function touchField(fieldName: keyof T): void {
    touched[fieldName as string] = true
  }

  /**
   * Reset form
   */
  function resetForm(newValues?: Partial<T>): void {
    Object.keys(formData).forEach((key) => {
      if (newValues && key in newValues) {
        (formData as any)[key] = newValues[key as keyof T]
      } else {
        (formData as any)[key] = initialValues[key as keyof T]
      }
      errors[key] = ''
      touched[key] = false
    })
  }

  /**
   * Clear errors
   */
  function clearErrors(): void {
    Object.keys(errors).forEach((key) => {
      errors[key] = ''
    })
  }

  /**
   * Set field value
   */
  function setFieldValue(fieldName: keyof T, value: any): void {
    (formData as any)[fieldName] = value
  }

  /**
   * Get field error
   */
  function getFieldError(fieldName: keyof T): string {
    return errors[fieldName as string] || ''
  }

  /**
   * Check if field has error
   */
  function hasFieldError(fieldName: keyof T): boolean {
    return !!errors[fieldName as string] && touched[fieldName as string]
  }

  return {
    formData,
    errors,
    touched,
    validateField,
    validateForm,
    touchField,
    resetForm,
    clearErrors,
    setFieldValue,
    getFieldError,
    hasFieldError,
  }
}
