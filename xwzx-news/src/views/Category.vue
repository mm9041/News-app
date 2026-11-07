<template>
  <div class="category">
    <van-nav-bar 
      :title="$t('common.allCategories')" 
      :left-text="$t('common.back')"
      left-arrow
      @click-left="onClickLeft"
      fixed 
    />
    
    <div class="category-container">
      <van-grid :column-num="3" :border="false">
        <van-grid-item 
          v-for="category in displayCategories" 
          :key="category.id"
          :text="getCategoryTranslation(category.name)"
          icon="newspaper-o"
          @click="goToCategoryNews(category.id)"
        />
      </van-grid>
    </div>
    
    <tab-bar />
  </div>
</template>

<script setup>
import { useNewsStore } from '../store/modules/news'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import TabBar from '../components/TabBar.vue'
import { computed, onMounted } from 'vue'

const newsStore = useNewsStore()
const router = useRouter()
const { t } = useI18n()

// 计算属性：显示的分类（只显示非"更多"分类）
const displayCategories = computed(() => {
  return newsStore.categories.filter(category => category.name !== '更多');
})

// 返回上一页
const onClickLeft = () => {
  router.back()
}

// 跳转到对应分类的新闻列表
const goToCategoryNews = (categoryId) => {
  // 先切换分类
  newsStore.changeCategory(categoryId)
  
  // 使用路由参数传递分类ID
  router.push({
    path: '/home',
    query: { categoryId: categoryId }
  })
}

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

// 本页是 keep-alive 缓存的，但首次进入（直接访问 /category 或刷新页面）时
// store 里还没有分类数据 —— 不补这一次请求，页面就是一片空白。
// 分类是低频数据，切回来不需要重新拉，所以只用 onMounted，不加 onActivated。
onMounted(() => {
  if (!newsStore.categories.length) {
    newsStore.getCategories()
  }
})
</script>

<style scoped>
.category {
  min-height: 100vh;
  min-height: 100dvh;
  padding-top: var(--nav-height);
  padding-bottom: calc(var(--tabbar-height) + var(--safe-area-inset-bottom));
  background-color: var(--background-color);
  color: var(--text-color);
}

.category-container {
  margin: 12px 16px;
  padding: 16px;
  border-radius: 12px;
  background-color: var(--surface-color);
}

:deep(.van-grid) {
  gap: 10px 0;
}

:deep(.van-grid-item__content) {
  min-height: 92px;
  border-radius: 10px;
  background-color: var(--surface-muted);
}

:deep(.van-grid-item__icon) {
  color: var(--primary-color);
  font-size: 28px;
}

:deep(.van-grid-item__text) {
  margin-top: 8px;
  color: var(--text-color);
  font-size: 14px;
}
</style>