import { defineStore } from 'pinia'

import http from '../api/http'
import { useUserStore } from './user'

const REFRESH_INTERVAL = 15_000

export const useNotificationStore = defineStore('notification', {
  state: () => ({
    unreadCount: 0,
    loading: false,
    lastFetchedAt: 0,
  }),

  getters: {
    hasUnread: state => state.unreadCount > 0,
    badgeText: state => {
      if (state.unreadCount <= 0) return ''
      return state.unreadCount > 99 ? '99+' : String(state.unreadCount)
    },
  },

  actions: {
    setUnreadCount(count) {
      this.unreadCount = Math.max(0, Number(count) || 0)
      this.lastFetchedAt = Date.now()
    },

    decrementUnread(step = 1) {
      this.unreadCount = Math.max(0, this.unreadCount - step)
    },

    clear() {
      this.unreadCount = 0
      this.loading = false
      this.lastFetchedAt = 0
    },

    /**
     * 拉取当前用户未读数。force=false 时 15 秒内复用上次结果，
     * 避免 TabBar、App 和「我的」页在同一轮激活里重复请求。
     */
    async refreshUnread(force = false) {
      const userStore = useUserStore()
      if (!userStore.getLoginStatus) {
        this.clear()
        return 0
      }
      if (this.loading) return this.unreadCount
      if (!force && Date.now() - this.lastFetchedAt < REFRESH_INTERVAL) {
        return this.unreadCount
      }

      this.loading = true
      try {
        const res = await http.get('/api/notification/unread-count', {
          skipAuthRedirect: true,
        })
        this.setUnreadCount(res.data?.data?.count)
        return this.unreadCount
      } catch (error) {
        // 会话失效时由全局拦截器清登录态；这里只保证不展示过期数字。
        if (error.response?.status === 401) this.clear()
        return this.unreadCount
      } finally {
        this.loading = false
      }
    },
  },
})
