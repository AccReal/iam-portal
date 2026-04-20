import api from './index'

export const authApi = {
  login(email: string, password: string) {
    return api.post('/auth/login', { email, password })
  },
  register(email: string, password: string, full_name: string, phone?: string) {
    return api.post('/auth/register', { email, password, full_name, phone })
  },
  verifyMfa(session_id: string, code: string) {
    return api.post('/auth/verify-mfa', { session_id, code })
  },
  refresh(refresh_token: string) {
    return api.post('/auth/refresh', { refresh_token })
  },
  logout(refresh_token: string) {
    return api.post('/auth/logout', { refresh_token })
  },
  getMe() {
    return api.get('/auth/me')
  },
}
