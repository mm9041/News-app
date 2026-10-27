import { showToast } from 'vant'

import { useUserStore } from '../store/user'

/**
 * 管理员路由守卫。
 *
 * 刻意不写在 `router/index.js` 里：那里 import store 会形成
 * `router -> store/user -> api/http -> router` 的循环依赖。
 * 改由 main.js 在 pinia 安装完成之后调用。
 *
 * 这里只是体验层拦截（未登录/非管理员不显示管理页），
 * 真正的权限校验在后端 `/api/admin/*` 的 get_current_admin。
 */
export function setupGuard(router) {
  router.beforeEach((to) => {
    if (!to.meta?.requiresAdmin) return true

    const userStore = useUserStore()

    if (!userStore.isLogin) {
      showToast('请先登录')
      return { path: '/login', query: { redirect: to.fullPath } }
    }

    if (!userStore.userInfo?.isAdmin) {
      showToast('需要管理员权限')
      return '/home'
    }

    return true
  })
}
