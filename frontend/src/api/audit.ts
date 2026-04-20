import api from './index'

export const auditApi = {
  list(params: {
    user_id?: string
    action?: string
    date_from?: string
    date_to?: string
    page?: number
    per_page?: number
  }) {
    return api.get('/audit', { params })
  },
  exportCsv(params: Record<string, any>) {
    return api.get('/audit/export', { params: { ...params, format: 'csv' }, responseType: 'blob' })
  },
  exportXlsx(params: Record<string, any>) {
    return api.get('/audit/export', { params: { ...params, format: 'xlsx' }, responseType: 'blob' })
  },
  getStats(days: number = 7) {
    return api.get('/audit/stats', { params: { days } })
  },
}
