<template>
  <div class="follow-page">
    <van-nav-bar title="关注" left-arrow fixed @click-left="goBack" />

    <div class="panel">
      <div class="panel-title">关注的报纸</div>
      <div v-if="sources.length">
        <div v-for="source in sources" :key="source.id" class="author-row">
          <van-icon name="newspaper-o" size="26" class="source-icon" />
          <div class="author-info">
            <div class="author-name">{{ source.name }}</div>
            <div class="author-meta">{{ source.newsCount }} 条新闻</div>
          </div>
          <van-button size="mini" plain type="primary" @click="unfollow('source', source.id)">取关</van-button>
        </div>
      </div>
      <div v-else class="empty-text">还没有关注的报纸</div>
    </div>

    <div class="panel">
      <div class="panel-title">关注流</div>
      <div v-if="list.length">
        <news-item v-for="item in list" :key="item.id" :news="item" />
      </div>
      <van-empty v-else description="关注的作者/分类还没有新内容" image-size="60" />
    </div>

    <tab-bar />
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { showConfirmDialog, showToast } from 'vant'

import http from '../api/http'
import NewsItem from '../components/NewsItem.vue'
import TabBar from '../components/TabBar.vue'
import { useUserStore } from '../store/user'

const router = useRouter()
const userStore = useUserStore()
const defaultAvatar = 'https://fastly.jsdelivr.net/npm/@vant/assets/cat.jpeg'

const sources = ref([])
const list = ref([])

const goBack = () => router.back()

const loadAll = async () => {
  const [sourcesRes, feedRes] = await Promise.all([
    http.get('/api/follow/sources'),
    http.get('/api/follow/feed', { params: { page: 1, pageSize: 20 } }),
  ])
  sources.value = sourcesRes.data?.data || []
  list.value = feedRes.data?.data?.list || []
}

const unfollow = async (type, id) => {
  try {
    await showConfirmDialog({ title: '取消关注', message: '确定取消关注？' })
  } catch (error) {
    return
  }
  await http.delete('/api/follow', { data: { targetType: type, targetId: id } })
  sources.value = sources.value.filter(item => item.id !== id)
  showToast('已取消关注')
  loadAll()
}

onMounted(() => {
  if (!userStore.getLoginStatus) {
    showToast('请先登录')
    router.push('/login')
    return
  }
  loadAll()
})
</script>

<style scoped>
.follow-page {
  padding-top: 46px;
  padding-bottom: 56px;
  min-height: 100vh;
  background-color: var(--background-color, #f7f8fa);
}

.panel {
  margin: 12px;
  padding: 14px;
  background-color: #fff;
  border-radius: 10px;
}

.panel-title {
  font-size: 14px;
  font-weight: 500;
  margin-bottom: 12px;
}

.author-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 0;
}

.author-info {
  flex: 1;
}

.author-name {
  font-size: 14px;
  color: #323233;
}

.author-meta {
  font-size: 11px;
  color: #969799;
}

.empty-text {
  padding: 8px 0;
  font-size: 12px;
  color: #c8c9cc;
}
</style>
