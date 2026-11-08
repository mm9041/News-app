import { defineStore } from 'pinia';
import http from '../api/http';

export const useUserStore = defineStore('user', {
  state: () => ({
    userInfo: null,
    isLogin: false,
    userBio: ''
  }),

  getters: {
    getUserInfo: (state) => state.userInfo,
    getLoginStatus: (state) => state.isLogin,
    getUserBio: (state) => state.userInfo?.bio || state.userBio
  },

  actions: {
    async login(userData) {
      try {
        // 发送登录请求。token 由后端写进 httpOnly cookie，
        // 响应体里虽然还带着 token（给 curl / 第三方用），前端**不保存**它。
        const response = await http.post('/api/user/login', {
          username: userData.username,
          password: userData.password
        });

        if (response.data && response.data.code === 200) {
          this.userInfo = response.data.data.userInfo;
          this.isLogin = true;

          return {
            success: true,
            message: '登录成功'
          };
        } else {
          return {
            success: false,
            message: response.data.message || '登录失败'
          };
        }
      } catch (error) {
        console.error('登录请求失败:', error);
        return {
          success: false,
          message: error.response?.data?.message || '登录请求失败，请稍后再试'
        };
      }
    },

    async register(userData) {
      try {
        const response = await http.post('/api/user/register', {
          username: userData.username,
          password: userData.password
        });

        if (response.data && [200, 201].includes(response.data.code)) {
          // 注册成功后端也会下发 cookie，直接算登录
          this.userInfo = response.data.data.userInfo;
          this.isLogin = true;

          return {
            success: true,
            message: '注册成功'
          };
        } else {
          return {
            success: false,
            message: response.data.message || '注册失败'
          };
        }
      } catch (error) {
        console.error('注册请求失败:', error);
        return {
          success: false,
          message: error.response?.data?.message || '注册请求失败，请稍后再试'
        };
      }
    },

    /** 只清本地状态（401 拦截器调用它，不能再发请求，否则会递归） */
    clearSession() {
      this.userInfo = null;
      this.isLogin = false;
    },

    /** 用户主动退出：先让后端删掉 token 行 + 清 cookie，再清本地 */
    async logout() {
      try {
        await http.post('/api/user/logout');
      } catch (e) {
        // 退出失败也要清本地 —— 否则界面卡在"已登录"但什么都做不了
        console.warn('退出登录请求失败:', e?.message);
      }
      this.clearSession();
    },

    /**
     * 启动时恢复会话。
     *
     * token 在 httpOnly cookie 里，JS 读不到，所以只能问一次后端：
     * 200 = 还登着，401 = 游客。skipAuthRedirect 用来避免游客被弹"登录已过期"。
     */
    async restoreSession() {
      try {
        const response = await http.get('/api/user/me', { skipAuthRedirect: true });
        if (response.data?.code === 200) {
          this.userInfo = response.data.data;
          this.isLogin = true;
          return;
        }
      } catch (e) {
        // 401 是正常情况（游客），静默处理
      }
      this.clearSession();
    },
    
    // 获取用户信息
    async getUserInfoDetail() {
      try {
        // 检查是否有token
        if (!this.isLogin) {
          return {
            success: false,
            message: '未登录'
          };
        }
        
        // 发送获取用户信息请求
        const response = await http.get('/api/user/me');
        
        // 检查响应状态
        if (response.data && response.data.code === 200) {
          // 更新用户信息
          this.userInfo = response.data.data;
          
          return {
            success: true,
            message: '获取用户信息成功',
            data: response.data.data
          };
        } else {
          return {
            success: false,
            message: response.data.message || '获取用户信息失败'
          };
        }
      } catch (error) {
        console.error('获取用户信息请求失败:', error);
        return {
          success: false,
          message: error.response?.data?.message || '获取用户信息请求失败，请稍后再试'
        };
      }
    },
    
    // 更新个人资料（昵称 / 头像 / 性别 / 简介 / 手机号）
    async updateUserProfile(profile) {
      if (!this.isLogin) {
        return { success: false, message: '未登录' };
      }
      try {
        const response = await http.patch('/api/user/me', profile);
        if (response.data && response.data.code === 200) {
          // 后端回的是完整用户信息，直接覆盖：昵称、头像、性别一次同步，
          // 评论列表下次加载时也会显示新昵称
          this.userInfo = response.data.data;
          return { success: true, message: '保存成功' };
        }
        return { success: false, message: response.data?.message || '保存失败' };
      } catch (error) {
        return {
          success: false,
          message: error.response?.data?.message || '保存失败，请稍后再试'
        };
      }
    },
    
    // 修改密码
    async updatePassword(oldPassword, newPassword) {
      try {
        // 检查是否有token
        if (!this.isLogin) {
          return {
            success: false,
            message: '未登录'
          };
        }
        
        // 发送修改密码请求
        const response = await http.put('/api/user/password', {
          oldPassword,
          newPassword
        });
        
        // 检查响应状态
        if (response.data && response.data.code === 200) {
          return {
            success: true,
            message: '密码修改成功'
          };
        } else {
          return {
            success: false,
            message: response.data.message || '密码修改失败'
          };
        }
      } catch (error) {
        console.error('修改密码请求失败:', error);
        return {
          success: false,
          message: error.response?.data?.message || '修改密码请求失败，请稍后再试'
        };
      }
    }
  },
  
  // pinia-plugin-persistedstate v4 的写法：key / storage / pick。
  // ⚠️ v3 的 `enabled` + `strategies` 在 4.x 已被移除，写了也不生效：
  // key 会退回默认的 store id，pick 不生效 —— 等于把整个 state 都写进 localStorage。
  persist: {
    key: 'user-store',
    storage: localStorage,
    // 只存登录态，不存 userBio 这类可有可无的字段
    pick: ['isLogin']
  }
});