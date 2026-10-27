<template>
  <div class="follow-page">
    <van-nav-bar title="我的关注" left-arrow fixed @click-left="goBack" />

    <div class="panel">
      <div class="panel-title">关注的作者</div>
      <div v-if="authors.length">
        <div
          v-for="author in authors"
          :key="author.name"
          class="author-row"
          @click="goToAuthor(author.name)"
        >
          <van-icon name="user-o" size="24" class="author-icon" />
          <div class="author-info">
            <div class="author-name">{{ author.name }}</div>
            <div class="author-meta">{{ author.newsCount }} 条新闻</div>
          </div>
          <van-icon name="arrow" class="row-arrow" />
          <van-button size="mini" plain type="primary" @click.stop="unfollow(author.name)">
            取关
          </van-button>
        </div>
      </div>
      <div v-else class="empty-text">还没有关注的作者</div>
    </div>

    <tab-bar />
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { showConfirmDialog, showToast } from 'vant'

import http from '../api/http'
import TabBar from '../components/TabBar.vue'
import { useUserStore } from '../store/user'

const router = useRouter()
const userStore = useUserStore()

const authors = ref([])

const goBack = () => router.back()

const loadAll = async () => {
  const res = await http.get('/api/follow/authors')
  authors.value = res.data?.data || []
}

const goToAuthor = name => router.push(`/author/${encodeURIComponent(name)}`)

const unfollow = async name => {
  try {
    await showConfirmDialog({ title: '取消关注', message: `不再关注「${name}」？` })
  } catch (error) {
    return
  }
  await http.delete('/api/follow', { params: { name } })
  authors.value = authors.value.filter(item => item.name !== name)
  showToast('已取消关注')
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
  padding: 10px 0;
}

.author-icon {
  color: #1989fa;
}

.author-info {
  flex: 1;
  min-width: 0;
}

.author-name {
  font-size: 14px;
  color: #323233;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.author-meta {
  font-size: 11px;
  color: #969799;
}

.row-arrow {
  color: #c8c9cc;
  flex-shrink: 0;
}

.empty-text {
  padding: 8px 0;
  font-size: 12px;
  color: #c8c9cc;
}
</style>
