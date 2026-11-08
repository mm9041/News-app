<template>
  <div class="follow-page">
    <van-nav-bar :title="$t('follow.title')" left-arrow fixed @click-left="goBack" />

    <div class="panel">
      <div class="panel-title">{{ $t('follow.authorsTitle') }}</div>
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
            <div class="author-meta">{{ $t('common.newsCount', { count: author.newsCount }) }}</div>
          </div>
          <van-icon name="arrow" class="row-arrow" />
          <van-button size="mini" plain type="primary" @click.stop="unfollow(author.name)">
            {{ $t('follow.unfollow') }}
          </van-button>
        </div>
      </div>
      <div v-else class="empty-text">{{ $t('follow.empty') }}</div>
    </div>

    <tab-bar />
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { showConfirmDialog, showToast } from 'vant'
import { useI18n } from 'vue-i18n'

import http from '../api/http'
import TabBar from '../components/TabBar.vue'
import { useUserStore } from '../store/user'

const router = useRouter()
const userStore = useUserStore()
const { t } = useI18n()

const authors = ref([])

const goBack = () => router.back()

const loadAll = async () => {
  const res = await http.get('/api/follow/authors')
  authors.value = res.data?.data || []
}

const goToAuthor = name => router.push(`/author/${encodeURIComponent(name)}`)

const unfollow = async name => {
  try {
    await showConfirmDialog({
      title: t('follow.confirmTitle'),
      message: t('follow.confirmMessage', { name })
    })
  } catch (error) {
    return
  }
  await http.delete('/api/follow', { params: { name } })
  authors.value = authors.value.filter(item => item.name !== name)
  showToast(t('follow.unfollowed'))
}

onMounted(() => {
  if (!userStore.getLoginStatus) {
    showToast(t('common.loginRequired'))
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
  color: var(--primary-color);
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
  color: var(--icon-color-muted);
  flex-shrink: 0;
}

.empty-text {
  padding: 8px 0;
  font-size: 12px;
  color: #c8c9cc;
}
</style>
