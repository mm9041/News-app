<template>
  <div class="ai-chat-container">
    <van-nav-bar title="AI问答" fixed />
    
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
import { showToast } from 'vant';
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

// 历史是否已拉取。本页是 keep-alive 缓存的，onActivated 会反复触发，用它防重复追加
const historyLoaded = ref(false);

// 格式化消息内容（支持Markdown）
const formatMessage = (content) => {
  if (!content) return '';
  // 使用marked解析Markdown，并用DOMPurify清理HTML
  return DOMPurify.sanitize(marked.parse(content));
};

// 进页面时加载历史对话
const loadHistory = async () => {
  if (historyLoaded.value) return;
  // 未登录既没有历史可拉，也不该发这个请求
  if (!isLogin.value || !userStore.token) return;

  // 必须在 await 之前就置位：首次进入已登录的页面时，onMounted 与 onActivated
  // 会在**同一个 tick** 里先后触发，两次调用都会走到这里。若是等 axios 返回后才置位，
  // 两次都能通过上面的守卫 → 请求发两次、历史对话被追加两遍（页面上整段重复）。
  historyLoaded.value = true;

  try {
    const response = await http.get('/api/ai/history', {
      params: { page: 1, pageSize: 20 }
    });

    if (response.data?.code !== 200) return;

    // 后端按时间倒序返回（最新的在前），这里反转成时间正序再渲染
    const list = response.data.data?.list || [];
    const restored = [];
    list.slice().reverse().forEach((item) => {
      restored.push({ role: 'user', content: item.message });
      restored.push({ role: 'assistant', content: item.response });
    });

    if (restored.length) {
      // 欢迎语保留在最前面，历史对话接在它后面
      messages.value = [...messages.value, ...restored];
      await nextTick();
      scrollToBottom();
    }
  } catch (error) {
    if (error.response?.status === 401) {
      // token 失效：清掉本地登录态，未登录提示条会重新出现
      userStore.logout();
    }
    // 拉历史失败不该阻断聊天。放开标志，下次进页面会重试
    historyLoaded.value = false;
    console.error('加载历史对话失败:', error);
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
        stream: true
      })
    });
    
    if (response.status === 401) {
      // token 过期或无效：清掉本地登录态并引导重新登录
      userStore.logout();
      showToast('登录已过期，请重新登录');
      router.push('/login');
      throw new Error('登录已过期，请重新登录');
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
  loadHistory();
});

// 本页被 keep-alive 缓存，从别的页面切回来时 onMounted 不会再执行，这里补一次
// （loadHistory 内部有 historyLoaded 守卫，未登录时也会自己退出，重复调用是安全的）
onActivated(() => {
  loadHistory();
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
  margin-bottom: 10px;
  max-width: 80%;
}

.user-message {
  margin-left: auto;
}

.ai-message {
  margin-right: auto;
}

.message-content {
  padding: 10px;
  border-radius: 10px;
  word-break: break-word;
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
</style>