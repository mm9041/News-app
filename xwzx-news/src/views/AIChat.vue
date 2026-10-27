<template>
  <div class="ai-chat-container">
    <van-nav-bar title="AI问答" fixed>
      <template #left>
        <span class="nav-action" @click="openHistory">历史</span>
      </template>
      <template #right>
        <span class="nav-action" @click="startNewChat">新对话</span>
      </template>
    </van-nav-bar>
    
    <div class="login-tip" v-if="!isLogin" @click="goToLogin">
      登录后即可与 AI 对话，聊天记录会保存到你的账号
      <span class="login-tip-action">去登录</span>
    </div>

    <div class="chat-content">
      <div class="messages-container" ref="messagesContainer">
        <div 
          v-for="(message, index) in messages" 
          :key="index" 
          :class="['message', message.role === 'user' ? 'user-message' : 'ai-message']"
        >
          <div class="message-content">
            <div v-if="message.role === 'assistant' && message.content === ''" class="typing-indicator">
              <span></span>
              <span></span>
              <span></span>
            </div>
            <div v-else v-html="formatMessage(message.content)"></div>
          </div>
        </div>
      </div>
      
      <div class="input-container">
        <van-field
          v-model="userInput"
          rows="1"
          autosize
          type="textarea"
          placeholder="请输入问题..."
          class="chat-input"
          @keypress.enter.prevent="sendMessage"
        />
        <van-button 
          type="primary" 
          class="send-button" 
          :disabled="isLoading || !userInput.trim()" 
          @click="sendMessage"
        >
          发送
        </van-button>
      </div>
    </div>
    
    <van-popup
      v-model:show="showHistory"
      position="left"
      :style="{ width: '80%', height: '100%' }"
    >
      <div class="history-panel">
        <div class="history-header">
          <span>历史对话</span>
          <span class="history-new" @click="startNewChat">+ 新对话</span>
        </div>

        <div v-if="conversations.length" class="conv-list">
          <div
            v-for="conv in conversations"
            :key="conv.id"
            class="conv-item"
            :class="{ 'is-active': conv.id === conversationId }"
            @click="selectConversation(conv)"
          >
            <div class="conv-title">{{ conv.title }}</div>
            <div class="conv-meta">{{ conv.messageCount }} 轮 · {{ formatTime(conv.updatedAt) }}</div>
            <span class="conv-delete" @click.stop="removeConversation(conv)">删除</span>
          </div>
        </div>
        <van-empty v-else description="还没有历史对话" image-size="60" />
      </div>
    </van-popup>

    <tab-bar />
  </div>
</template>

<script setup>
import { computed, nextTick, onActivated, onMounted, ref, watch } from 'vue';
import { useRouter } from 'vue-router';
import http from '../api/http';
import TabBar from '../components/TabBar.vue';
import * as marked from 'marked';
import DOMPurify from 'dompurify';
import { showConfirmDialog, showToast } from 'vant';
import { useUserStore } from '../store/user';
import { aiChatConfig } from '../config/api';

const router = useRouter();
const userStore = useUserStore();
// 后端 /api/ai/chat 需要登录（Key 在服务端，聊天记录要挂到账号下）
const isLogin = computed(() => userStore.getLoginStatus);
const goToLogin = () => router.push('/login');

// 聊天消息
const messages = ref([
  { role: 'assistant', content: '你好！我是AI助手，有什么可以帮助你的吗？' }
]);
const userInput = ref('');
const messagesContainer = ref(null);
const isLoading = ref(false);

// 统一走后端代理 /api/ai/chat，API Key 不再出现在前端
const chatEndpoint = aiChatConfig.chatEndpoint;

// 当前会话 id；null 表示还没开始（发送第一条消息时后端会创建，并从响应头回传）
const conversationId = ref(null);
const conversations = ref([]);
const showHistory = ref(false);
const historyLoading = ref(false);
const defaultGreeting = '你好！我是AI助手，有什么可以帮助你的吗？';

// 本页是 keep-alive 缓存的，onMounted 与 onActivated 会在同一个 tick 里先后触发，
// 用它防重复初始化（置位必须在 await 之前）
const historyLoaded = ref(false);

