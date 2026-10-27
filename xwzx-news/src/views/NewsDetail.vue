<template>
  <div class="news-detail">
    <van-nav-bar
      title="新闻详情"
      left-text="返回"
      left-arrow
      @click-left="onClickLeft"
      fixed
    />
    
    <div class="detail-content" v-if="newsStore.newsDetail.id">
      <div class="title-container">
        <h1 class="title">{{ newsStore.newsDetail.title }}</h1>
        <div class="title-actions">
          <div class="like-btn" :class="{ 'is-liked': liked }" @click="toggleLike">
            <van-icon :name="liked ? 'good-job' : 'good-job-o'" size="20" />
            <span class="like-count">{{ likes }}</span>
          </div>
          <van-button
            class="favorite-btn"
            :icon="isFavorite ? 'star' : 'star-o'"
            :class="{ 'is-favorite': isFavorite }"
            @click="toggleFavorite"
          />
        </div>
      </div>
      
      <div class="info">
        <span>{{ newsStore.newsDetail.author }}</span>
        <span>{{ newsStore.newsDetail.publishTime }}</span>
        <span>{{ newsStore.newsDetail.views }} 阅读</span>
      </div>

      <div class="cover" v-if="newsStore.newsDetail.image">
        <img :src="newsStore.newsDetail.image" :alt="newsStore.newsDetail.title" @error="onImageError">
      </div>
      
      <div class="content">
        <p v-for="(paragraph, index) in contentParagraphs" :key="index">
          {{ paragraph }}
        </p>
      </div>
      
      <div class="tag-list" v-if="newsStore.newsDetail.tags?.length">
        <span
          v-for="tag in newsStore.newsDetail.tags"
          :key="tag.id"
          class="tag-item"
          @click="goToTag(tag.id)"
        >
          #{{ tag.name }}
        </span>
      </div>

      <div class="related-news" v-if="newsStore.newsDetail.relatedNews?.length">
        <h3>相关推荐</h3>
        <div class="related-list">
          <div 
            class="related-item" 
            v-for="item in newsStore.newsDetail.relatedNews" 
            :key="item.id"
            @click="goToRelatedNews(item.id)"
          >
            <div class="related-image">
              <img :src="item.image" :alt="item.title" @error="onImageError">
            </div>
            <div class="related-title">{{ item.title }}</div>
          </div>
        </div>
      </div>

      <!-- 评论区 -->
      <div class="comment-section">
        <div class="comment-header">
          评论
          <span class="comment-count" v-if="commentTotal">{{ commentTotal }}</span>
        </div>

        <div class="comment-editor">
          <div class="editor-main">
            <div v-if="replyTarget" class="reply-hint">
              回复 @{{ replyTarget.name }}
              <span class="reply-cancel" @click="cancelReply">取消</span>
            </div>
            <van-field
              v-model="commentText"
              rows="2"
              autosize
              type="textarea"
              maxlength="500"
              show-word-limit
              :placeholder="replyTarget ? `回复 @${replyTarget.name}` : '说点什么...'"
              class="comment-field"
            />
          </div>
          <van-button
            size="small"
            type="primary"
            :loading="submitting"
            :disabled="!commentText.trim()"
            @click="submitComment"
          >
            发布
          </van-button>
        </div>

        <div v-if="comments.length" class="comment-list">
          <div v-for="item in comments" :key="item.id" class="comment-item">
            <van-image
              round
              width="32"
              height="32"
              class="comment-avatar"
              :src="item.user.avatar || defaultAvatar"
            />
            <div class="comment-body">
              <div class="comment-meta">
                <span class="comment-name">{{ item.user.nickname || item.user.username }}</span>
                <span class="comment-time">{{ formatTime(item.createdAt) }}</span>
                <span class="comment-actions">
                  <span class="comment-reply" @click="startReply(item.id, item.user.nickname || item.user.username)">回复</span>
                  <span v-if="item.canDelete" class="comment-delete" @click="deleteComment(item)">删除</span>
                </span>
              </div>
              <div class="comment-text">{{ item.content }}</div>

              <div v-if="item.replies && item.replies.length" class="reply-list">
                <div v-for="reply in item.replies" :key="reply.id" class="reply-item">
                  <van-image
                    round
                    width="24"
                    height="24"
                    class="comment-avatar"
                    :src="reply.user.avatar || defaultAvatar"
                  />
                  <div class="reply-body">
                    <div class="comment-meta">
                      <span class="comment-name">{{ reply.user.nickname || reply.user.username }}</span>
                      <span v-if="reply.replyTo" class="reply-to">回复 @{{ reply.replyTo }}</span>
                      <span class="comment-time">{{ formatTime(reply.createdAt) }}</span>
                      <span class="comment-actions">
                        <span class="comment-reply" @click="startReply(reply.id, reply.user.nickname || reply.user.username)">回复</span>
                        <span v-if="reply.canDelete" class="comment-delete" @click="deleteComment(reply)">删除</span>
                      </span>
                    </div>
                    <div class="comment-text">{{ reply.content }}</div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div v-if="commentHasMore" class="comment-more" @click="loadComments()">加载更多评论</div>
          <div v-else class="comment-more comment-end">没有更多了</div>
        </div>

        <van-empty v-else-if="commentLoaded" description="还没有评论，来说第一句吧" image-size="60" />
      </div>
    </div>
    
    <van-empty v-else description="加载中..." />
  </div>
