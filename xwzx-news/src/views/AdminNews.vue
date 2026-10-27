<template>
  <div class="admin-page">
    <van-nav-bar title="新闻管理" left-arrow fixed @click-left="goBack">
      <template #right>
        <span class="nav-action" @click="openCreate">新建</span>
      </template>
    </van-nav-bar>

    <div class="toolbar">
      <van-search
        v-model="keyword"
        placeholder="搜索标题或作者"
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
        finished-text="没有更多了"
        @load="loadMore"
      >
        <van-cell
          v-for="item in list"
          :key="item.id"
          :title="item.title"
          :label="`${categoryName(item.categoryId)} · ${formatTime(item.publishTime)} · ${item.views} 阅读`"
          is-link
          @click="openEdit(item)"
        />
      </van-list>

      <van-empty v-if="!loading && !list.length" description="没有新闻，点右上角新建" />
    </div>

    <!-- 新建 / 编辑 -->
    <van-popup v-model:show="showForm" position="bottom" round :style="{ height: '92%' }">
      <div class="form-wrap">
        <div class="form-title">{{ editingId ? '编辑新闻' : '新建新闻' }}</div>

        <van-form @submit="save">
          <van-field
            v-model="form.title"
            label="标题"
            placeholder="必填"
            :rules="[{ required: true, message: '请输入标题' }]"
          />
          <van-field
            v-model="form.categoryName"
            label="分类"
            readonly
            is-link
            placeholder="选择分类"
            :rules="[{ required: true, message: '请选择分类' }]"
            @click="showCategoryPicker = true"
          />
          <van-field v-model="form.author" label="作者" placeholder="选填" />
          <van-field v-model="form.image" label="封面图" placeholder="图片 URL，或点右侧上传">
            <template #button>
              <van-button size="small" type="primary" plain :loading="uploading" @click="pickImage">
                上传
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
            label="摘要"
            type="textarea"
            rows="2"
            autosize
            placeholder="选填，列表页展示这一句"
          />
          <van-field
            v-model="form.content"
            label="正文"
            type="textarea"
            rows="8"
            autosize
            placeholder="必填，用一个空行分段"
            :rules="[{ required: true, message: '请输入正文' }]"
          />

          <div class="form-actions">
            <van-button block type="primary" native-type="submit" :loading="saving">保存</van-button>
            <van-button
              v-if="editingId"
              block
              type="danger"
              plain
              :loading="removing"
              @click="remove"
            >
              删除这条新闻
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

import http from '../api/http'
import { uploadImage } from '../api/upload'
import { useNewsStore } from '../store/modules/news'

const router = useRouter()
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
    categoryId: null,
    categoryName: ''
  }
}

const categories = computed(() => newsStore.categories.filter(item => item.name !== '更多'))
const categoryColumns = computed(() => categories.value.map(item => ({ text: item.name, value: item.id })))

const categoryName = id => categories.value.find(item => item.id === id)?.name || '未分类'
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
    form.value.categoryName = first.name
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
    showToast('上传成功')
  } catch (error) {
    showToast(error.message || '上传失败')
  } finally {
    uploading.value = false
  }
}

const buildPayload = () => ({
  title: form.value.title.trim(),
  description: form.value.description.trim() || null,
  content: form.value.content,
  image: form.value.image.trim() || null,
  author: form.value.author.trim() || null,
  categoryId: form.value.categoryId
})

const save = async () => {
  if (!form.value.categoryId) {
    showToast('请选择分类')
    return
  }

  saving.value = true
  try {
    if (editingId.value) {
      await http.put(`/api/admin/news/${editingId.value}`, buildPayload())
      showToast('已保存')
    } else {
      await http.post('/api/admin/news', buildPayload())
      showToast('已创建')
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
    await showConfirmDialog({ title: '删除确认', message: '删除后不可恢复，确定删除这条新闻？' })
  } catch (error) {
    return
  }

  removing.value = true
  try {
    await http.delete(`/api/admin/news/${editingId.value}`)
    showToast('已删除')
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
