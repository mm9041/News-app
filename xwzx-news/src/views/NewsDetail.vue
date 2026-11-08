<template>
  <div class="news-detail">
    <van-nav-bar
      :title="$t('detail.title')"
      :left-text="$t('detail.back')"
      left-arrow
      @click-left="onClickLeft"
      fixed
    />
    
    <div class="detail-content" v-if="newsStore.newsDetail.id">
      <div class="title-container">
        <h1 class="title">{{ newsStore.newsDetail.title }}</h1>
        <div class="title-actions">
          <button
            type="button"
            class="like-btn"
            :class="{ 'is-liked': liked }"
            :aria-label="liked ? $t('detail.unlike') : $t('detail.like')"
            @click="toggleLike"
          >
            <van-icon :name="liked ? 'good-job' : 'good-job-o'" size="20" />
            <span class="like-count">{{ likes }}</span>
          </button>
          <button
            v-if="followTarget"
            type="button"
            class="follow-author-btn"
            :class="{ 'is-following': isFollowing }"
            @click="toggleFollow"
          >
            {{ isFollowing ? $t('detail.following') : $t('detail.followAuthor') }}
          </button>
          <van-button
            class="favorite-btn"
            :icon="isFavorite ? 'star' : 'star-o'"
            :class="{ 'is-favorite': isFavorite }"
            :aria-label="$t('favorite.title')"
            @click="toggleFavorite"
          />
        </div>
      </div>
      
      <div class="info">
        <span>{{ newsStore.newsDetail.author }}</span>
        <span>{{ newsStore.newsDetail.publishTime }}</span>
        <span>{{ $t('common.views', { count: newsStore.newsDetail.views }) }}</span>
      </div>

      <div class="cover" v-if="newsStore.newsDetail.image">
        <img
          :src="newsStore.newsDetail.image"
          :alt="newsStore.newsDetail.title"
          width="640"
          height="360"
          decoding="async"
          fetchpriority="high"
          @error="onImageError"
        >
      </div>
      
      <div class="content">
        <p v-for="(paragraph, index) in contentParagraphs" :key="index">
          {{ paragraph }}
        </p>
      </div>
      
      <div class="tag-list" v-if="newsStore.newsDetail.tags?.length">
        <button
          v-for="tag in newsStore.newsDetail.tags"
          :key="tag.id"
          type="button"
          class="tag-item"
          @click="goToTag(tag.id)"
        >
          #{{ tag.name }}
        </button>
      </div>

      <div class="related-news" v-if="newsStore.newsDetail.relatedNews?.length">
        <h3>{{ $t('detail.related') }}</h3>
        <div class="related-list">
          <div 
            class="related-item" 
            v-for="item in newsStore.newsDetail.relatedNews" 
            :key="item.id"
            @click="goToRelatedNews(item.id)"
          >
            <div class="related-image">
              <img
                :src="item.image"
                :alt="item.title"
                width="80"
                height="60"
                loading="lazy"
                decoding="async"
                @error="onImageError"
              >
            </div>
            <div class="related-title">{{ item.title }}</div>
          </div>
        </div>
      </div>

      <!-- 评论区 -->
      <div class="comment-section">
        <div class="comment-header">
          {{ $t('detail.comments') }}
          <span class="comment-count" v-if="commentTotal">{{ commentTotal }}</span>
        </div>

        <div class="comment-editor">
          <div class="editor-main">
            <div v-if="replyTarget" class="reply-hint">
              {{ $t('detail.replyingTo', { name: replyTarget.name }) }}
              <span class="reply-cancel" @click="cancelReply">{{ $t('detail.cancel') }}</span>
            </div>
            <van-field
              v-model="commentText"
              rows="2"
              autosize
              type="textarea"
              maxlength="500"
              show-word-limit
              :placeholder="replyTarget ? $t('detail.replyPlaceholder', { name: replyTarget.name }) : $t('detail.commentPlaceholder')"
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
            {{ $t('detail.publish') }}
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
                  <span class="comment-reply" @click="startReply(item.id, item.user.nickname || item.user.username)">{{ $t('detail.reply') }}</span>
                  <span v-if="item.canDelete" class="comment-delete" @click="deleteComment(item)">{{ $t('detail.delete') }}</span>
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
                      <span v-if="reply.replyTo" class="reply-to">{{ $t('detail.replyingTo', { name: reply.replyTo }) }}</span>
                      <span class="comment-time">{{ formatTime(reply.createdAt) }}</span>
                      <span class="comment-actions">
                        <span class="comment-reply" @click="startReply(reply.id, reply.user.nickname || reply.user.username)">{{ $t('detail.reply') }}</span>
                        <span v-if="reply.canDelete" class="comment-delete" @click="deleteComment(reply)">{{ $t('detail.delete') }}</span>
                      </span>
                    </div>
                    <div class="comment-text">{{ reply.content }}</div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div v-if="commentHasMore" class="comment-more" @click="loadComments()">{{ $t('detail.loadMoreComments') }}</div>
          <div v-else class="comment-more comment-end">{{ $t('detail.noMoreComments') }}</div>
        </div>

        <van-empty v-else-if="commentLoaded" :description="$t('detail.commentEmpty')" image-size="60" />
      </div>
    </div>
    
    <van-empty v-else :description="$t('detail.loadingComments')" />
  </div>