// 格式化消息内容（支持Markdown）
const formatMessage = (content) => {
  if (!content) return '';
  return DOMPurify.sanitize(marked.parse(content));
};

const formatTime = (value) => (value ? String(value).replace('T', ' ').slice(0, 16) : '');

const loadConversations = async () => {
  if (!isLogin.value) return;
  try {
    const res = await http.get('/api/ai/conversations', { params: { page: 1, pageSize: 30 } });
    conversations.value = res.data?.data?.list || [];
  } catch (error) {
    console.error('加载会话列表失败:', error);
  }
};

const openHistory = async () => {
  if (!isLogin.value) {
    showToast('请先登录');
    return;
  }
  showHistory.value = true;
  await loadConversations();
};

const selectConversation = async (conv) => {
  if (historyLoading.value) return;
  historyLoading.value = true;
  try {
    const res = await http.get(`/api/ai/conversations/${conv.id}`);
    const list = res.data?.data?.messages || [];

    messages.value = [
      { role: 'assistant', content: defaultGreeting },
      ...list.map(item => ({ role: item.role, content: item.content }))
    ];
    conversationId.value = conv.id;
    showHistory.value = false;

    await nextTick();
    scrollToBottom();
  } catch (error) {
    console.error('加载会话失败:', error);
  } finally {
    historyLoading.value = false;
  }
};

const startNewChat = () => {
  conversationId.value = null;
  messages.value = [{ role: 'assistant', content: defaultGreeting }];
  userInput.value = '';
  showHistory.value = false;
};

const removeConversation = async (conv) => {
  try {
    await showConfirmDialog({ title: '删除对话', message: '删除后不可恢复，确定删除？' });
  } catch (error) {
    return;
  }

  try {
    await http.delete(`/api/ai/conversations/${conv.id}`);
    conversations.value = conversations.value.filter(item => item.id !== conv.id);
    if (conversationId.value === conv.id) {
      startNewChat();
    }
    showToast('已删除');
  } catch (error) {
    // 拦截器已提示
  }
};

// 进页面：拉到会话列表后自动打开最近一次对话，没有就停在欢迎语
const initConversation = async () => {
  if (historyLoaded.value) return;
  if (!isLogin.value || !userStore.token) return;
  historyLoaded.value = true;

  try {
    await loadConversations();
    const latest = conversations.value[0];
    if (latest) {
      await selectConversation(latest);
    }
  } catch (error) {
    historyLoaded.value = false;
  }
};

// 发送消息
const sendMessage = async () => {
  if (!userInput.value.trim() || isLoading.value) return;

  // 登录校验必须放在最前面：否则被拦下后会在消息列表里留下一条孤立的提问
  if (!isLogin.value || !userStore.token) {
    showToast('请先登录后再使用 AI 问答');
    router.push('/login');
    return;
  }

  // 添加用户消息
  const userMessage = userInput.value.trim();
  messages.value.push({ role: 'user', content: userMessage });
  userInput.value = '';
  
  // 添加AI消息占位
  messages.value.push({ role: 'assistant', content: '' });
  
  // 滚动到底部
  await nextTick();
  scrollToBottom();
  
  // 发送请求
  isLoading.value = true;
  try {
    await fetchAIResponse(userMessage);
  } catch (error) {
    console.error('Error fetching AI response:', error);
    // 更新最后一条消息为错误信息
    messages.value[messages.value.length - 1].content = `发生错误: ${error.message || '请检查网络连接和API设置'}`;
  } finally {
    isLoading.value = false;
    await nextTick();
    scrollToBottom();
  }
};

// 上下文预算（字符）。之前每次请求都把**全部**历史消息发给上游：
// 聊到 30 轮时请求体线性膨胀，token 成本和首字延迟一起涨，最后撞上模型上限直接报错。
// 这里从最新往回取，凑满预算就停 —— 保证至少带上本轮提问，丢掉的是最早的对话。
const MAX_CONTEXT_CHARS = 12000;

