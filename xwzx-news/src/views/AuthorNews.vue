<template>
  <div class="author-page">
    <van-nav-bar :title="title" left-arrow fixed @click-left="goBack">
      <template #right>
        <span
          class="nav-follow"
          :class="{ 'is-following': isFollowing }"
          @click="toggleFollow"
        >
          {{ isFollowing ? '已关注' : '+ 关注' }}
        </span>
      </template>
    </van-nav-bar>

    <div class="list-area">
      <news-item v-for="item in list" :key="item.id" :news="item" />

      <div v-if="hasMore" class="load-more" @click="load()">加载更多</div>
      <div v-else-if="loaded && !list.length" class="empty">
        <van-empty description="该作者下还没有新闻" />
      </div>
      <div v-else-if="loaded" class="load-more load-end">没有更多了</div>
    </div>

    <tab-bar />
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { showToast } from 'vant'

import http from '../api/http'
import NewsItem from '../components/NewsItem.vue'
import TabBar from '../components/TabBar.vue'
import { useUserStore } from '../store/user'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

const PAGE_SIZE = 10

const list = ref([])
const page = ref(1)
const isFollowing = ref(false)
const hasMore = ref(false)
const loaded = ref(false)

let fetching = false
let followLoading = false

const authorName = computed(() => route.params.name || '')
const title = computed(() => authorName.value || '作者')

const goBack = () => router.back()

const load = async (reset = false) => {
  if (reset) {
    page.value = 1
    list.value = []
    hasMore.value = false
  } else if (!hasMore.value && page.value > 1) {
    return
  }
  if (fetching) return

  fetching = true
  try {
    const res = await http.get('/api/follow/news', {
      params: { name: authorName.value, page: page.value, pageSize: PAGE_SIZE }
    })
    const data = res.data?.data || {}
    const items = data.list || []

    list.value = page.value === 1 ? items : [...list.value, ...items]
    hasMore.value = Boolean(data.hasMore)
    page.value += 1
  } catch (error) {
    // 拦截器已提示
  } finally {
    fetching = false
    loaded.value = true
  }
}

const loadFollowState = async () => {
  if (!userStore.getLoginStatus) return
  try {
    const res = await http.get('/api/follow/status', {
      params: { name: authorName.value }
    })
    isFollowing.value = Boolean(res.data?.data?.following)
  } catch (error) {
    isFollowing.value = false
  }
}

const toggleFollow = async () => {
  if (!userStore.getLoginStatus) {
    showToast('请先登录')
    router.push('/login')
    return
  }
  if (followLoading) return

  followLoading = true
  try {
    if (isFollowing.value) {
      await http.delete('/api/follow', { params: { name: authorName.value } })
      isFollowing.value = false
      showToast('已取消关注')
    } else {
      await http.post('/api/follow', null, { params: { name: authorName.value } })
      isFollowing.value = true
      showToast('已关注作者')
    }
  } catch (error) {
    // 拦截器已提示
  } finally {
    followLoading = false
  }
}

onMounted(() => {
  hasMore.value = true
  load(true).then(loadFollowState)
})

watch(
  () => route.params.name,
  (newName, oldName) => {
    if (newName && newName !== oldName) {
      window.scrollTo(0, 0)
      isFollowing.value = false
      load(true).then(loadFollowState)
    }
  }
)
</script>

<style scoped>
.author-page {
  padding-top: 46px;
  padding-bottom: 56px;
  min-height: 100vh;
  background-color: var(--background-color, #f7f8fa);
}

.nav-follow {
  font-size: 13px;
  color: #1989fa;
}

.nav-follow.is-following {
  color: #969799;
}

.list-area {
  background-color: #fff;
}

.load-more {
  padding: 14px 0;
  text-align: center;
  font-size: 13px;
  color: #1989fa;
}

.load-end {
  color: #c8c9cc;
}

.empty {
  padding: 20px 0;
}
</style>
