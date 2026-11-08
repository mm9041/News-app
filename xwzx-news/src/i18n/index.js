import { createI18n } from 'vue-i18n';
import { Locale } from 'vant';
import vantZhCN from 'vant/es/locale/lang/zh-CN';
import vantEnUS from 'vant/es/locale/lang/en-US';
import zhCN from './locales/zh-CN.js';
import enUS from './locales/en-US.js';

// 在模块加载时创建唯一实例。路由标题和路由守卫也需要用它，
// 每次 setupI18n() 都新建实例会导致这些地方拿到另一份 locale。
const savedLanguage = localStorage.getItem('language') || 'zh-CN';

// Vant 的 Picker、Dialog、PullRefresh 等组件有一套独立文案。
// 必须同步切换，否则英文页面里的“取消/确认/下拉刷新”仍会是中文。
Locale.use(savedLanguage, savedLanguage === 'en-US' ? vantEnUS : vantZhCN);

export const i18n = createI18n({
  legacy: false,
  locale: savedLanguage,
  fallbackLocale: 'zh-CN',
  messages: {
    'zh-CN': zhCN,
    'en-US': enUS
  }
});

document.querySelector('html')?.setAttribute('lang', savedLanguage);

// 保留原入口，便于 main.js 继续按组件插件方式安装
export function setupI18n() {
  return i18n;
}

// 动态切换语言
export function setI18nLanguage(i18n, locale) {
  if (i18n.mode === 'legacy') {
    i18n.global.locale = locale;
  } else {
    i18n.global.locale.value = locale;
  }
  document.querySelector('html').setAttribute('lang', locale);
}