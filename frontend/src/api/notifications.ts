import api from './index'

export const notificationsApi = {
  list(unreadOnly = false, limit = 20) {
    return api.get('/notifications', { params: { unread_only: unreadOnly, limit } })
  },
  unreadCount() {
    return api.get('/notifications/unread-count')
  },
  markRead(id: string) {
    return api.post(`/notifications/${id}/read`)
  },
  markAllRead() {
    return api.post('/notifications/read-all')
  },
}
