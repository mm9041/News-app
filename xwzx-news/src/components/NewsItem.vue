<template>
  <article
    class="news-item"
    role="link"
    tabindex="0"
    :aria-label="$t('detail.readArticle', { title: news.title })"
    @click="goToDetail"
    @keydown.enter.prevent="goToDetail"
    @keydown.space.prevent="goToDetail"
  >
    <div class="news-content">
      <h3 class="news-title">
        <template v-for="(part, index) in titleParts" :key="index">
          <mark v-if="part.highlight">{{ part.text }}</mark>
          <template v-else>{{ part.text }}</template>
        </template>
      </h3>
      <p v-if="news.description" class="news-desc">{{ news.description }}</p>
      <div class="news-info">
        <span>{{ news.author }}</span>
        <span>{{ news.publishTime }}</span>
        <span>{{ $t('common.views', { count: news.views }) }}</span>
      </div>
    </div>
    <div v-if="news.image" class="news-image">
      <img
        :src="news.image"
        :alt="news.title"
        width="110"
        height="80"
        loading="lazy"
        decoding="async"
        @error="onImageError"
      >
    </div>
  </article>
</template>

<script setup>
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { onImageError } from '../config/image'

const props = defineProps({
  news: {
    type: Object,
    required: true
  },
  keyword: {
    type: String,
    default: ''
  }
})

// 直接渲染文本节点而不是 v-html：标题即使来自外部内容也不会被解析成 HTML。
const titleParts = computed(() => {
  const title = props.news.title || ''
  const keyword = (props.keyword || '').trim()
  if (!keyword) return [{ text: title, highlight: false }]

  const pattern = keyword.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  return title
    .split(new RegExp(`(${pattern})`, 'gi'))
    .filter(Boolean)
    .map((text, index) => ({ text, highlight: index % 2 === 1 }))
})

const router = useRouter()

const goToDetail = () => {
  router.push(`/news/detail/${props.news.id}`)
}
</script>

<style scoped>
.news-item {
  display: flex;
  min-height: 106px;
  padding: 12px 16px;
  border-bottom: 1px solid var(--border-color);
  background-color: var(--surface-color);
  color: var(--text-color);
  cursor: pointer;
  transition: background-color 0.2s ease;
}

.news-item:active {
  background-color: var(--surface-muted);
}

.news-content {
  flex: 1;
  min-width: 0;
  margin-right: 12px;
  overflow: hidden;
}

.news-title {
  font-size: 16px;
  font-weight: 500;
  margin: 0 0 8px;
  line-height: 1.4;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

.news-desc {
  font-size: 14px;
  color: var(--text-color-light);
  margin: 0 0 8px;
  line-height: 1.4;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

.news-info {
  display: flex;
  flex-wrap: wrap;
  gap: 2px 10px;
  font-size: 12px;
  color: var(--text-color-lighter);
}

.news-info span {
  min-width: 0;
}

.news-title mark {
  padding: 0 1px;
  color: inherit;
  background-color: #fff3cd;
}

.news-image {
  width: 110px;
  height: 80px;
  flex-shrink: 0;
}

.news-image img {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: cover;
  border-radius: 6px;
  background-color: var(--surface-muted);
}

@media (max-width: 380px) {
  .news-item {
    padding: 12px;
  }

  .news-image {
    width: 96px;
    height: 72px;
  }
}
</style>