</template>

<script setup>
import { computed, onMounted, ref,watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useNewsStore } from '../store/modules/news'
import { useHistoryStore } from '../store/modules/history'
import { useFavoriteStore } from '../store/modules/favorite'
import { useUserStore } from '../store/user'
import { showConfirmDialog, showToast } from 'vant'
import { onImageError } from '../config/image'
import http from '../api/http'

const route = useRoute()
const router = useRouter()
const newsStore = useNewsStore()
const historyStore = useHistoryStore()
const favoriteStore = useFavoriteStore()
const userStore = useUserStore()

// 获取路由参数中的新闻ID
const newsId = computed(() => Number(route.params.id))

// 将内容拆分为段落
const contentParagraphs = computed(() => {
  if (!newsStore.newsDetail.content) return []
  return newsStore.newsDetail.content.split('\n\n').filter(p => p.trim())
})

// 返回上一页
const onClickLeft = () => {
  router.back()
}

// 跳转到相关新闻
const goToTag = (tagId) => {
  router.push(`/tag/${tagId}`)
}
const goToRelatedNews = (id) => {
  router.push(`/news/detail/${id}`)
}

// 判断当前新闻是否已收藏
const isFavorite = computed(() => {
  return favoriteStore.isFavorite(newsId.value)
})

// 切换收藏状态
const toggleFavorite = async () => {
  // 判断用户是否已登录
  if (!userStore.getLoginStatus) {
    // 未登录则跳转到登录页
    showToast({
      message: '请先登录后再收藏',
      position: 'bottom',
    })
    router.push('/login')
    return
  }
  
  // 已登录则调用API切换收藏状态
  const status = await favoriteStore.toggleFavorite(newsStore.newsDetail)
  
  if (status === true) {
    showToast({
      message: '已添加到收藏',
      position: 'bottom',
    })
  } else if (status === false) {
    showToast({
      message: '已取消收藏',
      position: 'bottom',
    })
  } else {
    // status为null表示操作失败
    showToast({
      message: '操作失败，请稍后重试',
      position: 'bottom',
    })
  }
}

// 组件挂载时获取新闻详情并添加到浏览历史
// 把加载逻辑抽成函数，供首次挂载和路由参数变化时复用
const loadDetail = async () => {
  await newsStore.getNewsDetail(newsId.value)

  // 点赞状态跟着详情一起刷新（切换到相关新闻时也要重置）
  likes.value = newsStore.newsDetail.likes || 0
  liked.value = Boolean(newsStore.newsDetail.isLiked)

  // 添加到浏览历史
  if (newsStore.newsDetail.id) {
    if (userStore.getLoginStatus) {
      try {
        const result = await historyStore.addHistoryApi(newsStore.newsDetail.id);
      } catch (error) {
        console.error('记录浏览历史API失败:', error);
      }
    }
  }

  // 加载收藏数据
  favoriteStore.loadFavorites()

  // 检查文章收藏状态
  if (userStore.getLoginStatus && newsStore.newsDetail.id) {
    const result = await favoriteStore.checkFavoriteStatusApi(newsStore.newsDetail.id)
    if (result.success && !result.isLocal) {
      if (result.isFavorite && !favoriteStore.isFavorite(newsStore.newsDetail.id)) {
        favoriteStore.addFavorite(newsStore.newsDetail)
      } else if (!result.isFavorite && favoriteStore.isFavorite(newsStore.newsDetail.id)) {
        favoriteStore.removeFavorite(newsStore.newsDetail.id)
      }
    }
  }

  // 正文加载完再拉评论；评论失败不该阻塞正文阅读
  await loadComments(true)
}

