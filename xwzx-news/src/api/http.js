import axios from 'axios'
import { showToast } from 'vant'

import { apiConfig } from '../config/api'
import router from '../router'

/**
 * 全局唯一的 axios 实例。
 *
 * 认证走 httpOnly cookie（登录接口下发），所以这里只需要
 * `withCredentials: true` —— 不再有「每个调用点自己往 headers 塞 token」这回事，
 * JS 也读不到 token（XSS 偷不走）。
 *
 * 401 时要做的事（清登录态）由 main.js 注入：如果在模块顶层 import useUserStore，
 * 会和 store/user.js -> api/http.js 形成循环依赖（且 pinia 尚未安装）。
 */
const http = axios.create({
  baseURL: apiConfig.baseURL,
  timeout: 15000,
  withCredentials: true,
})

let onUnauthorized = null

export function bindUnauthorizedHandler(fn) {
  onUnauthorized = fn
}

http.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error.response?.status

    if (status === 401) {
      onUnauthorized?.()

      // 启动时探活 `/api/user/info` 本来就会 401（游客），
      // 这种请求自己带 skipAuthRedirect，别弹「登录已过期」、也别跳登录页。
      if (error.config?.skipAuthRedirect) {
        return Promise.reject(error)
      }

      // 登录接口自己返回 401（账号密码错）时不该弹「登录已过期」
      if (router.currentRoute.value.path !== '/login') {
        showToast('登录已过期，请重新登录')
        router.push('/login')
      }
    } else if (!error.response) {
      // 请求根本没到达服务端：超时、断网、服务没起
      showToast('网络异常，请检查连接后重试')
    }

    return Promise.reject(error)
  }
)

export default http
