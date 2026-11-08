<template>
  <div class="profile-page">
    <van-nav-bar
      :title="$t('profile.title')"
      left-arrow
      @click-left="$router.back()"
      fixed
    />
    
    <div class="profile-container">
      <van-cell-group inset class="avatar-group">
        <van-cell :title="$t('profile.avatar')" center is-link @click="openEditor">
          <template #right-icon>
            <van-image round width="60" height="60" :src="avatarUrl" />
          </template>
        </van-cell>
      </van-cell-group>
      
      <van-cell-group inset class="info-group">
        <van-cell :title="$t('profile.username')" :value="userInfo?.username || '-'" />
        <van-cell :title="$t('profile.nickname')" :value="userInfo?.nickname || $t('profile.notSet')" />
        <van-cell :title="$t('profile.gender')" :value="genderText" />
        <van-cell :title="$t('profile.phone')" :value="userInfo?.phone || $t('profile.notBound')" />
        <van-cell :title="$t('profile.bio')" :value="userBio || $t('profile.noBio')" />
        <van-cell :title="$t('profile.editProfile')" is-link @click="openEditor" />
      </van-cell-group>
      
      <van-cell-group inset class="security-group">
        <van-cell :title="$t('profile.changePassword')" is-link @click="showPasswordConfirm" />
      </van-cell-group>
    </div>

    <!-- 编辑资料 -->
    <van-popup v-model:show="showEditor" position="bottom" round :style="{ maxHeight: '85%' }">
      <div class="editor">
        <div class="editor-title">{{ $t('profile.editTitle') }}</div>
        <van-form @submit="saveProfile">
          <van-field
            v-model="form.nickname"
            :label="$t('profile.nickname')"
            maxlength="50"
            :placeholder="$t('profile.nicknamePlaceholder')"
          />
          <van-field v-model="form.avatar" :label="$t('profile.avatar')" :placeholder="$t('profile.avatarPlaceholder')">
            <template #button>
              <van-button size="small" type="primary" plain :loading="uploading" @click="pickImage">
                {{ $t('common.upload') }}
              </van-button>
            </template>
          </van-field>
          <input
            ref="fileInput"
            type="file"
            accept="image/*"
            style="display: none"
            @change="onFileChange"
          />
          <van-field
            v-model="form.genderText"
            :label="$t('profile.gender')"
            readonly
            is-link
            @click="showGenderPicker = true"
          />
          <van-field v-model="form.phone" :label="$t('profile.phone')" maxlength="20" :placeholder="$t('profile.optional')" />
          <van-field
            v-model="form.bio"
            :label="$t('profile.bio')"
            type="textarea"
            rows="3"
            autosize
            maxlength="500"
            show-word-limit
            :placeholder="$t('profile.bioPlaceholder')"
          />

          <div class="editor-actions">
            <van-button block type="primary" native-type="submit" :loading="saving">{{ $t('profile.save') }}</van-button>
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
import { useI18n } from 'vue-i18n';
import { uploadImage } from '../api/upload';

const router = useRouter();
const userStore = useUserStore();
const { t } = useI18n();

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
      message: t('profile.loadingProfile'),
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
      showFailToast(t('profile.loadFailed'));
    }
  } catch (error) {
    console.error('获取用户信息请求失败:', error);
    // 确保关闭加载提示
    showToast.clear();
    showToast.fail(t('profile.loadFailed'));
  }
});

const userInfo = computed(() => userStore.userInfo);
const userBio = computed(() => userStore.userInfo?.bio || t('profile.noBio'));
const avatarUrl = computed(
  () => userStore.userInfo?.avatar || 'https://fastly.jsdelivr.net/npm/@vant/assets/cat.jpeg'
);

const genderLabel = gender => {
  if (gender === 'male') return t('profile.genderMale');
  if (gender === 'female') return t('profile.genderFemale');
  return t('profile.genderUnknown');
};
const genderColumns = computed(() => [
  { text: t('profile.genderMale'), value: 'male' },
  { text: t('profile.genderFemale'), value: 'female' },
  { text: t('profile.genderUnknown'), value: 'unknown' }
]);
const genderText = computed(() => genderLabel(userStore.userInfo?.gender));

const showEditor = ref(false);
const showGenderPicker = ref(false);
const saving = ref(false);
const uploading = ref(false);
const fileInput = ref(null);
const form = ref({
  nickname: '',
  avatar: '',
  gender: 'unknown',
  genderText: '',
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
    genderText: genderLabel(gender),
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

const pickImage = () => fileInput.value?.click();

const onFileChange = async event => {
  const file = event.target.files?.[0];
  event.target.value = '';   // 允许连续选同一个文件
  if (!file) return;

  uploading.value = true;
  try {
    form.value.avatar = await uploadImage(file);
    showSuccessToast(t('common.uploadSuccess'));
  } catch (error) {
    showFailToast(t('common.uploadFailed'));
  } finally {
    uploading.value = false;
  }
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
      showSuccessToast(t('common.saveSuccess'));
      showEditor.value = false;
    } else {
      showFailToast(t('profile.saveFailed'));
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
    title: t('profile.changePassword'),
    showCancelButton: true,
    className: 'password-dialog',
    message: h('div', { style: 'text-align: left; padding: 10px 0;' }, [
      h('div', { style: 'margin-bottom: 15px;' }, [
        h('div', { style: 'margin-bottom: 5px; text-align: left;' }, t('profile.passwordCurrent')),
        h('input', {
          type: 'password',
          value: oldPassword.value,
          onInput: (e) => { oldPassword.value = e.target.value },
          style: 'width: 100%; border: 1px solid #dcdee0; border-radius: 4px; padding: 8px; box-sizing: border-box;'
        })
      ]),
      h('div', { style: 'margin-bottom: 15px;' }, [
        h('div', { style: 'margin-bottom: 5px; text-align: left;' }, t('profile.passwordNew')),
        h('input', {
          type: 'password',
          value: newPassword.value,
          onInput: (e) => { newPassword.value = e.target.value },
          style: 'width: 100%; border: 1px solid #dcdee0; border-radius: 4px; padding: 8px; box-sizing: border-box;'
        })
      ]),
      h('div', { style: 'margin-bottom: 15px;' }, [
        h('div', { style: 'margin-bottom: 5px; text-align: left;' }, t('profile.passwordConfirm')),
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
      showToast(t('profile.passwordCurrentRequired'));
      return;
    }
    
    if (!newPassword.value) {
      showToast(t('profile.passwordNewRequired'));
      return;
    }
    
    if (newPassword.value !== confirmPassword.value) {
      showToast(t('profile.passwordMismatch'));
      return;
    }
    
    try {
      // 显示加载提示
      const loadingInstance = showLoadingToast({
        message: t('profile.passwordChanging'),
        forbidClick: true,
        duration: 0
      });
      
      // 调用API更新密码
      const result = await userStore.updatePassword(oldPassword.value, newPassword.value);
      
      // 关闭加载提示
      loadingInstance.close();
      
      if (result && result.success) {
        showSuccessToast(t('profile.passwordChanged'));
      } else {
        showFailToast(t('profile.passwordChangeFailed'));
      }
    } catch (error) {
      console.error('修改密码失败:', error);
      showToast.clear();
      showToast.fail(t('profile.passwordChangeFailed'));
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