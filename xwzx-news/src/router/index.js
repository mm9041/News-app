import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    redirect: '/home'
  },
  {
    path: '/login',
    name: 'Login',
    component: () => import('../views/Login.vue'),
    meta: {
      title: '登录',
      keepAlive: false
    }
  },
  {
    path: '/register',
    name: 'Register',
    component: () => import('../views/Register.vue'),
    meta: {
      title: '注册',
      keepAlive: false
    }
  },
  {
    path: '/home',
    name: 'Home',
    component: () => import('../views/Home.vue'),
    meta: {
      title: '首页',
      keepAlive: true
    }
  },
  {
    path: '/news/detail/:id',
    name: 'NewsDetail',
    component: () => import('../views/NewsDetail.vue'),
    meta: {
      title: '新闻详情',
      keepAlive: false
    }
  },
  {
    path: '/history',
    name: 'History',
    component: () => import('../views/History.vue'),
    meta: {
      title: '浏览历史',
      keepAlive: false
    }
  },
  {
    path: '/favorite',
    name: 'Favorite',
    component: () => import('../views/Favorite.vue'),
    meta: {
      title: '我的收藏',
      keepAlive: false
    }
  },
  {
    path: '/category',
    name: 'Category',
    component: () => import('../views/Category.vue'),
    meta: {
      title: '分类',
      keepAlive: true
    }
  },
  {
    path: '/tag/:id',
    name: 'TagNews',
    component: () => import('../views/TagNews.vue'),
    meta: {
      title: '标签',
      keepAlive: false
    }
  },
  {
    path: '/follow',
    name: 'FollowFeed',
    component: () => import('../views/FollowFeed.vue'),
    meta: {
      title: '关注',
      keepAlive: false,
      requiresAuth: true
    }
  },
  {
    path: '/author/:name',
    name: 'AuthorNews',
    component: () => import('../views/AuthorNews.vue'),
    meta: {
      title: '作者',
      keepAlive: false
    }
  },
  {
    path: '/search',
    name: 'Search',
    component: () => import('../views/Search.vue'),
    meta: {
      title: '搜索',
      keepAlive: false
    }
  },
  {
    path: '/admin/news',
    name: 'AdminNews',
    component: () => import('../views/AdminNews.vue'),
    meta: {
      title: '新闻管理',
      keepAlive: false,
      // 真正的权限校验在后端 /api/admin/*；这里只做前端体验拦截
      requiresAdmin: true
    }
  },
  {
    path: '/admin/dashboard',
    name: 'AdminDashboard',
    component: () => import('../views/AdminDashboard.vue'),
    meta: {
      title: '数据看板',
      keepAlive: false,
      requiresAdmin: true
    }
  },
  {
    path: '/admin/users',
    name: 'AdminUsers',
    component: () => import('../views/AdminUsers.vue'),
    meta: {
      title: '用户管理',
      keepAlive: false,
      requiresAdmin: true
    }
  },
  {
    path: '/notifications',
    name: 'Notifications',
    component: () => import('../views/Notifications.vue'),
    meta: {
      title: '消息通知',
      keepAlive: false,
      requiresAuth: true
    }
  },
  {
    path: '/aichat',
    name: 'AIChat',
    component: () => import('../views/AIChat.vue'),
    meta: {
      title: 'AI问答',
      keepAlive: true
    }
  },
  {
    path: '/my',
    name: 'My',
    component: () => import('../views/My.vue'),
    meta: {
      title: '我的',
      keepAlive: true
    }
  },
  {
    path: '/profile',
    name: 'Profile',
    component: () => import('../views/Profile.vue'),
    meta: {
      title: '个人信息',
      keepAlive: false
    }
  },
  {
    path: '/settings',
    name: 'Settings',
    component: () => import('../views/Settings.vue'),
    meta: {
      title: '设置',
      keepAlive: false
    }
  },
]

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,
  // 单页应用切路由时浏览器不会自动回到顶部，必须显式声明。
  // 不配这个的典型症状：首页滚到一半点进详情，详情页直接停在中间。
  scrollBehavior(to, from, savedPosition) {
    // 浏览器前进/后退（含 router.back()）时恢复原来的位置
    if (savedPosition) return savedPosition
    // 其余跳转一律回顶部
    return { top: 0 }
  }
})

// 只负责设置页面标题。
// 登录 / 管理员拦截在 router/guard.js 里（那里能 import store，
// 不会形成 router -> store -> api/http -> router 的循环依赖）。
router.beforeEach((to) => {
  document.title = to.meta.title || '新闻资讯'
})

export default router