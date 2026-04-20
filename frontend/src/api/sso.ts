import api from './index'

export const ssoApi = {
  getMyApps() {
    return api.get('/sso/apps')
  },
  authorize(appId: string) {
    return api.get('/sso/authorize', { params: { app_id: appId } })
  },
}