const buildContext = (history) => {
  const picked = [];
  let total = 0;
  for (let i = history.length - 1; i >= 0; i--) {
    const msg = history[i];
    if (!msg.content) continue;
    // 开头的欢迎语不是真实对话，没必要每次都送给模型（还会让它以为是自己说的）
    if (i === 0 && msg.role === 'assistant') continue;
    if (picked.length > 0 && total + msg.content.length > MAX_CONTEXT_CHARS) break;
    picked.unshift({ role: msg.role, content: msg.content });
    total += msg.content.length;
  }
  return picked;
};

// 获取AI响应（使用SSE）
const fetchAIResponse = async (userMessage) => {
  const allMessages = buildContext(messages.value.slice(0, -1)); // 排除最后一个空的assistant消息
  
  try {
    const response = await fetch(chatEndpoint, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        // 后端要校验登录：裸 token 放 Authorization 头即可（auth.py 会自己剥掉 Bearer 前缀）
        Authorization: userStore.token
      },
      body: JSON.stringify({
        messages: allMessages,
        stream: true,
        conversationId: conversationId.value || undefined
      })
    });
    
    if (response.status === 401) {
      // token 过期或无效：清掉本地登录态并引导重新登录
      userStore.logout();
      showToast('登录已过期，请重新登录');
      router.push('/login');
      throw new Error('登录已过期，请重新登录');
    }

    // 首次对话时后端会新建会话，并通过响应头把 id 回传，前端无需额外请求
    const convHeader = response.headers.get('X-Conversation-Id');
    if (convHeader) {
      conversationId.value = Number(convHeader);
    }

    if (!response.ok) {
      // 后端统一返回 {code, message, data}
      const error = await response.json().catch(() => ({}));
      throw new Error(error.message || `HTTP error! status: ${response.status}`);
    }
    
    // 处理SSE流
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let aiResponse = '';
  
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop() || '';
    
    for (const line of lines) {
      if (line.startsWith('data: ')) {
        const data = line.slice(6);
        if (data === '[DONE]') continue;
        
        let json;
        try {
          json = JSON.parse(data);
        } catch (e) {
          console.error('Error parsing SSE data:', e);
          continue;
        }
        // 后端透传的上游错误（如 401 / 限流），直接抛出去让用户看到原因
        if (json.error) {
          throw new Error(`上游服务返回：${json.error}`);
        }
        // 适配 OpenAI 兼容格式与阿里云 DashScope 原生格式
        const content = json.choices?.[0]?.delta?.content || 
                       json.output?.text || 
                       json.choices?.[0]?.message?.content || '';
        if (content) {
          aiResponse += content;
          // 更新最后一条消息
          messages.value[messages.value.length - 1].content = aiResponse;
          await nextTick();
          scrollToBottom();
        }
      }
    }
  }
  
  // 如果没有收到任何内容
  if (!aiResponse) {
    messages.value[messages.value.length - 1].content = '抱歉，我无法生成回复。请检查API设置或稍后再试。';
  }
  } catch (error) {
    console.error('Fetch error:', error);
    throw error;
  }
};

// 滚动到底部
const scrollToBottom = () => {
  if (messagesContainer.value) {
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight;
  }
};

// 监听消息变化，自动滚动
watch(messages, () => {
  nextTick(scrollToBottom);
}, { deep: true });

// 组件挂载时滚动到底部，并拉取历史对话
onMounted(() => {
  scrollToBottom();
  initConversation();
});

// 本页被 keep-alive 缓存，从别的页面切回来时 onMounted 不会再执行，这里补一次
// （initConversation 内部有 historyLoaded 守卫，未登录时也会自己退出，重复调用是安全的）
onActivated(() => {
  initConversation();
});
</script>

<style scoped>
.login-tip {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px;
  font-size: 12px;
  color: #97690c;
  background-color: #fdf6e3;
  border-bottom: 1px solid #f5e3b3;
}

.login-tip-action {
  color: #1989fa;
  flex-shrink: 0;
  margin-left: 8px;
}

.ai-chat-container {
  display: flex;
  flex-direction: column;
  height: 100vh;
  padding-top: 46px;
  padding-bottom: 50px;
  box-sizing: border-box;
}

.chat-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.messages-container {
  flex: 1;
  overflow-y: auto;
  padding: 10px;
}

