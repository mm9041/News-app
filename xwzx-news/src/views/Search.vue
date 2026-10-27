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
        @focus="onFocus"
        @input="onInput"
      >
        <template #action>
          <div class="search-action" @click="onSearch">搜索</div>
        </template>
      </van-search>

      <div v-if="showSuggest" class="suggest-panel">
        <div v-if="suggestions.news.length">
          <div
            v-for="item in suggestions.news"
            :key="item.id"
            class="suggest-item"
            @click="goToNews(item.id)"
          >
            <van-icon name="search" class="suggest-icon" />
            <span class="suggest-text">{{ item.title }}</span>
          </div>
        </div>
        <div v-if="suggestions.tags.length">
          <div
            v-for="tag in suggestions.tags"
            :key="tag.id"
            class="suggest-item"
            @click="goToTag(tag.id)"
          >
            <van-icon name="bookmark-o" class="suggest-icon" />
            <span class="suggest-text">#{{ tag.name }}</span>
          </div>
        </div>
        <div v-if="history.length">
          <div class="suggest-section">
            最近搜索
            <span class="suggest-clear" @click="clearHistory">清空</span>
          </div>
          <div
            v-for="word in history"
            :key="word"
            class="suggest-item"
            @click="useHistory(word)"
          >
            <van-icon name="clock-o" class="suggest-icon" />
            <span class="suggest-text">{{ word }}</span>
          </div>
        </div>
      </div>
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
        <news-item
          v-for="item in list"
          :key="item.id"
          :news="item"
          :keyword="highlightKeyword"
        />
      </van-list>

      <van-empty v-if="searched && !loading && !list.length" description="没有找到相关新闻" />
      <van-empty v-if="!searched" description="输入关键词，搜索标题和正文" />
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

const route = useRoute()
const router = useRouter()

const PAGE_SIZE = 10
const HISTORY_KEY = 'search_history'
const HISTORY_LIMIT = 10

const keyword = ref(route.query.keyword || '')
const list = ref([])
const total = ref(0)
const page = ref(1)
const loading = ref(false)
const finished = ref(false)
const searched = ref(false)
const history = ref(JSON.parse(localStorage.getItem(HISTORY_KEY) || '[]'))
const suggestions = ref({ news: [], tags: [] })
const showSuggest = ref(false)

const highlightKeyword = computed(() => (searched.value ? keyword.value.trim() : ''))

const goBack = () => router.back()

let debounceTimer = null
const onInput = () => {
  clearTimeout(debounceTimer)
  const kw = keyword.value.trim()
  if (!kw) {
    suggestions.value = { news: [], tags: [] }
    showSuggest.value = history.value.length > 0
    return
  }
  debounceTimer = setTimeout(async () => {
    try {
      const res = await http.get('/api/news/suggest', { params: { keyword: kw } })
      suggestions.value = res.data?.data || { news: [], tags: [] }
      showSuggest.value = true
    } catch (error) {
      // 联想失败不影响主流程
    }
  }, 300)
}

const onFocus = () => {
  if (showSuggest.value) return
  showSuggest.value = suggestions.value.news.length > 0 || history.value.length > 0
}

const saveHistory = word => {
  const next = [word, ...history.value.filter(item => item !== word)].slice(0, HISTORY_LIMIT)
  history.value = next
  localStorage.setItem(HISTORY_KEY, JSON.stringify(next))
}

const clearHistory = () => {
  history.value = []
  localStorage.removeItem(HISTORY_KEY)
  showSuggest.value = false
}

const useHistory = word => {
  keyword.value = word
  showSuggest.value = false
  fetchPage(true)
}

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
    showSuggest.value = false
    saveHistory(kw)
  }

  if (loading.value || finished.value) return

  loading.value = true
  try {
    const res = await http.get('/api/news/search', {
      params: { keyword: kw, page: page.value, pageSize: PAGE_SIZE }
    })
    const data = res.data?.data || {}
    const items = data.list || []

    list.value = [...list.value, ...items]
    total.value = data.total || 0
    finished.value = items.length < PAGE_SIZE
    page.value += 1
  } catch (error) {
    finished.value = true
  } finally {
    loading.value = false
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

const goToNews = id => router.push(`/news/detail/${id}`)
const goToTag = id => router.push(`/tag/${id}`)

// 点击页面其他区域收起联想面板
watch(showSuggest, visible => {
  if (!visible) return
  const close = () => {
    showSuggest.value = false
    document.removeEventListener('click', close)
  }
  setTimeout(() => document.addEventListener('click', close), 0)
})

onMounted(() => {
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

.suggest-panel {
  border-top: 1px solid #f2f3f5;
  background-color: #fff;
  padding-bottom: 8px;
}

.suggest-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 16px;
  font-size: 13px;
  color: #323233;
}

.suggest-icon {
  color: #c8c9cc;
}

.suggest-text {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.suggest-section {
  display: flex;
  justify-content: space-between;
  padding: 8px 16px 4px;
  font-size: 12px;
  color: #969799;
}

.suggest-clear {
  color: #c8c9cc;
}

.result-area {
  margin-top: 54px;
}

.result-meta {
  padding: 8px 16px;
  font-size: 12px;
  color: #969799;
}

:deep(mark) {
  background-color: #fff3cd;
  color: inherit;
  padding: 0 1px;
}
</style>
