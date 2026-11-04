import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue()],
  server: {
    // 把 /api 和 /uploads 反代到后端，开发时前后端**同源**。
    //
    // 为什么必须这么做：登录 token 现在放在 httpOnly cookie 里，SameSite=Lax。
    // 如果前端跑在 localhost:5173、直接请求 127.0.0.1:8000，浏览器会认为是两个站点，
    // 跨站请求不会带上 cookie —— 表现为"登录成功但下一个请求就是 401"。
    // 走代理后就只有 5173 一个源，cookie 正常生效，也顺带绕开了 CORS。
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      '/uploads': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
})
