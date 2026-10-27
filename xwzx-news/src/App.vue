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
import { computed } from 'vue'
import { useRouter } from 'vue-router'

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
</script>

<style>
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

html, body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen,
    Ubuntu, Cantarell, 'Open Sans', 'Helvetica Neue', sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  font-size: 16px;
  background-color: #f7f8fa;
  color: #333;
  height: 100%;
  width: 100%;
}

.app {
  max-width: 750px;
  margin: 0 auto;
  height: 100%;
}

/* 移动端适配 */
@media screen and (max-width: 750px) {
  html {
    font-size: calc(100vw / 750 * 16);
  }
}
</style>
