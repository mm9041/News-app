<template>
  <div class="login-page">
    <van-nav-bar
      :title="$t('auth.loginTitle')"
      left-arrow
      @click-left="onClickLeft"
      fixed
    />
    
    <div class="login-container">
      <div class="login-logo">
        <van-image
          width="80"
          height="80"
          src="https://fastly.jsdelivr.net/npm/@vant/assets/cat.jpeg"
          round
        />
        <h2>{{ $t('auth.brand') }}</h2>
      </div>
      
      <van-form @submit="onSubmit" class="login-form">
        <van-cell-group inset>
          <van-field
            v-model="username"
            name="username"
            :label="$t('auth.username')"
            :placeholder="$t('auth.usernamePlaceholder')"
            :rules="[{ required: true, message: $t('auth.usernameRequired') }]"
          />
          <van-field
            v-model="password"
            type="password"
            name="password"
            :label="$t('auth.password')"
            :placeholder="$t('auth.passwordPlaceholder')"
            :rules="[{ required: true, message: $t('auth.passwordRequired') }]"
          />
        </van-cell-group>
        
        <div class="submit-btn">
          <van-button round block type="primary" native-type="submit" size="large">
            {{ $t('auth.loginAction') }}
          </van-button>
        </div>
      </van-form>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue';
import { useRouter } from 'vue-router';
import { showToast } from 'vant';
import { useI18n } from 'vue-i18n';
import { useUserStore } from '../store/user';

const router = useRouter();
const userStore = useUserStore();
const { t } = useI18n();

const username = ref('');
const password = ref('');

const onSubmit = async (values) => {
  // 显示加载提示
  showToast({
    type: 'loading',
    message: t('auth.loggingIn'),
    forbidClick: true,
    duration: 0
  });
  
  try {
    // 调用API登录
    const result = await userStore.login({
      username: username.value,
      password: password.value
    });
    
    if (result.success) {
      showToast({
        type: 'success',
        message: t('auth.loginSuccess')
      });
      
      router.push('/');
    } else {
      showToast({
        type: 'fail',
        message: t('auth.loginFailed')
      });
    }
  } catch (error) {
    showToast({
      type: 'fail',
      message: t('auth.loginFailed')
    });
  }
};

const onClickLeft = () => {
  router.back();
};
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  background-color: #f7f8fa;
}

.login-container {
  padding-top: 56px;
  display: flex;
  flex-direction: column;
  align-items: center;
}

.login-logo {
  margin: 40px 0;
  text-align: center;
}

.login-logo h2 {
  margin-top: 16px;
  color: #323233;
  font-size: 22px;
}

.login-form {
  width: 100%;
  padding: 0 16px;
}

.submit-btn {
  margin: 24px 16px;
}

</style>