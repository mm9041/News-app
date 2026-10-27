<template>
  <div class="notice-page">
    <van-nav-bar title="消息通知" left-arrow fixed @click-left="goBack">
      <template #right>
        <span v-if="unread > 0" class="nav-action" @click="markAllRead">全部已读</span>
      </template>
    </van-nav-bar>

    <div class="list-area">
      <div
        v-for="item in list"
        :key="item.id"
        class="notice-item"
        :class="{ 'is-unread': !item.isRead }"
        @click="openItem(item)"
      >
        <van-image
          round
          width="36"
          height="36"
          class="notice-avatar"
          :src="item.actor.avatar || defaultAvatar"
        />
        <div class="notice-body">
          <div class="notice-line">
            <span class="actor">{{ item.actor.nickname || item.actor.username }}</span>
            <span class="action">{{ actionText(item.type) }}</span>
          </div>
          <div class="notice-news">{{ item.newsTitle }}</div>
          <div v-if="item.commentPreview" class="notice-comment">「{{ item.commentPreview }}」</div>
          <div class="notice-time">{{ formatTime(item.createdAt) }}</div>
        </div>
        <span v-if="!item.isRead" class="dot"></span>
      </div>

      <div v-if="hasMore" class="load-more" @click="load()">加载更多</div>
      <div v-else-if="loaded && !list.length" class="empty">
        <van-empty description="还没有收到通知" />
      </div>
    </div>

    <tab-bar />
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { showToast } from 'vant'

import http from '../api/http'
import TabBar from '../components/TabBar.vue'

const router = useRouter()

const PAGE_SIZE = 10
const defaultAvatar = 'https://fastly.jsdelivr.net/npm/@vant/assets/cat.jpeg'

const list = ref([])
const page = ref(1)
const unread = ref(0)
const loading = ref(false)
const hasMore = ref(false)
const loaded = ref(false)

// 同样不用 van-list：它会在触发 @load 前抢先置 loading，容易把自己挡死
let fetching = false

const goBack = () => router.back()

const formatTime = value => (value ? String(value).replace('T', ' ').slice(0, 16) : '')

const actionText = type => {
  if (type === 'comment') return '评论了你的新闻'
  if (type === 'like') return '赞了你的新闻'
  return '与你互动'
}

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
  loading.value = true
  try {
    const res = await http.get('/api/notification/list', {
      params: { page: page.value, pageSize: PAGE_SIZE }
    })
    const data = res.data?.data || {}

    list.value = page.value === 1 ? data.list || [] : [...list.value, ...(data.list || [])]
    unread.value = data.unread || 0
    hasMore.value = Boolean(data.hasMore)
    page.value += 1
  } catch (error) {
    // 拦截器已提示
  } finally {
    fetching = false
    loading.value = false
    loaded.value = true
  }
}

const openItem = async item => {
  if (!item.isRead) {
    try {
      await http.put(`/api/notification/${item.id}/read`)
      item.isRead = true
      unread.value = Math.max(0, unread.value - 1)
    } catch (error) {
      // 标记失败不影响跳转
    }
  }
  router.push(`/news/detail/${item.newsId}`)
}

const markAllRead = async () => {
  try {
    await http.put('/api/notification/read-all')
    list.value = list.value.map(item => ({ ...item, isRead: true }))
    unread.value = 0
    showToast('已全部标记为已读')
  } catch (error) {
    // 拦截器已提示
  }
}

onMounted(() => {
  hasMore.value = true
  load(true)
})
</script>

<style scoped>
.notice-page {
  padding-top: 46px;
  padding-bottom: 56px;
  min-height: 100vh;
  background-color: var(--background-color, #f7f8fa);
}

.nav-action {
  color: #1989fa;
  font-size: 14px;
}

.list-area {
  background-color: #fff;
}

.notice-item {
  position: relative;
  display: flex;
  gap: 10px;
  padding: 14px 16px;
  border-bottom: 1px solid #f2f3f5;
  background-color: #fff;
}

.notice-item.is-unread {
  background-color: #f7fbff;
}

.notice-avatar {
  flex-shrink: 0;
}

.notice-body {
  flex: 1;
  min-width: 0;
}

.notice-line {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 14px;
}

.actor {
  font-weight: 500;
  color: #323233;
}

.action {
  color: #646566;
}

.notice-news {
  margin-top: 4px;
  font-size: 13px;
  color: #1989fa;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.notice-comment {
  margin-top: 2px;
  font-size: 12px;
  color: #969799;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.notice-time {
  margin-top: 6px;
  font-size: 11px;
  color: #c8c9cc;
}

.dot {
  position: absolute;
  top: 18px;
  right: 14px;
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background-color: #ee0a24;
}

.load-more {
  padding: 14px 0;
  text-align: center;
  font-size: 13px;
  color: #1989fa;
  background-color: #fff;
}

.empty {
  padding: 20px 0;
  background-color: #fff;
}
</style>
