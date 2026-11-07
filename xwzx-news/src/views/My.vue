<template>
  <div class="my-container">
    <van-nav-bar :title="$t('my.title')" fixed />
    <div
      v-if="isLogin"
      class="user-info user-info--link"
      role="button"
      tabindex="0"
      @click="goToProfile"
      @keydown.enter.prevent="goToProfile"
      @keydown.space.prevent="goToProfile"
    >
      <div class="avatar">
        <van-image
          round
          width="80"
          height="80"
          :src="avatarUrl"
        />
      </div>
      <div class="info">
        <div class="username">{{ isLogin && userInfo ? userInfo.username : $t('my.notLoggedIn') }}</div>
        <div class="desc" v-if="isLogin">{{ userBio || $t('profile.bio') }}</div>
      </div>
      <van-icon name="arrow" class="arrow-icon" />
    </div>
    <div class="user-info" v-else>
      <div class="avatar">
        <van-image
          round
          width="80"
          height="80"
          src="https://fastly.jsdelivr.net/npm/@vant/assets/cat.jpeg"
        />
      </div>
      <div class="info">
        <div class="username">{{ $t('my.notLoggedIn') }}</div>
        <div class="desc">
          <van-button type="primary" size="small" @click="goToLogin" style="margin-right: 10px">{{ $t('my.goToLogin') }}</van-button>
          <van-button type="default" size="small" @click="goToRegister">{{ $t('my.goToRegister') }}</van-button>
        </div>
      </div>
    </div>

    <div class="menu-list">
      <van-cell-group inset>
        <van-cell :title="$t('my.myFavorite')" is-link @click="goToFavorite" />
        <van-cell :title="$t('my.browsingHistory')" is-link @click="goToHistory" />
        <van-cell :title="$t('my.notifications')" is-link :badge="unreadCount > 0 ? unreadCount : ''" @click="goToNotifications" />
        <van-cell v-if="userInfo?.isAdmin" title="新闻管理" is-link @click="goToAdminNews" />
        <van-cell v-if="userInfo?.isAdmin" title="数据看板" is-link @click="goToDashboard" />
        <van-cell v-if="userInfo?.isAdmin" title="用户管理" is-link @click="goToAdminUsers" />
        <van-cell title="我的关注" is-link @click="goToFollow" />
        <van-cell :title="$t('my.settings')" is-link @click="goToSettings" />
        <van-cell v-if="isLogin" :title="$t('my.logout')" @click="handleLogout" />
      </van-cell-group>
    </div>
    <tab-bar />
  </div>
</template>

<script setup>
import { computed, onActivated, onMounted, ref } from 'vue';
import { useUserStore } from '../store/user';
import { useRouter } from 'vue-router';
import { showDialog, showToast } from 'vant';
import TabBar from '../components/TabBar.vue';
import { useI18n } from 'vue-i18n';
import http from '../api/http';

const userStore = useUserStore();
const router = useRouter();
const { t } = useI18n();

// 从store获取用户信息和登录状态
const userInfo = computed(() => userStore.userInfo);
const isLogin = computed(() => userStore.getLoginStatus);
const userBio = computed(() => userStore.getUserBio || t('profile.bio'));

const defaultAvatar = 'https://fastly.jsdelivr.net/npm/@vant/assets/cat.jpeg';
// 头像以「个人信息」里设置的为准，没设置才回落到默认图。
// 之前这里写死了 cat.jpeg，所以在个人信息页换了头像，这一页也不变。
const avatarUrl = computed(() => userInfo.value?.avatar || defaultAvatar);

// 未读通知数，显示在「消息通知」右侧
const unreadCount = ref(0);

const loadUnread = async () => {
  if (!isLogin.value) {
    unreadCount.value = 0;
    return;
  }
  try {
    const res = await http.get('/api/notification/unread-count');
    unreadCount.value = res.data?.data?.count || 0;
  } catch (error) {
    // 未读数失败不影响页面
  }
};

