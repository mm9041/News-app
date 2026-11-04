/**
 * API配置文件
 * 包含API基础URL和AI问答功能的接口地址
 */

// 默认走**相对路径**：开发时由 vite 的 server.proxy 反代到 127.0.0.1:8000，
// 生产由 nginx 反代到 backend:8000。
// 这样前后端同源，httpOnly cookie 才能被正常带上（跨站请求不会发 Lax cookie）。
// Docker 构建时显式设成空串 VITE_API_BASE_URL=，同样走相对路径。
// （用 ?? 而不是 ||：空串是有效值，不能被当成「没配置」）
export const apiConfig = {
  baseURL: import.meta.env.VITE_API_BASE_URL ?? '',
}

export const aiChatConfig = {
  // 统一走后端代理，API Key 由后端 .env 提供
  // 千万不要把 Key 写回这里 —— 前端打包产物任何访客都能抓走
  chatEndpoint: `${apiConfig.baseURL}/api/ai/chat`,
}
