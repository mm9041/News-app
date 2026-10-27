import http from './http'

const MAX_SIZE = 5 * 1024 * 1024

/**
 * 上传图片，返回可直接用于 <img src> 的完整 URL。
 *
 * 前端这层只做基本拦截（类型、大小）以省一次请求；真正的校验在后端：
 * 文件名和 Content-Type 都不可信，服务端会按文件头魔数判断真实类型。
 */
export async function uploadImage(file) {
  if (!file) {
    throw new Error('没有选择文件')
  }
  if (!file.type.startsWith('image/')) {
    throw new Error('只能上传图片')
  }
  if (file.size > MAX_SIZE) {
    throw new Error('图片不能超过 5MB')
  }

  const form = new FormData()
  form.append('file', file)

  // 不要手动设置 Content-Type：axios 需要自己补 multipart 的 boundary
  const res = await http.post('/api/upload/image', form)
  return res.data?.data?.url
}