// ---------------------------- 点赞 ----------------------------

const likes = ref(0)
const liked = ref(false)
const likeLoading = ref(false)

const toggleLike = async () => {
  if (!userStore.getLoginStatus) {
    showToast('请先登录后再点赞')
    router.push('/login')
    return
  }
  if (likeLoading.value) return

  likeLoading.value = true
  try {
    // PUT 点赞 / DELETE 取消，两者都幂等；不用 toggle 是为了弱网重试时不会翻回去
    const res = liked.value
      ? await http.delete(`/api/news/${newsId.value}/like`)
      : await http.put(`/api/news/${newsId.value}/like`)

    const data = res.data?.data || {}
    liked.value = Boolean(data.liked)
    likes.value = data.likes || 0
  } catch (error) {
    // 拦截器已提示
  } finally {
    likeLoading.value = false
  }
}

// ---------------------------- 评论 ----------------------------

const COMMENT_PAGE_SIZE = 10
const defaultAvatar = 'https://fastly.jsdelivr.net/npm/@vant/assets/cat.jpeg'

const comments = ref([])
const commentTotal = ref(0)
const commentPage = ref(1)
const commentHasMore = ref(false)
const commentLoaded = ref(false)
const commentLoading = ref(false)
const commentText = ref('')
const submitting = ref(false)
// 正在回复的目标：{ id, name }。null 表示发一级评论
const replyTarget = ref(null)

const startReply = (id, name) => {
  replyTarget.value = { id, name }
  commentText.value = ''
  // 输入框在列表上方，滚回去并聚焦
  const editor = document.querySelector('.comment-editor')
  if (editor) {
    editor.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }
}

const cancelReply = () => {
  replyTarget.value = null
}

const formatTime = value => (value ? String(value).replace('T', ' ').slice(0, 16) : '')

// 这里刻意用「加载更多」按钮而不是 van-list：
// van-list 在触发 @load 前会自己把 loading 置 true，稍不注意就会挡掉自己的请求。
const loadComments = async (reset = false) => {
  if (reset) {
    commentPage.value = 1
    comments.value = []
    commentHasMore.value = false
    commentLoaded.value = false
  }
  if (commentLoading.value) return

  commentLoading.value = true
  try {
    const res = await http.get('/api/comment/list', {
      params: {
        newsId: newsId.value,
        page: commentPage.value,
        pageSize: COMMENT_PAGE_SIZE
      }
    })
    const data = res.data?.data || {}
    const items = data.list || []

    comments.value = [...comments.value, ...items]
    commentTotal.value = data.total || 0
    commentHasMore.value = Boolean(data.hasMore)
    commentPage.value += 1
  } catch (error) {
    // 评论加载失败不影响正文阅读，静默处理
  } finally {
    commentLoading.value = false
    commentLoaded.value = true
  }
}

const submitComment = async () => {
  const content = commentText.value.trim()
  if (!content) return

  if (!userStore.getLoginStatus) {
    showToast('请先登录后再评论')
    router.push('/login')
    return
  }

  submitting.value = true
  try {
    const payload = { newsId: newsId.value, content }
    if (replyTarget.value) {
      payload.parentId = replyTarget.value.id
    }

    await http.post('/api/comment/add', payload)
    commentText.value = ''
    replyTarget.value = null
    showToast('评论成功')
    await loadComments(true)
  } catch (error) {
    // 拦截器已提示
  } finally {
    submitting.value = false
  }
}

const deleteComment = async item => {
  try {
    await showConfirmDialog({ title: '删除评论', message: '确定删除这条评论？' })
  } catch (error) {
    return
  }

  try {
    await http.delete(`/api/comment/${item.id}`)
    // 本地移除即可，不必整页重刷
    comments.value = comments.value.filter(comment => comment.id !== item.id)
    commentTotal.value = Math.max(0, commentTotal.value - 1)
    showToast('已删除')
  } catch (error) {
    // 拦截器已提示
  }
}

onMounted(() => {
  loadDetail()
})

// 关键：同一条路由只换参数时组件会被复用，onMounted 不会再次触发，
// 所以必须显式监听参数变化
watch(newsId, (newId, oldId) => {
  if (newId && newId !== oldId) {
    window.scrollTo(0, 0)   // 顺手回到顶部，否则会停在上一篇文章的滚动位置
    loadDetail()
  }
})