</template>

<script setup>
import { computed, onMounted, ref,watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useNewsStore } from '../store/modules/news'
import { useHistoryStore } from '../store/modules/history'
import { useFavoriteStore } from '../store/modules/favorite'
import { useUserStore } from '../store/user'
import { showConfirmDialog, showToast } from 'vant'
import { onImageError } from '../config/image'
import http from '../api/http'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()
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
      message: t('detail.loginToFavorite'),
      position: 'bottom',
    })
    router.push('/login')
    return
  }
  
  // 已登录则调用API切换收藏状态
  const status = await favoriteStore.toggleFavorite(newsStore.newsDetail)
  
  if (status === true) {
    showToast({
      message: t('detail.favoriteAdded'),
      position: 'bottom',
    })
  } else if (status === false) {
    showToast({
      message: t('detail.favoriteRemoved'),
      position: 'bottom',
    })
  } else {
    // status为null表示操作失败
    showToast({
      message: t('common.operationFailed'),
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

  // 关注状态跟着当前作者走
  const target = followTarget.value
  if (target && userStore.getLoginStatus) {
    try {
      const res = await http.get('/api/follow/status', {
        params: { name: target.name }
      })
      isFollowing.value = Boolean(res.data?.data?.following)
    } catch (error) {
      isFollowing.value = false
    }
  } else {
    isFollowing.value = false
  }

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
    showToast(t('detail.loginToLike'))
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

// ---------------------------- 关注作者 ----------------------------

const isFollowing = ref(false)
const followLoading = ref(false)

// 关注对象：作者（就是页面上显示的那个名字——可能是「海南日报」，也可能是人名）
const followTarget = computed(() => {
  const author = newsStore.newsDetail.author
  return author ? { name: author, label: t('author.fallback') } : null
})

const toggleFollow = async () => {
  const target = followTarget.value
  if (!target) return

  if (!userStore.getLoginStatus) {
    showToast(t('common.loginRequired'))
    router.push('/login')
    return
  }
  if (followLoading.value) return

  followLoading.value = true
  try {
    if (isFollowing.value) {
      await http.delete('/api/follow', {
        params: { name: target.name }
      })
      isFollowing.value = false
      showToast(t('detail.unfollowed'))
    } else {
      await http.post('/api/follow', null, {
        params: { name: target.name }
      })
      isFollowing.value = true
      showToast(t('detail.followed'))
    }
  } catch (error) {
    // 拦截器已提示
  } finally {
    followLoading.value = false
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
    const res = await http.get('/api/comment', {
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
    showToast(t('detail.loginToComment'))
    router.push('/login')
    return
  }

  submitting.value = true
  try {
    const payload = { newsId: newsId.value, content }
    if (replyTarget.value) {
      payload.parentId = replyTarget.value.id
    }

    await http.post('/api/comment', payload)
    commentText.value = ''
    replyTarget.value = null
    showToast(t('detail.commentSuccess'))
    await loadComments(true)
  } catch (error) {
    // 拦截器已提示
  } finally {
    submitting.value = false
  }
}

const deleteComment = async item => {
  try {
    await showConfirmDialog({ title: t('detail.deleteCommentTitle'), message: t('detail.deleteCommentMessage') })
  } catch (error) {
    return
  }

  try {
    await http.delete(`/api/comment/${item.id}`)
    // 本地移除即可，不必整页重刷
    const isReply = Boolean(item.parentId)
    // 删一级评论会级联删掉它的全部回复，计数要一起减，否则总数会虚高
    const removedCount = isReply ? 1 : 1 + (item.replies?.length || 0)

    if (isReply) {
      const parent = comments.value.find(comment => comment.id === item.parentId)
      if (parent) {
        parent.replies = (parent.replies || []).filter(reply => reply.id !== item.id)
      }
    } else {
      comments.value = comments.value.filter(comment => comment.id !== item.id)
    }

    commentTotal.value = Math.max(0, commentTotal.value - removedCount)
    showToast(t('detail.deleted'))
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
  min-height: 100vh;
  min-height: 100dvh;
  padding-top: var(--nav-height);
  background-color: var(--surface-color);
  color: var(--text-color);
}

.detail-content {
  width: min(100%, 720px);
  margin: 0 auto;
  padding: 16px;
}

.title-container {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.title {
  flex: 1;
  min-width: 0;
  margin: 0;
  color: var(--text-color);
  font-size: 22px;
  font-weight: 700;
  line-height: 1.4;
  overflow-wrap: anywhere;
}

.favorite-btn {
  width: 44px;
  height: 44px;
  padding: 0;
  border-radius: 50%;
  color: var(--icon-color-muted);
}

.favorite-btn.is-favorite {
  color: #ff9500;
}

.info {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 12px;
  margin-bottom: 16px;
  color: var(--text-color-lighter);
  font-size: 12px;
}

.cover {
  margin-bottom: 16px;
  overflow: hidden;
  border-radius: 8px;
  background-color: var(--surface-muted);
  aspect-ratio: 16 / 9;
}

.cover img {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.content {
  color: var(--text-color);
  font-size: 16px;
  line-height: 1.8;
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
  width: 44px;
  height: 44px;
  padding: 0;
  border: 0;
  background: transparent;
  color: var(--icon-color-muted);
  cursor: pointer;
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

.follow-author-btn {
  min-width: 72px;
  height: 36px;
  padding: 0 10px;
  border: 1px solid var(--primary-color);
  border-radius: 999px;
  background-color: var(--surface-color);
  color: var(--primary-color);
  font-size: 12px;
  cursor: pointer;
}

.follow-author-btn.is-following {
  border-color: var(--border-color);
  color: var(--text-color-lighter);
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
  min-height: 32px;
  padding: 4px 10px;
  border: 0;
  border-radius: 12px;
  background-color: #f2f8ff;
  color: var(--primary-color);
  font-size: 12px;
  cursor: pointer;
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
  color: var(--text-color-lighter);
}

@media (max-width: 480px) {
  .title-container {
    flex-direction: column;
  }

  .title-actions {
    margin: 0 0 0 -4px;
  }

  .comment-meta {
    flex-wrap: wrap;
    row-gap: 4px;
  }

  .comment-actions {
    margin-left: 0;
  }
}
</style>