.message {
  /* 块级元素默认 width:auto 会先撑满整行，再被 max-width 压到 80%，
     结果短消息的气泡也是满宽。fit-content 让宽度真正跟着内容走，
     只有长内容才会触到 max-width 并换行。 */
  width: fit-content;
  max-width: 80%;
  margin-bottom: 10px;
}

.user-message {
  margin-left: auto;
}

.ai-message {
  margin-right: auto;
}

.message-content {
  padding: 9px 12px;
  border-radius: 10px;
  line-height: 1.6;
  word-break: break-word;
  overflow-wrap: anywhere;
}

/* Markdown 渲染出来的 p / ul 自带上下 margin，会把气泡撑得很空，
   这里只保留段落之间的间距，首尾贴边 */
.message-content p {
  margin: 0 0 6px;
}

.message-content p:last-child {
  margin-bottom: 0;
}

.message-content ul,
.message-content ol {
  margin: 6px 0;
  padding-left: 18px;
}

.message-content ul:last-child,
.message-content ol:last-child {
  margin-bottom: 0;
}

.user-message .message-content {
  background-color: #007aff;
  color: white;
}

.ai-message .message-content {
  background-color: #f2f2f2;
  color: #333;
}

.input-container {
  display: flex;
  padding: 10px;
  border-top: 1px solid #eee;
  background-color: #fff;
}

.chat-input {
  flex: 1;
  margin-right: 10px;
}

.send-button {
  align-self: flex-end;
}

/* Markdown 样式 */
.message-content pre {
  background-color: #f8f8f8;
  padding: 10px;
  border-radius: 5px;
  overflow-x: auto;
  /* 代码块不能被 max-width 撑破，横向滚动交给 overflow-x */
  max-width: 100%;
  margin: 6px 0;
}

.message-content code {
  background-color: rgba(0, 0, 0, 0.05);
  padding: 2px 4px;
  border-radius: 3px;
}

.message-content img {
  max-width: 100%;
}

/* 打字指示器 */
.typing-indicator {
  display: flex;
  padding: 5px;
}

.typing-indicator span {
  height: 8px;
  width: 8px;
  background-color: #999;
  border-radius: 50%;
  margin: 0 2px;
  display: inline-block;
  animation: bounce 1.5s infinite ease-in-out;
}

.typing-indicator span:nth-child(2) {
  animation-delay: 0.2s;
}

.typing-indicator span:nth-child(3) {
  animation-delay: 0.4s;
}

@keyframes bounce {
  0%, 60%, 100% {
    transform: translateY(0);
  }
  30% {
    transform: translateY(-5px);
  }
}

/* Markdown样式 */
:deep(pre) {
  background-color: #f0f0f0;
  padding: 10px;
  border-radius: 4px;
  overflow-x: auto;
}

:deep(code) {
  font-family: monospace;
  background-color: #f0f0f0;
  padding: 2px 4px;
  border-radius: 4px;
}

:deep(p) {
  margin: 8px 0;
}

:deep(ul), :deep(ol) {
  padding-left: 20px;
}

:deep(a) {
  color: #1989fa;
  text-decoration: none;
}
/* ---------------------------- 会话历史 ---------------------------- */
.nav-action {
  color: #1989fa;
  font-size: 14px;
}

.history-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  background-color: #fff;
}

.history-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px;
  font-size: 16px;
  font-weight: 500;
  color: #323233;
  border-bottom: 1px solid #f2f3f5;
}

.history-new {
  font-size: 13px;
  font-weight: normal;
  color: #1989fa;
}

.conv-list {
  flex: 1;
  overflow-y: auto;
}

.conv-item {
  position: relative;
  padding: 12px 16px;
  border-bottom: 1px solid #f7f8fa;
}

.conv-item.is-active {
  background-color: #f2f8ff;
}

.conv-title {
  padding-right: 48px;
  font-size: 14px;
  color: #323233;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.conv-meta {
  margin-top: 4px;
  font-size: 11px;
  color: #c8c9cc;
}

.conv-delete {
  position: absolute;
  top: 12px;
  right: 16px;
  font-size: 12px;
  color: #ee0a24;
}
</style>