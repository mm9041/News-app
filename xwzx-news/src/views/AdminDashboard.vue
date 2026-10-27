<template>
  <div class="dash-page">
    <van-nav-bar title="数据看板" left-arrow fixed @click-left="goBack" />

    <div class="content">
      <div class="cards">
        <div class="card">
          <div class="num">{{ data.overview.news }}</div>
          <div class="label">新闻</div>
        </div>
        <div class="card">
          <div class="num">{{ data.overview.comments }}</div>
          <div class="label">评论</div>
        </div>
        <div class="card">
          <div class="num">{{ data.overview.users }}</div>
          <div class="label">用户</div>
        </div>
        <div class="card">
          <div class="num">{{ data.overview.views }}</div>
          <div class="label">总阅读</div>
        </div>
      </div>

      <div class="panel">
        <div class="panel-title">近 {{ days }} 天新增</div>
        <div class="chart">
          <div v-for="item in data.trend" :key="item.date" class="chart-col">
            <div class="bars">
              <div class="bar bar-news" :style="{ height: barHeight(item.news) + '%' }"></div>
              <div class="bar bar-comment" :style="{ height: barHeight(item.comments) + '%' }"></div>
            </div>
            <div class="chart-label">{{ item.date.slice(5) }}</div>
          </div>
        </div>
        <div class="legend">
          <span class="dot dot-news"></span><span class="legend-text">新闻</span>
          <span class="dot dot-comment"></span><span class="legend-text">评论</span>
        </div>
      </div>

      <div class="panel">
        <div class="panel-title">分类分布</div>
        <div v-for="item in data.categories" :key="item.name" class="cat-row">
          <span class="cat-name">{{ item.name }}</span>
          <div class="cat-track">
            <div class="cat-fill" :style="{ width: catPercent(item.news) + '%' }"></div>
          </div>
          <span class="cat-val">{{ item.news }}</span>
        </div>
      </div>

      <div class="panel">
        <div class="panel-title">阅读量 Top {{ data.topNews.length }}</div>
        <div
          v-for="(item, index) in data.topNews"
          :key="item.id"
          class="top-row"
          @click="openNews(item.id)"
        >
          <span class="rank" :class="{ 'is-top3': index < 3 }">{{ index + 1 }}</span>
          <span class="top-title">{{ item.title }}</span>
          <span class="top-views">{{ item.views }}</span>
        </div>
        <div v-if="!data.topNews.length" class="empty-text">暂无数据</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import http from '../api/http'

const router = useRouter()
const days = 7

const data = ref({
  overview: { news: 0, comments: 0, users: 0, views: 0 },
  trend: [],
  categories: [],
  topNews: []
})

const maxTrend = computed(() =>
  Math.max(1, ...data.value.trend.map(item => Math.max(item.news, item.comments)))
)

const barHeight = value => Math.max(2, Math.round((value / maxTrend.value) * 100))

const maxCategory = computed(() =>
  Math.max(1, ...data.value.categories.map(item => item.news))
)

const catPercent = value => Math.max(2, Math.round((value / maxCategory.value) * 100))

const goBack = () => router.back()
const openNews = id => router.push(`/news/detail/${id}`)

onMounted(async () => {
  try {
    const res = await http.get('/api/admin/stats', { params: { days } })
    const payload = res.data?.data
    if (payload) {
      data.value = payload
    }
  } catch (error) {
    // 拦截器已提示
  }
})
</script>

<style scoped>
.dash-page {
  padding-top: 46px;
  padding-bottom: 20px;
  min-height: 100vh;
  background-color: #f7f8fa;
}

.content {
  padding: 12px;
}

.cards {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 10px;
}

.card {
  background-color: #fff;
  border-radius: 10px;
  padding: 14px;
  text-align: center;
}

.card .num {
  font-size: 22px;
  font-weight: 500;
  color: #1989fa;
}

.card .label {
  margin-top: 4px;
  font-size: 12px;
  color: #969799;
}

.panel {
  margin-top: 12px;
  padding: 14px;
  background-color: #fff;
  border-radius: 10px;
}

.panel-title {
  font-size: 14px;
  font-weight: 500;
  color: #323233;
  margin-bottom: 12px;
}

.chart {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  height: 120px;
  gap: 4px;
}

.chart-col {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  height: 100%;
}

.bars {
  flex: 1;
  display: flex;
  align-items: flex-end;
  gap: 2px;
  width: 100%;
  justify-content: center;
}

.bar {
  width: 8px;
  border-radius: 3px 3px 0 0;
  min-height: 2px;
}

.bar-news {
  background-color: #378add;
}

.bar-comment {
  background-color: #1d9e75;
}

.chart-label {
  margin-top: 6px;
  font-size: 10px;
  color: #c8c9cc;
}

.legend {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 10px;
  font-size: 11px;
  color: #969799;
}

.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.dot-news {
  background-color: #378add;
}

.dot-comment {
  background-color: #1d9e75;
}

.legend-text {
  margin-right: 10px;
}

.cat-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.cat-name {
  width: 42px;
  font-size: 12px;
  color: #646566;
  flex-shrink: 0;
}

.cat-track {
  flex: 1;
  height: 8px;
  background-color: #f2f3f5;
  border-radius: 4px;
  overflow: hidden;
}

.cat-fill {
  height: 100%;
  background-color: #85b7eb;
  border-radius: 4px;
}

.cat-val {
  width: 32px;
  text-align: right;
  font-size: 12px;
  color: #969799;
  flex-shrink: 0;
}

.top-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 0;
  border-bottom: 1px solid #f7f8fa;
}

.top-row:last-child {
  border-bottom: none;
}

.rank {
  width: 18px;
  height: 18px;
  line-height: 18px;
  text-align: center;
  font-size: 11px;
  color: #969799;
  background-color: #f2f3f5;
  border-radius: 4px;
  flex-shrink: 0;
}

.rank.is-top3 {
  color: #fff;
  background-color: #ee0a24;
}

.top-title {
  flex: 1;
  font-size: 13px;
  color: #323233;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.top-views {
  font-size: 12px;
  color: #969799;
  flex-shrink: 0;
}

.empty-text {
  padding: 12px 0;
  text-align: center;
  font-size: 12px;
  color: #c8c9cc;
}
</style>
