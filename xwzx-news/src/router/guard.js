import { showToast } from 'vant'

import { i18n } from '../i18n'
import { useUserStore } from '../store/user'

/**
 * 登录 / 管理员路由守卫。
 *
 * 刻意不写在 `router/index.js` 里：那里 import store 会形成
 * `router -> store/user -> api/http -> router` 的循环依赖。
 * 改由 main.js 在 pinia 安装完成之后调用。
 *
 * 这里只是体验层拦截，真正的权限校验在后端（401 / 403）。
 */
export function setupGuard(router) {
  router.beforeEach((to) => {
    const needsAuth = to.meta?.requiresAuth || to.meta?.requiresAdmin
    if (!needsAuth) return true

    const userStore = useUserStore()

    if (!userStore.isLogin) {
      showToast(i18n.global.t('common.loginRequired'))
      return { path: '/login', query: { redirect: to.fullPath } }
    }

    if (to.meta?.requiresAdmin && !userStore.userInfo?.isAdmin) {
      showToast(i18n.global.t('common.adminRequired'))
      return '/home'
    }

    return true
  })
}
