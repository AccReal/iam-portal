import api from './index'

export const rolesApi = {
  list() {
    return api.get('/roles')
  },
  
  create(data: { name: string; description?: string }) {
    return api.post('/roles', data)
  },
  
  get(id: string) {
    return api.get(`/roles/${id}`)
  },
  
  update(id: string, data: { name?: string; description?: string }) {
    return api.put(`/roles/${id}`, data)
  },
  
  delete(id: string) {
    return api.delete(`/roles/${id}`)
  },
  
  getPermissions(roleId: string) {
    return api.get(`/roles/${roleId}/permissions`)
  },
  
  updatePermissions(roleId: string, permissions: Array<{ permission_id: string; granted: boolean }>) {
    return api.put(`/roles/${roleId}/permissions`, { permissions })
  },
  
  getAllPermissions() {
    return api.get('/roles/permissions')
  },
}
