<template>
  <div class="profile-page">
    <van-nav-bar
      title="个人信息"
      left-arrow
      @click-left="$router.back()"
      fixed
    />
    
    <div class="profile-container">
      <van-cell-group inset class="avatar-group">
        <van-cell title="头像" center is-link @click="openEditor">
          <template #right-icon>
            <van-image round width="60" height="60" :src="avatarUrl" />
          </template>
        </van-cell>
      </van-cell-group>
      
      <van-cell-group inset class="info-group">
        <van-cell title="用户名" :value="userInfo?.username || '-'" />
        <van-cell title="昵称" :value="userInfo?.nickname || '未设置'" />
        <van-cell title="性别" :value="genderText" />
        <van-cell title="手机号" :value="userInfo?.phone || '未绑定'" />
        <van-cell title="个人简介" :value="userBio || '暂无简介'" />
        <van-cell title="编辑资料" is-link @click="openEditor" />
      </van-cell-group>
      
      <van-cell-group inset class="security-group">
        <van-cell title="修改密码" is-link @click="showPasswordConfirm" />
      </van-cell-group>
    </div>

    <!-- 编辑资料 -->
    <van-popup v-model:show="showEditor" position="bottom" round :style="{ maxHeight: '85%' }">
      <div class="editor">
        <div class="editor-title">编辑资料</div>
        <van-form @submit="saveProfile">
          <van-field
            v-model="form.nickname"
            label="昵称"
            maxlength="50"
            placeholder="评论和留言里显示这个名字"
          />
          <van-field v-model="form.avatar" label="头像" placeholder="图片 URL" />
          <van-field
            v-model="form.genderText"
            label="性别"
            readonly
            is-link
            @click="showGenderPicker = true"
          />
          <van-field v-model="form.phone" label="手机号" maxlength="20" placeholder="选填" />
          <van-field
            v-model="form.bio"
            label="简介"
            type="textarea"
            rows="3"
            autosize
            maxlength="500"
            show-word-limit
            placeholder="介绍一下自己"
          />

          <div class="editor-actions">
            <van-button block type="primary" native-type="submit" :loading="saving">保存</van-button>
          </div>
        </van-form>
      </div>
    </van-popup>

    <van-popup v-model:show="showGenderPicker" position="bottom" round>
      <van-picker
        :columns="genderColumns"
        @confirm="onGenderConfirm"
        @cancel="showGenderPicker = false"
      />
    </van-popup>
  </div>
</template>

<script setup>
import { ref, computed, h, onMounted } from 'vue';
import { useUserStore } from '../store/user';
import { showDialog, showToast, showLoadingToast, showSuccessToast, showFailToast } from 'vant';
import { useRouter } from 'vue-router';

const router = useRouter();
const userStore = useUserStore();

// 初始化用户状态
onMounted(async () => {
  // 如果用户未登录，跳转到登录页面
  if (!userStore.getLoginStatus) {
    router.push('/login');
    return;
  }
  
  // 获取用户信息
  try {
    // 显示加载提示
    const loadingInstance = showLoadingToast({
      message: '加载中...',
      forbidClick: true,
      duration: 0
    });
    
    // 使用新的 getUserInfoDetail 方法
    const result = await userStore.getUserInfoDetail();
    
    // 手动关闭加载提示
    loadingInstance.close();
    
    if (result.success) {
      // 显示成功提示
      // showSuccessToast('获取用户信息成功');
    } else {
      console.error('获取用户信息失败:', result.message);
      showFailToast(result.message || '获取用户信息失败');
    }
  } catch (error) {
    console.error('获取用户信息请求失败:', error);
    // 确保关闭加载提示
    showToast.clear();
    showToast.fail('获取用户信息失败');
  }
});

const userInfo = computed(() => userStore.userInfo);
const userBio = computed(() => userStore.userInfo?.bio || '暂无简介');
const avatarUrl = computed(
  () => userStore.userInfo?.avatar || 'https://fastly.jsdelivr.net/npm/@vant/assets/cat.jpeg'
);

const GENDER_LABELS = { male: '男', female: '女', unknown: '保密' };
const genderColumns = [
  { text: '男', value: 'male' },
  { text: '女', value: 'female' },
  { text: '保密', value: 'unknown' }
];
const genderText = computed(() => GENDER_LABELS[userStore.userInfo?.gender] || '保密');

const showEditor = ref(false);
const showGenderPicker = ref(false);
const saving = ref(false);
const form = ref({
  nickname: '',
  avatar: '',
  gender: 'unknown',
  genderText: '保密',
  bio: '',
  phone: ''
});

const openEditor = () => {
  const info = userStore.userInfo || {};
  const gender = info.gender || 'unknown';
  form.value = {
    nickname: info.nickname || '',
    avatar: info.avatar || '',
    gender,
    genderText: GENDER_LABELS[gender] || '保密',
    bio: info.bio || '',
    phone: info.phone || ''
  };
  showEditor.value = true;
};

