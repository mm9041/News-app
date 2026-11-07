import { defineStore } from 'pinia';

export const useThemeStore = defineStore('theme', {
  state: () => ({
    currentTheme: localStorage.getItem('theme') || 'light', // 默认浅色主题
    themes: {
      light: {
        name: '浅色模式',
        backgroundColor: '#f7f8fa',
        surfaceColor: '#ffffff',
        surfaceMuted: '#f2f3f5',
        textColor: '#323233',
        textColorLight: '#646566',
        textColorLighter: '#969799',
        borderColor: '#ebedf0',
        primaryColor: '#1989fa',
        secondaryColor: '#f5f5f5',
      },
      dark: {
        name: '深色模式',
        backgroundColor: '#121212',
        surfaceColor: '#1f1f1f',
        surfaceMuted: '#2d2d2d',
        textColor: '#f5f5f5',
        textColorLight: '#c8c9cc',
        textColorLighter: '#969799',
        borderColor: '#3a3a3a',
        primaryColor: '#4c8bf5',
        secondaryColor: '#2d2d2d',
      },
      blue: {
        name: '蓝色主题',
        backgroundColor: '#e6f7ff',
        surfaceColor: '#ffffff',
        surfaceMuted: '#eef8ff',
        textColor: '#263445',
        textColorLight: '#506070',
        textColorLighter: '#7a8b9d',
        borderColor: '#d6e4f0',
        primaryColor: '#1890ff',
        secondaryColor: '#bae7ff',
      },
      green: {
        name: '绿色主题',
        backgroundColor: '#f6ffed',
        surfaceColor: '#ffffff',
        surfaceMuted: '#f0f8e9',
        textColor: '#263326',
        textColorLight: '#526152',
        textColorLighter: '#7d8b7d',
        borderColor: '#d9e8d2',
        primaryColor: '#52c41a',
        secondaryColor: '#d9f7be',
      }
    }
  }),
  
  getters: {
    getCurrentTheme: (state) => state.currentTheme,
    getThemeConfig: (state) => state.themes[state.currentTheme],
    getAllThemes: (state) => Object.keys(state.themes).map(key => ({
      id: key,
      name: state.themes[key].name,
      primaryColor: state.themes[key].primaryColor
    }))
  },
  
  actions: {
    setTheme(themeName) {
      if (this.themes[themeName]) {
        this.currentTheme = themeName;
        localStorage.setItem('theme', themeName);
        this.applyTheme();
      }
    },
    
    applyTheme() {
      const theme = this.themes[this.currentTheme];
      if (!theme) return;

      const root = document.documentElement;
      root.style.setProperty('--background-color', theme.backgroundColor);
      root.style.setProperty('--surface-color', theme.surfaceColor);
      root.style.setProperty('--surface-muted', theme.surfaceMuted);
      root.style.setProperty('--text-color', theme.textColor);
      root.style.setProperty('--text-color-light', theme.textColorLight);
      root.style.setProperty('--text-color-lighter', theme.textColorLighter);
      root.style.setProperty('--border-color', theme.borderColor);
      root.style.setProperty('--primary-color', theme.primaryColor);
      root.style.setProperty('--secondary-color', theme.secondaryColor);
      root.style.colorScheme = this.currentTheme === 'dark' ? 'dark' : 'light';
    },
    
    initTheme() {
      this.applyTheme();
    }
  }
});