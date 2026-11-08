<template>
  <div class="app">
    <router-view v-slot="{ Component }">
      <keep-alive :include="keepAliveNames">
        <component :is="Component" />
      </keep-alive>
    </router-view>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useNotificationStore } from './store/notification'
import { useUserStore } from './store/user'

// 只缓存 meta.keepAlive 的页面，其余页面每次进入都重建（数据才不会是旧的）。
//
// ⚠️ 千万不要把 <keep-alive> 放进 v-if 里（比如 v-if="$route.meta.keepAlive"）。
// 那样一旦跳到不缓存的页面，keep-alive 组件**本身**会被卸载，它缓存的所有实例一起被销毁 ——
// 回到原页面时是重新挂载的，本地状态全丢。典型表现：从新闻详情返回首页，
// 顶部的分类标签跳回第一个（头条），而 store 里的当前分类其实没变，两边对不上。
// 正确做法是 keep-alive 常驻，用 include 决定缓存谁。
//
// include 匹配的是**组件名**。这些页面都是 <script setup> 单文件组件，
// 编译器会按文件名注入 __name，而文件名与路由 name 一致，所以这里直接用路由 name。
const router = useRouter()
const keepAliveNames = computed(() =>
  router.getRoutes()
    .filter((route) => route.meta?.keepAlive && route.name)
    .map((route) => route.name)
)

// 登录/恢复会话后立即同步未读通知；退出时立刻清掉红色数字。
// 没有 WebSocket，因此登录期间每 60 秒轻量刷新一次，页面切换时也会补拉。
const userStore = useUserStore()
const notificationStore = useNotificationStore()
let unreadTimer = null
watch(
  () => userStore.isLogin,
  loggedIn => {
    if (unreadTimer) {
      clearInterval(unreadTimer)
      unreadTimer = null
    }
    if (loggedIn) {
      notificationStore.refreshUnread(true)
      unreadTimer = setInterval(() => notificationStore.refreshUnread(true), 60_000)
    } else {
      notificationStore.clear()
    }
  },
  { immediate: true }
)

watch(
  () => router.currentRoute.value.path,
  () => {
    if (userStore.isLogin) notificationStore.refreshUnread()
  }
)

onBeforeUnmount(() => {
  if (unreadTimer) clearInterval(unreadTimer)
})
</script>

<style>
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

html,
body {
  font-family: inherit;
  font-size: 16px;
  background-color: var(--background-color);
  color: var(--text-color);
  height: 100%;
  width: 100%;
}

.app {
  width: 100%;
  max-width: var(--content-max-width);
  min-height: 100vh;
  min-height: 100dvh;
  margin: 0 auto;
  background-color: var(--background-color);
}
</style>