</script>

<style scoped>
.news-detail {
  padding-top: 46px;
  background-color: #fff;
  min-height: 100vh;
}

.detail-content {
  padding: 16px;
}

.title-container {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 12px;
}

.title {
  font-size: 22px;
  font-weight: bold;
  line-height: 1.4;
  margin: 0;
  flex: 1;
}

.favorite-btn {
  padding: 0;
  width: 36px;
  height: 36px;
  border-radius: 50%;
}

.favorite-btn.is-favorite {
  color: #ff9500;
}

.info {
  display: flex;
  font-size: 12px;
  color: #999;
  margin-bottom: 16px;
}

.info span {
  margin-right: 12px;
}

.cover {
  margin-bottom: 16px;
}

.cover img {
  width: 100%;
  border-radius: 4px;
}

.content {
  font-size: 16px;
  line-height: 1.8;
  color: #333;
}

.content p {
  margin-bottom: 16px;
  text-align: justify;
}

.related-news {
  margin-top: 24px;
  padding-top: 16px;
  border-top: 8px solid #f5f5f5;
}

.related-news h3 {
  font-size: 18px;
  margin: 0 0 16px;
}

.related-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.related-item {
  display: flex;
  align-items: center;
}

.related-image {
  width: 80px;
  height: 60px;
  margin-right: 12px;
  flex-shrink: 0;
}

.related-image img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  border-radius: 4px;
}

.related-title {
  font-size: 14px;
  line-height: 1.4;
  flex: 1;
}
/* ---------------------------- 点赞 ---------------------------- */
.title-actions {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
  margin-left: 10px;
  margin-top: 2px;
}

.like-btn {
  display: inline-flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  color: #646566;
  transition: color 0.2s;
}

.like-btn.is-liked {
  color: #ee0a24;
}

.like-count {
  margin-top: 2px;
  font-size: 11px;
  line-height: 1;
}

/* ---------------------------- 评论 ---------------------------- */
.comment-section {
  margin-top: 28px;
  padding-top: 16px;
  border-top: 8px solid #f7f8fa;
}

.comment-header {
  font-size: 16px;
  font-weight: 600;
  margin-bottom: 12px;
}

.comment-count {
  color: #969799;
  font-weight: normal;
  font-size: 13px;
}

.comment-editor {
  display: flex;
  align-items: flex-end;
  gap: 8px;
  margin-bottom: 8px;
}

.editor-main {
  flex: 1;
  min-width: 0;
}

.reply-hint {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
  font-size: 12px;
  color: #1989fa;
}

.reply-cancel {
  color: #969799;
  text-decoration: underline;
}

.comment-actions {
  margin-left: auto;
  display: flex;
  gap: 12px;
}

.comment-reply {
  font-size: 12px;
  color: #1989fa;
}

.reply-list {
  margin-top: 8px;
  padding: 8px;
  background-color: #f7f8fa;
  border-radius: 6px;
}

.reply-item {
  display: flex;
  gap: 8px;
  padding: 6px 0;
}

.reply-body {
  flex: 1;
  min-width: 0;
}

.reply-to {
  font-size: 11px;
  color: #646566;
}

.tag-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin: 16px 0 4px;
}

.tag-item {
  padding: 4px 10px;
  font-size: 12px;
  color: #1989fa;
  background-color: #f2f8ff;
  border-radius: 12px;
}

.comment-field {
  flex: 1;
  padding: 8px;
  background-color: #f7f8fa;
  border-radius: 8px;
}

.comment-item {
  display: flex;
  gap: 10px;
  padding: 12px 0;
  border-bottom: 1px solid #f2f3f5;
}

.comment-avatar {
  flex-shrink: 0;
}

.comment-body {
  flex: 1;
  min-width: 0;
}

.comment-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}

.comment-name {
  font-size: 13px;
  font-weight: 500;
  color: #323233;
}

.comment-time {
  font-size: 11px;
  color: #c8c9cc;
}

.comment-delete {
  font-size: 12px;
  color: #ee0a24;
}

.comment-text {
  font-size: 14px;
  line-height: 1.5;
  color: #323233;
  word-break: break-word;
}

.comment-more {
  padding: 14px 0;
  text-align: center;
  font-size: 13px;
  color: #1989fa;
}

.comment-end {
  color: #c8c9cc;
}
</style>