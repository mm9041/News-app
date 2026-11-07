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
          <button type="button" class="search-action" @click="onSearch">搜索</button>
        </template>
      </van-search>

      <div v-if="showSuggest" class="suggest-panel">
        <div v-if="suggestions.news.length">
          <button
            v-for="item in suggestions.news"
            :key="item.id"
            type="button"
            class="suggest-item"
            @click="goToNews(item.id)"
          >
            <van-icon name="search" class="suggest-icon" />
            <span class="suggest-text">{{ item.title }}</span>
          </button>
        </div>
        <div v-if="suggestions.tags.length">
          <button
            v-for="tag in suggestions.tags"
            :key="tag.id"
            type="button"
            class="suggest-item"
            @click="goToTag(tag.id)"
          >
            <van-icon name="bookmark-o" class="suggest-icon" />
            <span class="suggest-text">#{{ tag.name }}</span>
          </button>
        </div>
        <div v-if="history.length">
          <div class="suggest-section">
            最近搜索
            <button type="button" class="suggest-clear" @click="clearHistory">清空</button>
          </div>
          <button
            v-for="word in history"
            :key="word"
            type="button"
            class="suggest-item"
            @click="useHistory(word)"
          >
            <van-icon name="clock-o" class="suggest-icon" />
            <span class="suggest-text">{{ word }}</span>
          </button>
        </div>
      </div>
    </div>

    <div class="result-area">
      <div v-if="searched && total > 0" class="result-meta" role="status" aria-live="polite">
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

      <div v-if="searched && loadError" class="result-error" role="alert">
        <span>{{ loadError }}</span>
        <van-button size="small" type="primary" plain @click="retrySearch">重试</van-button>
      </div>

      <van-empty
        v-if="searched && !loading && !loadError && !list.length"
        description="没有找到相关新闻"
      />
      <van-empty v-if="!searched" description="输入关键词，搜索标题和正文" />
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { showToast } from 'vant'

import http from '../api/http'
import NewsItem from '../components/NewsItem.vue'

const route = useRoute()
const router = useRouter()

const PAGE_SIZE = 10
const HISTORY_KEY = 'search_history'
const HISTORY_LIMIT = 10

const readHistory = () => {
  try {
    const saved = JSON.parse(localStorage.getItem(HISTORY_KEY) || '[]')
    return Array.isArray(saved) ? saved.filter(item => typeof item === 'string').slice(0, HISTORY_LIMIT) : []
  } catch (error) {
    return []
  }
}

const keyword = ref(route.query.keyword || '')
const submittedKeyword = ref('')
const list = ref([])
const total = ref(0)
const page = ref(1)
const loading = ref(false)
const finished = ref(false)
const searched = ref(false)
const loadError = ref('')
const history = ref(readHistory())
const suggestions = ref({ news: [], tags: [] })
const showSuggest = ref(false)

let debounceTimer = null
let searchRequestSeq = 0
let suggestRequestSeq = 0

const highlightKeyword = computed(() => submittedKeyword.value)

const goBack = () => router.back()

