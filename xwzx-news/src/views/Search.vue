<template>
  <div class="search-page">
    <van-nav-bar title="搜索" left-arrow fixed @click-left="goBack" />

    <div class="search-bar">
      <van-search
        v-model="keyword"
        placeholder="搜索标题或正文"
        shape="round"
        show-action
        @search="onSearch"
        @clear="onClear"
      >
        <template #action>
          <div class="search-action" @click="onSearch">搜索</div>
        </template>
      </van-search>
    </div>

    <div class="result-area">
      <div v-if="searched && total > 0" class="result-meta">
        找到 {{ total }} 条相关新闻
      </div>

      <van-list
        v-if="searched"
        v-model:loading="loading"
        :finished="finished"
        :immediate-check="false"
        finished-text="没有更多了"
        @load="loadMore"
      >
        <news-item v-for="item in list" :key="item.id" :news="item" />
      </van-list>

      <van-empty v-if="searched && !loading && !list.length" description="没有找到相关新闻" />
      <van-empty v-if="!searched" description="输入关键词，搜索标题和正文" />
    </div>

    <tab-bar />
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { showToast } from 'vant'

import http from '../api/http'
import NewsItem from '../components/NewsItem.vue'
import TabBar from '../components/TabBar.vue'

const route = useRoute()
const router = useRouter()

const PAGE_SIZE = 10

const keyword = ref(route.query.keyword || '')
const list = ref([])
const total = ref(0)
const page = ref(1)
const loading = ref(false)
const finished = ref(false)
const searched = ref(false)

// ⚠️ `loading` 会被 van-list 在触发 @load 之前抢先置为 true，
// 拿它当并发守卫会导致第一次触底就 return 且不再复位 —— 一直显示「加载中」。
// 用独立标志 + 请求序号（丢弃重置时仍在飞行的旧响应）。
let fetching = false
let requestSeq = 0

const goBack = () => router.back()

const fetchPage = async (reset = false) => {
  const kw = keyword.value.trim()
  if (!kw) {
    showToast('请输入关键词')
    return
  }

  if (reset) {
    page.value = 1
    list.value = []
    finished.value = false
    searched.value = true
    fetching = false
    requestSeq += 1
  }

  if (fetching || finished.value) {
    loading.value = false
    return
  }

  fetching = true
  loading.value = true
  const seq = ++requestSeq

  try {
    const res = await http.get('/api/news/search', {
      params: { keyword: kw, page: page.value, pageSize: PAGE_SIZE }
    })
    if (seq !== requestSeq) return

    const data = res.data?.data || {}
    const items = data.list || []
    const totalCount = data.total || 0

    list.value = [...list.value, ...items]
    total.value = totalCount
    finished.value = list.value.length >= totalCount || items.length < PAGE_SIZE
    page.value += 1
  } catch (error) {
    // 具体错误提示由 http 拦截器统一处理，这里只需要停止继续加载
    if (seq === requestSeq) finished.value = true
  } finally {
    if (seq === requestSeq) {
      fetching = false
      loading.value = false
    }
  }
}

const onSearch = () => fetchPage(true)

const onClear = () => {
  list.value = []
  total.value = 0
  searched.value = false
  finished.value = false
}

const loadMore = () => fetchPage()

onMounted(() => {
  // 支持 /search?keyword=xxx 直接进结果页
  if (keyword.value.trim()) {
    fetchPage(true)
  }
})
</script>

<style scoped>
.search-page {
  padding-top: 46px;
  padding-bottom: 50px;
  min-height: 100vh;
  background-color: var(--background-color, #f7f8fa);
}

.search-bar {
  position: fixed;
  top: 46px;
  left: 0;
  right: 0;
  z-index: 99;
  max-width: 750px;
  margin: 0 auto;
  background-color: #fff;
}

.search-action {
  color: #1989fa;
  font-size: 14px;
  padding-left: 8px;
}

.result-area {
  margin-top: 54px;
}

.result-meta {
  padding: 8px 16px;
  font-size: 12px;
  color: #969799;
}
</style>
