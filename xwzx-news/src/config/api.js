/**
 * API配置文件
 * 包含API基础URL和AI问答功能的接口地址
 */

// API基础URL配置
// 部署时在 xwzx-news/.env 里写 VITE_API_BASE_URL=https://api.example.com 覆盖，
// 不用再去改代码。本地开发保持回落到 127.0.0.1:8000。
export const apiConfig = {
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000',
}

export const aiChatConfig = {
  // 统一走后端代理，API Key 由后端 .env 提供
  // 千万不要把 Key 写回这里 —— 前端打包产物任何访客都能抓走
  chatEndpoint: `${apiConfig.baseURL}/api/ai/chat`,
}
