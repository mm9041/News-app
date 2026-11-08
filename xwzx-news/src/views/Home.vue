<template>
  <div class="home">
    <van-nav-bar :title="$t('home.title')" fixed>
      <template #right>
        <button type="button" class="nav-search" :aria-label="$t('home.searchAria')" @click="goSearch">
          <van-icon name="search" size="20" />
        </button>
      </template>
    </van-nav-bar>
    
    <div class="recommend-section" v-if="newsStore.recommendations.length">
      <div class="recommend-header">{{ $t('home.recommended') }}</div>
      <div class="recommend-scroll">
        <button
          v-for="item in newsStore.recommendations"
          :key="item.id"
          type="button"
          class="recommend-card"
          @click="goToNews(item.id)"
        >
          <img
            :src="item.image"
            :alt="item.title"
            width="120"
            height="78"
            loading="lazy"
            decoding="async"
            @error="onImageError"
          >
          <span class="recommend-title">{{ item.title }}</span>
        </button>
      </div>
    </div>

    <div class="category-tabs">
      <div class="category-sticky">
        <van-tabs v-model:active="activeTab">
          <van-tab
            v-for="category in displayCategories"
            :key="category.id"
            :title="getCategoryTranslation(category.name)"
          />
        </van-tabs>
        <button type="button" class="more-tab" @click="goToCategory">
          {{ $t('home.more') }} <van-icon name="arrow" />
        </button>
      </div>

      <!-- 所有分类共用同一份列表，避免每个 Tab 复制 DOM、图片和加载监听器。 -->
      <van-pull-refresh v-model="newsStore.refreshing" @refresh="onRefresh">
        <van-list
          v-model:loading="newsStore.loading"
          :finished="newsStore.finished"
          :finished-text="$t('home.noMore')"
          :immediate-check="false"
          @load="onLoad"
        >
          <news-item
            v-for="item in newsStore.newsList"
            :key="item.id"
            :news="item"
          />
        </van-list>
      </van-pull-refresh>
    </div>
    
    <tab-bar />
  </div>
</template>

