<template>
  <div class="admin-page">
    <van-nav-bar :title="$t('admin.news.title')" left-arrow fixed @click-left="goBack">
      <template #right>
        <span class="nav-action" @click="openCreate">{{ $t('admin.news.create') }}</span>
      </template>
    </van-nav-bar>

    <div class="toolbar">
      <van-search
        v-model="keyword"
        :placeholder="$t('admin.news.searchPlaceholder')"
        shape="round"
        @search="reload"
        @clear="reload"
      />
    </div>

    <div class="list-area">
      <van-list
        v-model:loading="loading"
        :finished="finished"
        :immediate-check="false"
        :finished-text="$t('admin.common.noMore')"
        @load="loadMore"
      >
        <van-cell
          v-for="item in list"
          :key="item.id"
          :title="item.title"
          :label="$t('admin.news.meta', { category: categoryName(item.categoryId), time: formatTime(item.publishTime), views: item.views })"
          is-link
          @click="openEdit(item)"
        />
      </van-list>

      <van-empty v-if="!loading && !list.length" :description="$t('admin.news.empty')" />
    </div>

    <!-- 新建 / 编辑 -->
    <van-popup v-model:show="showForm" position="bottom" round :style="{ height: '92%' }">
      <div class="form-wrap">
        <div class="form-title">{{ editingId ? $t('admin.news.editTitle') : $t('admin.news.createTitle') }}</div>

        <van-form @submit="save">
          <van-field
            v-model="form.title"
            :label="$t('admin.news.title')"
            :placeholder="$t('admin.news.titlePlaceholder')"
            :rules="[{ required: true, message: $t('admin.news.titleRequired') }]"
          />
          <van-field
            v-model="form.categoryName"
            :label="$t('admin.news.category')"
            readonly
            is-link
            :placeholder="$t('admin.news.categoryPlaceholder')"
            :rules="[{ required: true, message: $t('admin.news.categoryRequired') }]"
            @click="showCategoryPicker = true"
          />
          <van-field v-model="form.author" :label="$t('admin.news.author')" :placeholder="$t('admin.news.authorPlaceholder')" />
          <van-field
            v-model="form.tagsText"
            :label="$t('admin.news.tags')"
            :placeholder="$t('admin.news.tagsPlaceholder')"
          />
          <van-field v-model="form.image" :label="$t('admin.news.cover')" :placeholder="$t('admin.news.coverPlaceholder')">
            <template #button>
              <van-button size="small" type="primary" plain :loading="uploading" @click="pickImage">
                {{ $t('admin.news.upload') }}
              </van-button>
            </template>
          </van-field>
          <input
            ref="fileInput"
            type="file"
            accept="image/*"
            style="display: none"
            @change="onFileChange"
          />
          <van-field
            v-model="form.description"
            :label="$t('admin.news.summary')"
            type="textarea"
            rows="2"
            autosize
            :placeholder="$t('admin.news.summaryPlaceholder')"
          />
          <van-field
            v-model="form.content"
            :label="$t('admin.news.content')"
            type="textarea"
            rows="8"
            autosize
            :placeholder="$t('admin.news.contentPlaceholder')"
            :rules="[{ required: true, message: $t('admin.news.contentRequired') }]"
          />

          <div class="form-actions">
            <van-button block type="primary" native-type="submit" :loading="saving">{{ $t('admin.news.save') }}</van-button>
            <van-button
              v-if="editingId"
              block
              type="danger"
              plain
              :loading="removing"
              @click="remove"
            >
              {{ $t('admin.news.deleteNews') }}
            </van-button>
          </div>
        </van-form>
      </div>
    </van-popup>

    <van-popup v-model:show="showCategoryPicker" position="bottom" round>
      <van-picker
        :columns="categoryColumns"
        @confirm="onCategoryConfirm"
        @cancel="showCategoryPicker = false"
      />
    </van-popup>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { showConfirmDialog, showToast } from 'vant'
import { useI18n } from 'vue-i18n'

import http from '../api/http'
import { categoryLabel, isMoreCategory } from '../i18n/categories'
import { uploadImage } from '../api/upload'
import { useNewsStore } from '../store/modules/news'

const router = useRouter()
const { t } = useI18n()
const newsStore = useNewsStore()

const PAGE_SIZE = 10

const keyword = ref('')
const list = ref([])
const page = ref(1)
const loading = ref(false)
const finished = ref(false)

// ⚠️ 不能用 `loading` 当并发守卫：van-list 在调用 @load **之前**就会把它置为 true，
// 于是第一行判断直接命中并 return，既没发请求、也没人把 loading 复位 ——
// 界面就永远停在「加载中」，这是之前只显示 10 条的根因。
// 这里用独立的 fetching 标志，loading 只负责给 van-list 展示转圈；
// requestSeq 用来丢弃「重置列表时仍在飞行」的旧响应，避免旧关键词的结果混进来。
let fetching = false
let requestSeq = 0

const showForm = ref(false)
const showCategoryPicker = ref(false)
const editingId = ref(null)
const saving = ref(false)
const removing = ref(false)
const uploading = ref(false)
const fileInput = ref(null)
const form = ref(emptyForm())

function emptyForm() {
  return {
    title: '',
    description: '',
    content: '',
    image: '',
    author: '',
    tagsText: '',
    categoryId: null,
    categoryName: ''
  }
}

const categories = computed(() => newsStore.categories.filter(item => !isMoreCategory(item.name)))
const categoryColumns = computed(() =>
  categories.value.map(item => ({ text: categoryLabel(item.name, t), value: item.id }))
)

const categoryName = id => {
  const name = categories.value.find(item => item.id === id)?.name
  return name ? categoryLabel(name, t) : t('admin.news.uncategorized')
}
const formatTime = value => (value ? String(value).replace('T', ' ').slice(0, 16) : '—')

