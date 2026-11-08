import { i18n } from './index'

// 后端错误文案目前只有中文。英文界面下把常见业务错误映射成英文；
// 未收录的中文错误降级为通用提示，避免中英文混排。
const EN_MESSAGES = {
  用户已存在: 'This username is already taken',
  用户名或密码错误: 'Incorrect username or password',
  '账号已被禁用，请联系管理员': 'This account has been disabled. Please contact an administrator.',
  '未提供令牌，请先登录': 'Authentication required. Please sign in.',
  '无效的令牌或已经过期的令牌': 'Your session is invalid or has expired. Please sign in again.',
  需要管理员权限: 'Administrator permission required',
  新闻不存在: 'Article not found',
  用户不存在: 'User not found',
  评论不存在: 'Comment not found',
  被回复的评论不存在: 'The comment being replied to no longer exists',
  评论内容不能为空: 'Comment cannot be empty',
  只能删除自己的评论: 'You can only delete your own comments',
  会话不存在: 'Conversation not found',
  历史记录不存在: 'History record not found',
  不能禁用自己: 'You cannot ban your own account',
  不能取消自己的管理员权限: 'You cannot revoke your own administrator permission',
  不能删除自己: 'You cannot delete your own account',
  '大模型未配置，请检查 .env 中的 AI_CHAT_URL 与 AI_API_KEY':
    'The AI model is not configured. Check AI_CHAT_URL and AI_API_KEY in .env.',
  文件为空: 'The file is empty',
  '图片不能超过 5MB': 'The image must not exceed 5 MB',
  '只支持 JPG / PNG / GIF / WebP': 'Only JPG, PNG, GIF, and WebP images are supported',
  '用户已存在，请更换用户名': 'This username is already taken. Choose another one.',
  '新闻不存在或已被删除': 'The article does not exist or has been deleted',
  '收藏记录不存在': 'Favorite not found',
  '该手机号已被其他账号使用': 'This phone number is already used by another account',
  '登录状态冲突，请重新登录': 'Session conflict. Please sign in again.',
  '已经点过赞了': 'You have already liked this article',
  '已经收藏过这条新闻了': 'You have already saved this article',
  '同一篇新闻不能重复挂同一个标签': 'The same tag cannot be added twice to one article',
  '名称已存在': 'This name already exists',
  '数据已存在，请勿重复提交': 'This record already exists',
  '关联数据不存在': 'Related data does not exist',
  '数据库操作失败，请稍后重试': 'Database operation failed. Please try again later.',
  '服务器内部错误': 'Internal server error'
}

const EN_PATTERNS = [
  [/^大模型返回 (\d+)$/, match => `AI service returned HTTP ${match[1]}`],
  [/^注册过于频繁.*$/, () => 'Too many registration attempts. Try again in a minute.'],
  [/^登录尝试过于频繁.*$/, () => 'Too many login attempts. Try again in a minute.'],
  [/^操作过于频繁.*$/, () => 'Too many requests. Try again later.'],
  [/^提问过于频繁.*$/, () => 'Too many AI requests. Try again in a minute.'],
  [/^参数 (.+) 不能小于 (.+)$/, match => `Parameter ${match[1]} must be at least ${match[2]}`],
  [/^参数 (.+) 不能大于 (.+)$/, match => `Parameter ${match[1]} must be at most ${match[2]}`],
  [/^缺少必填参数：(.+)$/, match => `Missing required parameter: ${match[1]}`]
]

export function localizeApiMessage(message) {
  if (!message || !String(i18n.global.locale.value).startsWith('en')) {
    return message
  }

  const text = String(message)
  if (EN_MESSAGES[text]) return EN_MESSAGES[text]

  for (const [pattern, replace] of EN_PATTERNS) {
    const match = text.match(pattern)
    if (match) return replace(match)
  }

  // 后端消息中英文混排比“稍微具体一点的中文”更影响体验。
  if (/\p{Script=Han}/u.test(text)) {
    return i18n.global.t('common.operationFailed')
  }
  return text
}