<script setup>
import { ref, onMounted, onActivated, watch, computed, nextTick } from 'vue'
import { useNewsStore } from '../store/modules/news'
import { useUserStore } from '../store/user'
import { useRouter, useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import NewsItem from '../components/NewsItem.vue'
import TabBar from '../components/TabBar.vue'
import { onImageError } from '../config/image'

const newsStore = useNewsStore()
const userStore = useUserStore()
const router = useRouter()
const route = useRoute()
const { t } = useI18n()
const activeTab = ref(0)

// 显示的分类：排除「更多」这个仅用于跳转的伪分类。
const displayCategories = computed(() =>
  newsStore.categories.filter(category => category.name !== '更多')
)

const syncCategoryFromRoute = () => {
  const categoryId = Number(route.query.categoryId)
  if (!categoryId || !displayCategories.value.length) return

  const index = displayCategories.value.findIndex(category => category.id === categoryId)
  if (index !== -1) activeTab.value = index
}

// 分类数据回来后再处理带 categoryId 的入口，避免首次进入丢失指定分类。
watch(
  [() => route.query.categoryId, displayCategories],
  syncCategoryFromRoute,
  { immediate: true }
)

onMounted(async () => {
  await newsStore.getCategories()
  await nextTick()

  if (!newsStore.newsList.length && !newsStore.fetching) {
    newsStore.getNewsList()
  }

  // 猜你喜欢只对登录用户有意义（游客直接看分类列表就够了）
  if (userStore.getLoginStatus) {
    newsStore.getRecommendations()
  }
})

// 获取分类名称的翻译
const getCategoryTranslation = (categoryName) => {
  const categoryMap = {
    '头条': 'headline',
    '社会': 'society',
    '国内': 'domestic',
    '国际': 'international',
    '娱乐': 'entertainment',
    '体育': 'sports',
    '军事': 'military',
    '科技': 'technology',
    '财经': 'finance',
    '更多': 'more'
  };
  
  const key = categoryMap[categoryName];
  return key ? t(`home.categories.${key}`) : categoryName;
}
    

// 跳转到分类页面
const goToCategory = () => {
  router.push('/category')
}

// 跳转到搜索页
const goSearch = () => {
  router.push('/search')
}

// 打开推荐卡片
const goToNews = (id) => {
  router.push(`/news/detail/${id}`)
}

// ⚠️ 这里刻意**只有一个** onMounted（上面那个：先取分类，再取列表）。
// 之前这里是第二个 onMounted 并直接调 getNewsList()，于是首次进首页会发两次列表请求：
// 两个请求并发，第二次算 page 时 newsList 往往还是空的（Math.ceil(0/10)+1 = 1），
// 于是又把第 1 页请求了一遍并 append → 首屏前 10 条新闻重复出现一遍。

// 本页是 keep-alive 缓存的：从新闻详情页返回时 onMounted 不会再执行，而详情页会让阅读量 +1。
// 这里在重新激活时同步一次，否则首页会一直显示进入详情之前的旧数字。
// 首次激活（就是刚挂载那一次）跳过 —— 列表已由 onMounted 拉过，避免重复请求。
const activatedBefore = ref(false)
onActivated(() => {
  if (!activatedBefore.value) {
    activatedBefore.value = true
    return
  }
  newsStore.refreshViews()
  // 未登录时看过首页、登录后切回来：补一次推荐
  if (userStore.getLoginStatus && !newsStore.recommendations.length) {
    newsStore.getRecommendations()
  }
})

// 分类导航是唯一入口：点击、路由同步和下拉刷新都走这里。
watch(activeTab, newIndex => {
  const category = displayCategories.value[newIndex]
  if (category) {
    newsStore.changeCategory(category.id)
  }
})

// 下拉刷新
const onRefresh = () => {
  newsStore.getNewsList(true)
}

// 上拉加载更多
const onLoad = () => {
  newsStore.getNewsList()
}
</script>

<style scoped>
.home {
  min-height: 100vh;
  min-height: 100dvh;
  padding-top: var(--nav-height);
  padding-bottom: calc(var(--tabbar-height) + var(--safe-area-inset-bottom));
  background-color: var(--background-color);
}

.nav-search {
  display: grid;
  width: 44px;
  height: 44px;
  margin-right: -8px;
  padding: 0;
  border: 0;
  background: transparent;
  color: var(--icon-color);
  place-items: center;
}

.nav-search:active {
  color: var(--primary-color);
}

.recommend-section {
  padding: 12px 0 10px;
  margin-bottom: 8px;
  background-color: var(--surface-color);
}

.recommend-header {
  padding: 0 16px 8px;
  font-size: 15px;
  font-weight: 600;
  color: var(--text-color);
}

.recommend-scroll {
  display: flex;
  gap: 10px;
  padding: 0 16px 2px;
  overflow-x: auto;
  scroll-snap-type: x proximity;
  -webkit-overflow-scrolling: touch;
  scrollbar-width: none;
}

.recommend-scroll::-webkit-scrollbar {
  display: none;
}

.recommend-card {
  flex: 0 0 120px;
  width: 120px;
  padding: 0;
  border: 0;
  background: transparent;
  color: inherit;
  text-align: left;
  scroll-snap-align: start;
  cursor: pointer;
}

.recommend-card img {
  display: block;
  width: 120px;
  height: 78px;
  object-fit: cover;
  border-radius: 6px;
  background-color: var(--surface-muted);
}

.recommend-title {
  display: -webkit-box;
  margin-top: 6px;
  overflow: hidden;
  color: var(--text-color);
  font-size: 12px;
  line-height: 1.4;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  line-clamp: 2;
}

.category-tabs {
  position: relative;
  margin-bottom: 10px;
}

.category-sticky {
  position: sticky;
  top: var(--nav-height);
  z-index: 20;
  display: flex;
  background-color: var(--surface-color);
}

.category-sticky :deep(.van-tabs) {
  flex: 1;
  min-width: 0;
}

:deep(.van-tabs__wrap) {
  background-color: var(--surface-color);
}

:deep(.van-tab) {
  padding: 0 14px;
  font-size: 14px;
}

:deep(.van-tab--active) {
  color: var(--primary-color);
  font-weight: 600;
}

.more-tab {
  display: inline-flex;
  flex: 0 0 58px;
  align-items: center;
  justify-content: center;
  gap: 2px;
  width: 58px;
  height: 44px;
  padding: 0 6px;
  border: 0;
  border-left: 1px solid var(--border-color);
  background: var(--surface-color);
  color: var(--primary-color);
  font-weight: 600;
  cursor: pointer;
  box-shadow: -6px 0 10px rgba(0, 0, 0, 0.03);
}

@media (max-width: 380px) {
  .recommend-card,
  .recommend-card img {
    width: 104px;
  }

  .recommend-card img {
    height: 72px;
  }
}
</style>