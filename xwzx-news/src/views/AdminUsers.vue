<template>
  <div class="users-page">
    <van-nav-bar title="用户管理" left-arrow fixed @click-left="goBack" />

    <div class="toolbar">
      <van-search v-model="keyword" placeholder="搜索用户名或昵称" shape="round" @search="reload" @clear="reload" />
    </div>

    <div class="list-area">
      <div v-for="user in list" :key="user.id" class="user-row">
        <van-image round width="40" height="40" :src="user.avatar || defaultAvatar" />
        <div class="user-info">
          <div class="user-name">
            {{ user.nickname || user.username }}
            <span v-if="user.isAdmin" class="badge badge-admin">管理员</span>
            <span v-if="user.banned" class="badge badge-banned">已禁用</span>
          </div>
          <div class="user-meta">
            @{{ user.username }} · {{ user.commentCount }} 条评论 · {{ formatTime(user.createdAt) }}
          </div>
        </div>
        <div class="user-actions">
          <van-button size="mini" plain :type="user.banned ? 'primary' : 'danger'" @click="toggleBan(user)">
            {{ user.banned ? '解禁' : '禁用' }}
          </van-button>
          <van-button size="mini" plain type="warning" @click="toggleAdmin(user)">
            {{ user.isAdmin ? '取消管理' : '设为管理' }}
          </van-button>
          <van-button size="mini" plain type="danger" @click="removeUser(user)">删除</van-button>
        </div>
      </div>

      <div v-if="hasMore" class="load-more" @click="load()">加载更多</div>
      <van-empty v-if="loaded && !list.length" description="没有匹配的用户" />
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { showConfirmDialog, showToast } from 'vant'

import http from '../api/http'
import { useUserStore } from '../store/user'

const router = useRouter()
const userStore = useUserStore()
const defaultAvatar = 'https://fastly.jsdelivr.net/npm/@vant/assets/cat.jpeg'

const PAGE_SIZE = 20
const keyword = ref('')
const list = ref([])
const total = ref(0)
const page = ref(1)
const hasMore = ref(false)
const loaded = ref(false)

let fetching = false

const formatTime = value => (value ? String(value).slice(0, 10) : '')

const goBack = () => router.back()

const load = async (reset = false) => {
  if (reset) {
    page.value = 1
    list.value = []
    hasMore.value = false
  }
  if (fetching) return

  fetching = true
  try {
    const res = await http.get('/api/admin/users', {
      params: {
        page: page.value,
        pageSize: PAGE_SIZE,
        keyword: keyword.value.trim() || undefined
      }
    })
    const data = res.data?.data || {}
    const items = data.list || []

    list.value = page.value === 1 ? items : [...list.value, ...items]
    total.value = data.total || 0
    hasMore.value = list.value.length < total.value
    page.value += 1
  } catch (error) {
    // 拦截器已提示
  } finally {
    fetching = false
    loaded.value = true
  }
}

const reload = () => load(true)

const toggleBan = async user => {
  const banning = !user.banned
  try {
    await showConfirmDialog({
      title: banning ? '禁用账号' : '解禁账号',
      message: banning ? '禁用后该用户将无法登录和发言，确定？' : '恢复该用户的访问权限？'
    })
  } catch (error) {
    return
  }

  try {
    await http.patch(`/api/admin/users/${user.id}`, { banned: banning })
    user.banned = banning
    showToast(banning ? '已禁用' : '已解禁')
  } catch (error) {
    // 拦截器已提示
  }
}

const toggleAdmin = async user => {
  const granting = !user.isAdmin
  try {
    await showConfirmDialog({
      title: granting ? '授予管理员' : '取消管理员',
      message: granting ? '该用户将可以管理新闻和用户' : '该用户将失去管理后台权限'
    })
  } catch (error) {
    return
  }

  try {
    await http.patch(`/api/admin/users/${user.id}`, { isAdmin: granting })
    user.isAdmin = granting
    showToast('已更新')
  } catch (error) {
    // 拦截器已提示
  }
}

const removeUser = async user => {
  try {
    await showConfirmDialog({
      title: '删除用户',
      message: `将删除 @${user.username} 及其全部评论/点赞/收藏，不可恢复！`
    })
  } catch (error) {
    return
  }

  try {
    await http.delete(`/api/admin/users/${user.id}`)
    list.value = list.value.filter(item => item.id !== user.id)
    showToast('已删除')
  } catch (error) {
    // 拦截器已提示
  }
}

onMounted(() => {
  load(true)
})
</script>

<style scoped>
.users-page {
  padding-top: 46px;
  padding-bottom: 20px;
  min-height: 100vh;
  background-color: #f7f8fa;
}

.toolbar {
  position: fixed;
  top: 46px;
  left: 0;
  right: 0;
  z-index: 99;
  max-width: 750px;
  margin: 0 auto;
  background-color: #fff;
}

.list-area {
  margin-top: 54px;
  background-color: #fff;
}

.user-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 16px;
  border-bottom: 1px solid #f7f8fa;
}

.user-info {
  flex: 1;
  min-width: 0;
}

.user-name {
  font-size: 14px;
  color: #323233;
  display: flex;
  align-items: center;
  gap: 6px;
}

.badge {
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 4px;
}

.badge-admin {
  color: #1989fa;
  background-color: #e6f1fb;
}

.badge-banned {
  color: #ee0a24;
  background-color: #fcebeb;
}

.user-meta {
  margin-top: 2px;
  font-size: 11px;
  color: #c8c9cc;
}

.user-actions {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.load-more {
  padding: 14px 0;
  text-align: center;
  font-size: 13px;
  color: #1989fa;
}
</style>
