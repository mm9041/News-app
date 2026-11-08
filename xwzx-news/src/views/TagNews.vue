<template>
  <div class="tag-page">
    <van-nav-bar :title="title" left-arrow fixed @click-left="goBack" />

    <div class="list-area">
      <news-item v-for="item in list" :key="item.id" :news="item" />

      <div v-if="hasMore" class="load-more" @click="load()">{{ $t('common.loadMore') }}</div>
      <div v-else-if="loaded && !list.length" class="empty">
        <van-empty :description="$t('tag.empty')" />
      </div>
      <div v-else-if="loaded" class="load-more load-end">{{ $t('common.noMore') }}</div>
    </div>

    <tab-bar />
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'

import http from '../api/http'
import NewsItem from '../components/NewsItem.vue'
import TabBar from '../components/TabBar.vue'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()

const PAGE_SIZE = 10

const list = ref([])
const page = ref(1)
const tagName = ref('')
const hasMore = ref(false)
const loaded = ref(false)

let fetching = false

const title = computed(() => (tagName.value ? `#${tagName.value}` : t('tag.fallback')))

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
    const res = await http.get(`/api/tag/${route.params.id}/news`, {
      params: { page: page.value, pageSize: PAGE_SIZE }
    })
    const data = res.data?.data || {}
    const items = data.list || []

    list.value = page.value === 1 ? items : [...list.value, ...items]
    tagName.value = data.tag?.name || tagName.value
    hasMore.value = Boolean(data.hasMore)
    page.value += 1
  } catch (error) {
    // 拦截器已提示
  } finally {
    fetching = false
    loaded.value = true
  }
}

onMounted(() => {
  hasMore.value = true
  load(true)
})

// 从详情页点另一个标签时组件会复用，需要重新加载
watch(
  () => route.params.id,
  (newId, oldId) => {
    if (newId && newId !== oldId) {
      window.scrollTo(0, 0)
      load(true)
    }
  }
)
</script>

<style scoped>
.tag-page {
  padding-top: 46px;
  padding-bottom: 56px;
  min-height: 100vh;
  background-color: var(--background-color, #f7f8fa);
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