const goBack = () => router.back()

const fetchPage = async (reset = false) => {
  if (reset) {
    page.value = 1
    list.value = []
    finished.value = false
    fetching = false
    requestSeq += 1 // 让在飞的旧请求作废
  }

  if (fetching || finished.value) {
    // 提前退出也必须把 loading 复位，否则 van-list 会一直转圈
    loading.value = false
    return
  }

  fetching = true
  loading.value = true
  const seq = ++requestSeq

  try {
    const res = await http.get('/api/admin/news', {
      params: {
        page: page.value,
        pageSize: PAGE_SIZE,
        keyword: keyword.value.trim() || undefined
      }
    })
    if (seq !== requestSeq) return

    const data = res.data?.data || {}
    const items = data.list || []
    const total = data.total || 0

    list.value = [...list.value, ...items]
    // 用 total 判断比「这一页不满 10 条」更准：总数正好是 10 的倍数时不会多请求一次
    finished.value = list.value.length >= total || items.length < PAGE_SIZE
    page.value += 1
  } catch (error) {
    if (seq === requestSeq) finished.value = true
  } finally {
    if (seq === requestSeq) {
      fetching = false
      loading.value = false
    }
  }
}

const reload = () => fetchPage(true)
const loadMore = () => fetchPage()

const openCreate = () => {
  editingId.value = null
  form.value = emptyForm()
  const first = categories.value[0]
  if (first) {
    form.value.categoryId = first.id
    form.value.categoryName = categoryLabel(first.name, t)
  }
  showForm.value = true
}

const openEdit = async item => {
  try {
    const res = await http.get(`/api/admin/news/${item.id}`)
    const data = res.data?.data
    editingId.value = data.id
    form.value = {
      title: data.title,
      description: data.description || '',
      content: data.content,
      image: data.image || '',
      author: data.author || '',
      tagsText: (data.tags || []).join(','),
      categoryId: data.categoryId,
      categoryName: categoryName(data.categoryId)
    }
    showForm.value = true
  } catch (error) {
    // 拦截器已提示
  }
}

const onCategoryConfirm = ({ selectedOptions }) => {
  const option = selectedOptions[0]
  if (option) {
    form.value.categoryId = option.value
    form.value.categoryName = option.text
  }
  showCategoryPicker.value = false
}

const pickImage = () => fileInput.value?.click()

const onFileChange = async event => {
  const file = event.target.files?.[0]
  // 清空 value，否则连续选同一个文件不会触发 change
  event.target.value = ''
  if (!file) return

  uploading.value = true
  try {
    form.value.image = await uploadImage(file)
    showToast(t('admin.news.uploadSuccess'))
  } catch (error) {
    showToast(t('admin.news.uploadFailed'))
  } finally {
    uploading.value = false
  }
}

// 中英文逗号都当分隔符，去空、去重、最多 5 个（后端也会再截一次）
const parseTags = () => [...new Set(
  form.value.tagsText
    .split(/[,，]/)
    .map(item => item.trim())
    .filter(Boolean)
)].slice(0, 5)

const buildPayload = () => ({
  title: form.value.title.trim(),
  description: form.value.description.trim() || null,
  content: form.value.content,
  image: form.value.image.trim() || null,
  author: form.value.author.trim() || null,
  categoryId: form.value.categoryId,
  tags: parseTags()
})

const save = async () => {
  if (!form.value.categoryId) {
    showToast(t('admin.news.selectCategoryFirst'))
    return
  }

  // tag.name 是 VARCHAR(30)，超长会被数据库静默截断（不同长标签还可能撞成同一个）
  const tooLongTag = parseTags().find(item => item.length > 30)
  if (tooLongTag) {
    showToast(t('admin.news.tagTooLong', { tag: tooLongTag }))
    return
  }

  saving.value = true
  try {
    if (editingId.value) {
      await http.put(`/api/admin/news/${editingId.value}`, buildPayload())
      showToast(t('admin.news.saved'))
    } else {
      await http.post('/api/admin/news', buildPayload())
      showToast(t('admin.news.created'))
    }
    showForm.value = false
    await reload()
  } catch (error) {
    // 拦截器已提示
  } finally {
    saving.value = false
  }
}

const remove = async () => {
  try {
    await showConfirmDialog({ title: t('admin.news.deleteTitle'), message: t('admin.news.deleteMessage') })
  } catch (error) {
    return
  }

  removing.value = true
  try {
    await http.delete(`/api/admin/news/${editingId.value}`)
    showToast(t('admin.news.deleted'))
    showForm.value = false
    await reload()
  } catch (error) {
    // 拦截器已提示
  } finally {
    removing.value = false
  }
}

onMounted(async () => {
  if (!newsStore.categories.length) {
    await newsStore.getCategories()
  }
  await reload()
})
</script>

<style scoped>
.admin-page {
  padding-top: 46px;
  padding-bottom: 20px;
  min-height: 100vh;
  background-color: var(--background-color, #f7f8fa);
}

.nav-action {
  color: #1989fa;
  font-size: 14px;
}

.toolbar {
  position: fixed;
  top: 46px;
  left: 0;
  right: 0;
  z-index: 99;
  max-width: 750px;
  margin: 0 auto;
  background-color: #fff;
}

.list-area {
  margin-top: 54px;
}

.form-wrap {
  padding: 16px;
  height: 100%;
  overflow-y: auto;
  box-sizing: border-box;
}

.form-title {
  font-size: 16px;
  font-weight: 600;
  margin-bottom: 12px;
  text-align: center;
}

.form-actions {
  margin-top: 20px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
</style>