const onGenderConfirm = ({ selectedOptions }) => {
  const option = selectedOptions[0];
  if (option) {
    form.value.gender = option.value;
    form.value.genderText = option.text;
  }
  showGenderPicker.value = false;
};

const saveProfile = async () => {
  if (!userStore.getLoginStatus) {
    router.push('/login');
    return;
  }

  saving.value = true;
  try {
    // 昵称和简介允许传空串（就是清空）；头像、手机号留空表示「不修改」——
    // phone 上有唯一索引，传空串会让第二个用户直接撞车
    const payload = {
      nickname: form.value.nickname.trim(),
      bio: form.value.bio.trim(),
      gender: form.value.gender
    };
    if (form.value.avatar.trim()) payload.avatar = form.value.avatar.trim();
    if (form.value.phone.trim()) payload.phone = form.value.phone.trim();

    const result = await userStore.updateUserProfile(payload);
    if (result.success) {
      showSuccessToast('已保存');
      showEditor.value = false;
    } else {
      showFailToast(result.message || '保存失败');
    }
  } finally {
    saving.value = false;
  }
};

const showPasswordConfirm = () => {
  // 使用ref创建响应式变量
  const oldPassword = ref('');
  const newPassword = ref('');
  const confirmPassword = ref('');
  
  showDialog({
    title: '修改密码',
    showCancelButton: true,
    className: 'password-dialog',
    message: h('div', { style: 'text-align: left; padding: 10px 0;' }, [
      h('div', { style: 'margin-bottom: 15px;' }, [
        h('div', { style: 'margin-bottom: 5px; text-align: left;' }, '当前密码：'),
        h('input', {
          type: 'password',
          value: oldPassword.value,
          onInput: (e) => { oldPassword.value = e.target.value },
          style: 'width: 100%; border: 1px solid #dcdee0; border-radius: 4px; padding: 8px; box-sizing: border-box;'
        })
      ]),
      h('div', { style: 'margin-bottom: 15px;' }, [
        h('div', { style: 'margin-bottom: 5px; text-align: left;' }, '新密码：'),
        h('input', {
          type: 'password',
          value: newPassword.value,
          onInput: (e) => { newPassword.value = e.target.value },
          style: 'width: 100%; border: 1px solid #dcdee0; border-radius: 4px; padding: 8px; box-sizing: border-box;'
        })
      ]),
      h('div', { style: 'margin-bottom: 15px;' }, [
        h('div', { style: 'margin-bottom: 5px; text-align: left;' }, '确认密码：'),
        h('input', {
          type: 'password',
          value: confirmPassword.value,
          onInput: (e) => { confirmPassword.value = e.target.value },
          style: 'width: 100%; border: 1px solid #dcdee0; border-radius: 4px; padding: 8px; box-sizing: border-box;'
        })
      ])
    ]),
  }).then(async () => {
    // 点击确认按钮
    if (!oldPassword.value) {
      showToast('请输入当前密码');
      return;
    }
    
    if (!newPassword.value) {
      showToast('请输入新密码');
      return;
    }
    
    if (newPassword.value !== confirmPassword.value) {
      showToast('两次密码输入不一致');
      return;
    }
    
    try {
      // 显示加载提示
      const loadingInstance = showLoadingToast({
        message: '修改中...',
        forbidClick: true,
        duration: 0
      });
      
      // 调用API更新密码
      const result = await userStore.updatePassword(oldPassword.value, newPassword.value);
      
      // 关闭加载提示
      loadingInstance.close();
      
      if (result && result.success) {
        showSuccessToast('密码修改成功');
      } else {
        showFailToast((result && result.message) || '密码修改失败');
      }
    } catch (error) {
      console.error('修改密码失败:', error);
      showToast.clear();
      showToast.fail('密码修改失败');
    }
  }).catch(() => {
    // 点击取消按钮
  });
};

</script>

<style scoped>
.profile-page {
  min-height: 100vh;
  background-color: #f7f8fa;
}

.profile-container {
  padding-top: 56px;
  padding-bottom: 20px;
}

.editor {
  padding: 16px;
}

.editor-title {
  text-align: center;
  font-size: 16px;
  font-weight: 600;
  margin-bottom: 12px;
}

.editor-actions {
  margin-top: 20px;
  padding: 0 4px 8px;
}

.avatar-group,
.info-group,
.security-group {
  margin-top: 12px;
}

.password-dialog .van-dialog__content {
  padding: 20px;
}

.password-form .form-item {
  margin-bottom: 15px;
  text-align: left;
}

.password-form .form-item span {
  display: block;
  margin-bottom: 5px;
  text-align: left;
}

.password-form .password-input {
  width: 100%;
  border: 1px solid #dcdee0;
  border-radius: 4px;
  padding: 8px;
  outline: none;
  box-sizing: border-box;
}
</style>