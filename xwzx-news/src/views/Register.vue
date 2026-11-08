<template>
  <div class="register-page">
    <van-nav-bar
      :title="$t('auth.registerTitle')"
      left-arrow
      @click-left="onClickLeft"
      fixed
    />
    
    <div class="register-container">
      <div class="register-logo">
        <van-image
          width="80"
          height="80"
          src="https://fastly.jsdelivr.net/npm/@vant/assets/cat.jpeg"
          round
        />
        <h2>{{ $t('auth.brand') }}</h2>
      </div>
      
      <van-form @submit="onSubmit" class="register-form">
        <van-cell-group inset>
          <van-field
            v-model="username"
            name="username"
            :label="$t('auth.username')"
            :placeholder="$t('auth.usernamePlaceholder')"
            :rules="[
              { required: true, message: $t('auth.usernameRequired') },
              { validator: validateUsername, message: $t('auth.usernameRule') }
            ]"
          />
          <van-field
            v-model="password"
            type="password"
            name="password"
            :label="$t('auth.password')"
            :placeholder="$t('auth.passwordPlaceholder')"
            :rules="[
              { required: true, message: $t('auth.passwordRequired') },
              { validator: validatePasswordLength, message: $t('auth.passwordRule') }
            ]"
          />
          <van-field
            v-model="confirmPassword"
            type="password"
            name="confirmPassword"
            :label="$t('auth.confirmPassword')"
            :placeholder="$t('auth.confirmPasswordPlaceholder')"
            :rules="[
              { required: true, message: $t('auth.confirmPasswordRequired') },
              { validator: validatePassword, message: $t('auth.passwordMismatch') }
            ]"
          />
        </van-cell-group>
        
        <div class="submit-btn">
          <van-button round block type="primary" native-type="submit" size="large">
            {{ $t('auth.registerAction') }}
          </van-button>
        </div>
        
        <div class="login-link">
          {{ $t('auth.haveAccount') }}<span @click="goToLogin">{{ $t('auth.goLogin') }}</span>
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
const confirmPassword = ref('');

// 与后端 schemas/users.py 的 UserRegisterRequest 对齐：
// username 3-50 字符、password 6-72 字符（且不超过 bcrypt 的 72 字节）。
// 前端先挡一道，用户不用等一次 422 才知道密码太短。
const validateUsername = (val) => {
  const n = (val || '').trim().length;
  return n >= 3 && n <= 50;
};

const validatePasswordLength = (val) => {
  const n = (val || '').length;
  return n >= 6 && n <= 72;
};

// 验证两次密码是否一致
const validatePassword = () => {
  return password.value === confirmPassword.value;
};

const onSubmit = async () => {
  // 显示加载提示
  showToast({
    type: 'loading',
    message: t('auth.registering'),
    forbidClick: true,
    duration: 0
  });
  
  try {
    // 调用API注册
    const result = await userStore.register({
      username: username.value,
      password: password.value
    });
    
    if (result.success) {
      showToast({
        type: 'success',
        message: t('auth.registerSuccess')
      });
      
      router.push('/');
    } else {
      showToast({
        type: 'fail',
        message: t('auth.registerFailed')
      });
    }
  } catch (error) {
    showToast({
      type: 'fail',
      message: t('auth.registerFailed')
    });
  }
};

const onClickLeft = () => {
  router.back();
};

const goToLogin = () => {
  router.push('/login');
};
</script>

<style scoped>
.register-page {
  min-height: 100vh;
  background-color: #f7f8fa;
}

.register-container {
  padding-top: 56px;
  display: flex;
  flex-direction: column;
  align-items: center;
}

.register-logo {
  margin: 40px 0;
  text-align: center;
}

.register-logo h2 {
  margin-top: 16px;
  color: #323233;
  font-size: 22px;
}

.register-form {
  width: 100%;
  padding: 0 16px;
}

.submit-btn {
  margin: 24px 16px;
}

.login-link span {
  margin-left: 4px;
}

.login-link {
  text-align: center;
  margin-top: 16px;
  color: #969799;
  font-size: 14px;
}

.login-link span {
  color: #1989fa;
}
</style>