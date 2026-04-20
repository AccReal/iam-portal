import api from './index'

export async function getApplications(): Promise<any[]> {
  const res = await api.get('/sso/apps')
  return res.data.apps ?? []
}

export const applicationsApi = {
  list(page = 1, perPage = 20) {
    return api.get('/applications', { params: { page, per_page: perPage } })
  },
  create(data: Record<string, any>) {
    return api.post('/applications', data)
  },
  update(appId: string, data: Record<string, any>) {
    return api.put(`/applications/${appId}`, data)
  },
  delete(appId: string) {
    return api.delete(`/applications/${appId}`)
  },
  toggleActive(appId: string, isActive: boolean) {
    return api.put(`/applications/${appId}`, { is_active: isActive })
  },
}
