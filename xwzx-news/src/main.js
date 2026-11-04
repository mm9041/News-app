import { createApp } from 'vue'
import App from './App.vue'
import router from './router'
import pinia from './store'
import { bindUnauthorizedHandler } from './api/http'
import { useThemeStore } from './store/theme'
import { setupGuard } from './router/guard'
import { useUserStore } from './store/user'

// 导入Vant组件库
import { 
  Button, 
  NavBar, 
  Tabbar, 
  TabbarItem, 
  Tab, 
  Tabs, 
  List, 
  PullRefresh, 
  Cell, 
  CellGroup,
  Grid,
  GridItem,
  Empty,
  Form,
  Field,
  Image,
  Toast,
  Icon,
  Popup,
  Picker,
  Search
} from 'vant'

// 导入Vant样式
import 'vant/lib/index.css'

// 导入全局样式
import './style.css'

// 引入国际化
import { setupI18n } from './i18n'

const app = createApp(App)

// 设置i18n
const i18n = setupI18n()
app.use(i18n)

// 注册Vant组件
app.use(Button)
app.use(NavBar)
app.use(Tabbar)
app.use(TabbarItem)
app.use(Tab)
app.use(Tabs)
app.use(List)
app.use(PullRefresh)
app.use(Cell)
app.use(CellGroup)
app.use(Grid)
app.use(GridItem)
app.use(Empty)
app.use(Form)
app.use(Field)
app.use(Image)
app.use(Toast)
app.use(Icon)
app.use(Popup)
app.use(Picker)
app.use(Search)

// 使用路由和状态管理
app.use(router)
app.use(pinia)

// token 存在 httpOnly cookie 里（JS 读不到），所以请求层不需要注入 token；
// 401 时统一清本地登录态（跳转与提示在拦截器里做）
bindUnauthorizedHandler(() => useUserStore().clearSession())

// 管理员路由守卫（必须在 pinia 安装之后注册）
setupGuard(router)

// 主题：把 store 里保存的主题写进 CSS 变量。不调用的话刷新页面后
// 变量全部丢失，只有再次进设置页才会恢复
const themeStore = useThemeStore()
themeStore.applyTheme()

// PWA：生产构建才注册 Service Worker（开发环境会干扰 Vite 热更新）
if ('serviceWorker' in navigator && import.meta.env.PROD) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js').catch(error => {
      console.error('Service Worker 注册失败:', error)
    })
  })
}

app.mount('#app')

// 启动时恢复会话：token 在 httpOnly cookie 里读不到，只能问一次后端。
// 放在 mount 之后，不阻塞首屏；游客会拿到 401，静默处理。
useUserStore().restoreSession()