const onInput = () => {
  clearTimeout(debounceTimer)
  const kw = keyword.value.trim()
  const requestId = ++suggestRequestSeq

  if (!kw) {
    suggestions.value = { news: [], tags: [] }
    showSuggest.value = history.value.length > 0
    return
  }

  debounceTimer = setTimeout(async () => {
    try {
      const res = await http.get('/api/news/suggest', { params: { keyword: kw } })
      if (requestId !== suggestRequestSeq || kw !== keyword.value.trim()) return
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
  try {
    localStorage.setItem(HISTORY_KEY, JSON.stringify(next))
  } catch (error) {
    // 隐私模式或存储已满时仍保留当前会话内的搜索历史
  }
}

const clearHistory = () => {
  history.value = []
  try {
    localStorage.removeItem(HISTORY_KEY)
  } catch (error) {
    // 本地存储不可用时只清内存状态
  }
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
    // 新搜索立即让旧请求和旧联想失效，即使旧请求迟到也不会污染结果。
    searchRequestSeq += 1
    suggestRequestSeq += 1
    clearTimeout(debounceTimer)
    page.value = 1
    list.value = []
    loadError.value = ''
    finished.value = false
    searched.value = true
    submittedKeyword.value = kw
    showSuggest.value = false
    saveHistory(kw)
  } else if (loading.value || finished.value) {
    return
  }

  const requestId = reset ? searchRequestSeq : ++searchRequestSeq
  const requestedPage = page.value
  loading.value = true
  loadError.value = ''

  try {
    const res = await http.get('/api/news/search', {
      params: { keyword: kw, page: requestedPage, pageSize: PAGE_SIZE }
    })
    if (requestId !== searchRequestSeq) return

    const data = res.data?.data || {}
    const items = data.list || []
    list.value = [...list.value, ...items]
    total.value = data.total || 0
    finished.value = items.length < PAGE_SIZE
    page.value = requestedPage + 1
  } catch (error) {
    if (requestId === searchRequestSeq) {
      loadError.value = '搜索失败，请稍后重试'
      finished.value = false
    }
  } finally {
    if (requestId === searchRequestSeq) loading.value = false
  }
}

const onSearch = () => fetchPage(true)

const onClear = () => {
  searchRequestSeq += 1
  suggestRequestSeq += 1
  clearTimeout(debounceTimer)
  list.value = []
  total.value = 0
  loadError.value = ''
  searched.value = false
  finished.value = false
  submittedKeyword.value = ''
  loading.value = false
}

const retrySearch = () => fetchPage()

const loadMore = () => fetchPage()

const goToNews = id => router.push(`/news/detail/${id}`)
const goToTag = id => router.push(`/tag/${id}`)

const closeSuggestOnOutsideClick = event => {
  if (!event.target.closest('.search-bar')) {
    showSuggest.value = false
  }
}

onMounted(() => {
  document.addEventListener('click', closeSuggestOnOutsideClick)
  if (keyword.value.trim()) {
    fetchPage(true)
  }
})

onBeforeUnmount(() => {
  searchRequestSeq += 1
  suggestRequestSeq += 1
  clearTimeout(debounceTimer)
  document.removeEventListener('click', closeSuggestOnOutsideClick)
})
</script>

<style scoped>
.search-page {
  min-height: 100vh;
  min-height: 100dvh;
  padding-top: var(--nav-height);
  padding-bottom: calc(20px + var(--safe-area-inset-bottom));
  background-color: var(--background-color);
}

.search-bar {
  position: fixed;
  top: var(--nav-height);
  left: 50%;
  z-index: 99;
  width: 100%;
  max-width: var(--content-max-width);
  margin: 0 auto;
  background-color: var(--surface-color);
  transform: translateX(-50%);
}

.search-action {
  min-width: 44px;
  min-height: 44px;
  padding: 0 0 0 8px;
  border: 0;
  background: transparent;
  color: var(--primary-color);
  font-size: 14px;
  cursor: pointer;
}

.suggest-panel {
  padding-bottom: 8px;
  border-top: 1px solid var(--border-color);
  background-color: var(--surface-color);
}

.suggest-item {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  min-height: 44px;
  padding: 10px 16px;
  border: 0;
  background: transparent;
  color: var(--text-color);
  font-size: 13px;
  text-align: left;
  cursor: pointer;
}

.suggest-item:active {
  background-color: var(--surface-muted);
}

.suggest-icon {
  color: var(--text-color-lighter);
}

.suggest-text {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.suggest-section {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 16px 4px;
  color: var(--text-color-lighter);
  font-size: 12px;
}

.suggest-clear {
  min-width: 44px;
  min-height: 32px;
  padding: 0;
  border: 0;
  background: transparent;
  color: var(--text-color-light);
  cursor: pointer;
}

.result-area {
  margin-top: 54px;
}

.result-meta {
  padding: 8px 16px;
  color: var(--text-color-lighter);
  font-size: 12px;
}

.result-error {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  padding: 24px 16px;
  color: var(--text-color-light);
  font-size: 14px;
  text-align: center;
}
</style>