const goToNotifications = () => {
  if (!isLogin.value) {
    showToast(t('common.login'));
    return;
  }
  router.push('/notifications');
};

// 跳转到登录页
const goToLogin = () => {
  router.push('/login');
};

// 跳转到注册页
const goToRegister = () => {
  router.push('/register');
};

// 跳转到个人信息页
const goToProfile = () => {
  if (isLogin.value) {
    router.push('/profile');
  }
};

// 新闻管理（入口只对管理员显示，路由守卫和后端还会各校验一次）
const goToAdminNews = () => {
  router.push('/admin/news');
};

// 数据看板
const goToDashboard = () => {
  router.push('/admin/dashboard');
};

// 用户管理
const goToAdminUsers = () => {
  router.push('/admin/users');
};

// 关注页
const goToFollow = () => {
  if (!isLogin.value) {
    showToast(t('common.login'));
    return;
  }
  router.push('/follow');
};

// 跳转到浏览历史页面
const goToHistory = () => {
  if (isLogin.value) {
    router.push('/history');
  } else {
    showToast(t('common.login'));
    router.push('/login');
  }
};

// 跳转到我的收藏页面
const goToFavorite = () => {
  if (isLogin.value) {
    router.push('/favorite');
  } else {
    showToast(t('common.login'));
    router.push('/login');
  }
};

// 跳转到设置页面
const goToSettings = () => {
  router.push('/settings');
};

// 退出登录
const handleLogout = () => {
  showDialog({
    title: t('common.confirm'),
    message: t('my.logout') + '?',
    showCancelButton: true,
  }).then((action) => {
    if (action === 'confirm') {
      userStore.logout();
      router.push('/login');
    }
  });
};

// 拉取最新资料。未登录时不必发这个请求。
const loadUserInfo = async () => {
  if (!userStore.getLoginStatus || !userStore.isLogin) return;
  try {
    await userStore.getUserInfoDetail();
  } catch (error) {
    console.error('获取用户信息失败:', error);
  }
};

// 首次进入由 onMounted 拉；本页是 keep-alive 缓存的，从别的页面切回来时
// onMounted 不会再执行，这里补一次，用来同步服务端最新资料（例如在另一台设备上改过）。
// 标志必须在 await 之前置位：两个 hook 在同一个 tick 里先后触发，
// 若等请求返回才置位，首次进入会请求两次。
const activatedBefore = ref(false);
onMounted(() => {
  loadUserInfo();
  loadUnread();
});
onActivated(() => {
  if (!activatedBefore.value) {
    activatedBefore.value = true;
    return;
  }
  loadUserInfo();
  loadUnread();
});
</script>

<style scoped>
.my-container {
  box-sizing: border-box;
  min-height: 100vh;
  min-height: 100dvh;
  padding-top: calc(var(--nav-height) + 16px);
  padding-bottom: calc(var(--tabbar-height) + var(--safe-area-inset-bottom));
  background-color: var(--background-color);
  color: var(--text-color);
}

.user-info {
  position: relative;
  display: flex;
  align-items: center;
  margin: 0 16px 16px;
  padding: 20px 16px;
  border-radius: 12px;
  background: linear-gradient(135deg, var(--primary-color), #0f6fdc);
  color: #fff;
  box-shadow: 0 8px 20px rgba(25, 137, 250, 0.18);
}

.user-info--link {
  cursor: pointer;
}

.arrow-icon {
  position: absolute;
  right: 16px;
  color: rgba(255, 255, 255, 0.85);
}

.avatar {
  margin-right: 16px;
}

.info {
  flex: 1;
}

.username {
  font-size: 18px;
  font-weight: bold;
  margin-bottom: 4px;
}

.desc {
  color: rgba(255, 255, 255, 0.82);
  font-size: 14px;
}

.menu-list {
  margin: 0 16px;
}

.menu-list :deep(.van-cell-group--inset) {
  margin: 0;
  overflow: hidden;
  border-radius: 12px;
  background-color: var(--surface-color);
}
</style>