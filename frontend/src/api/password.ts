import api from './index'

export const passwordApi = {
  generate(params: {
    length?: number
    include_uppercase?: boolean
    include_digits?: boolean
    include_special?: boolean
    exclude_similar?: boolean
    exclude_ambiguous?: boolean
    count?: number
  }) {
    return api.post('/password/generate', params)
  },
  validate(password: string) {
    return api.post('/password/validate', { password })
  },
}
