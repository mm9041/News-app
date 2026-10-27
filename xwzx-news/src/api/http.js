import axios from 'axios'
import { showToast } from 'vant'

import { apiConfig } from '../config/api'
import router from '../router'

/**
 * 全局唯一的 axios 实例。
 *
 * 之前每个 store、每个页面都自己 `axios.get('http://127.0.0.1:8000/...')`，
 * 二十个调用点各自拼 baseURL、各自往 headers 里塞 token，结果是：
 * - 端口/域名一改要改二十处；
 * - 只有 AIChat 处理了 401，其它页面 token 过期后静默失败，界面还显示着"已登录"；
 * - 超时、重试、错误提示无从统一。
 */
const http = axios.create({
  baseURL: apiConfig.baseURL,
  timeout: 15000,
})

// token 由 main.js 注入：如果在模块顶层 import useUserStore，
// 会和 store/user.js -> api/http.js 形成循环依赖（且 pinia 尚未安装）。
let getToken = () => ''

export function bindTokenGetter(fn) {
  getToken = fn
}

// 401 时要做的事（清登录态）也由 main.js 注入，原因同上
let onUnauthorized = null

export function bindUnauthorizedHandler(fn) {
  onUnauthorized = fn
}

http.interceptors.request.use(
  (config) => {
    let token = ''
    try {
      token = getToken() || ''
    } catch (e) {
      token = ''
    }
    if (token) {
      config.headers = config.headers || {}
      // 后端 utils/auth.py 兼容裸 token 与 "Bearer xxx"
      config.headers.Authorization = token
    }
    return config
  },
  (error) => Promise.reject(error)
)

http.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error.response?.status

    if (status === 401) {
      onUnauthorized?.()

      // 登录接口自己返回 401（账号密码错）时不该弹"登录已过期"
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
