import api from './index'

export const usersApi = {
  getMe() {
    return api.get('/users/me')
  },
  getMfaConfig() {
    return api.get('/users/mfa-config')
  },
  list(page = 1, perPage = 20, search?: string) {
    return api.get('/users', { params: { page, per_page: perPage, search } })
  },
  create(data: { email: string; full_name: string; phone?: string; role_id?: string; password?: string }) {
    return api.post('/users', data)
  },
  update(userId: string, data: Record<string, any>) {
    return api.put(`/users/${userId}`, data)
  },
  block(userId: string) {
    return api.post(`/users/${userId}/block`)
  },
  unblock(userId: string) {
    return api.post(`/users/${userId}/unblock`)
  },
  resetPassword(userId: string) {
    return api.post(`/users/${userId}/reset-password`)
  },

  // --- MFA (two-step) ---
  /** Step 1: generate secret + QR, stored pending in Redis */
  setupMfa() {
    return api.post('/users/me/setup-mfa')
  },
  /** Step 2: confirm TOTP code → enable MFA */
  confirmMfa(code: string) {
    return api.post('/users/me/confirm-mfa', { code })
  },
  /** Disable MFA — requires current TOTP code */
  disableMfaWithCode(code: string) {
    return api.post('/users/me/disable-mfa', { code })
  },

  changePassword(oldPassword: string, newPassword: string) {
    return api.post('/users/me/change-password', { old_password: oldPassword, new_password: newPassword })
  },
  getMyActivity(limit = 10) {
    return api.get('/users/me/activity', { params: { limit } })
  },
}
