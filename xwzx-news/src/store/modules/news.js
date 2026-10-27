import { defineStore } from 'pinia'
import http from '../../api/http'

export const useNewsStore = defineStore('news', {
  state: () => ({
    newsList: [],
    newsDetail: {},
    categories: [],
    recommendations: [],
    currentCategory: 1,
    loading: false,
    refreshing: false,
    finished: false,
    categoriesLoading: false
  }),
  
  actions: {
    // 获取新闻分类
    async getCategories() {
      if (this.categoriesLoading) return;
      
      this.categoriesLoading = true;
      
      try {
        // 调用API获取分类列表
        const response = await http.get('/api/news/categories');
        
        if (response.data && response.data.code === 200) {
          // 设置分类数据
          this.categories = [...response.data.data, { id: 10, name: '更多' }];
          
          // 如果没有设置当前分类，则设置为第一个分类
          if (!this.currentCategory && this.categories.length > 0) {
            this.currentCategory = this.categories[0].id;
          }
        }
      } catch (error) {
        console.error('获取新闻分类失败:', error);
        // 设置默认分类，以防API请求失败
        this.categories = [
          { id: 1, name: '头条' },
          { id: 2, name: '社会' },
          { id: 3, name: '国内' },
          { id: 4, name: '国际' },
          { id: 5, name: '娱乐' },
          { id: 6, name: '体育' },
          { id: 7, name: '科技' }
        ];
      } finally {
        this.categoriesLoading = false;
      }
    },
    
    // 获取新闻列表
    async getNewsList(isRefresh = false) {
      if (isRefresh) {
        this.refreshing = true
        this.newsList = []
        this.finished = false
      }
      
      this.loading = true
      
      try {
        // 使用API请求获取新闻列表
        const params = {
          categoryId: this.currentCategory,
          page: isRefresh ? 1 : Math.ceil(this.newsList.length / 10) + 1,
          pageSize: 10
        }
        
        const response = await http.get('/api/news/list', { params });
        
        if (response.data && response.data.code === 200) {
          const newsData = response.data.data.list;
          
          // 更新新闻列表
          this.newsList = isRefresh ? newsData : [...this.newsList, ...newsData];
          
          // 判断是否加载完成
          if (newsData.length < params.pageSize) {
            this.finished = true;
          }
        }

      } catch (error) {
        console.error('获取新闻列表失败:', error)
      } finally {
        this.loading = false
        this.refreshing = false
      }
    },
    
    // 从详情页返回时同步阅读量。
    // 只拉第一页、按 id 合并 views，不重置列表 —— 否则用户已加载的分页和滚动位置都会丢。
    async refreshViews() {
      try {
        const params = {
          categoryId: this.currentCategory,
          page: 1,
          pageSize: 10
        }
        const response = await http.get('/api/news/list', { params });

        if (!response.data || response.data.code !== 200) return;

        const freshList = response.data.data.list || [];
        const viewsById = new Map(freshList.map(item => [item.id, item.views]));
        this.newsList = this.newsList.map(item =>
          viewsById.has(item.id) ? { ...item, views: viewsById.get(item.id) } : item
        );
      } catch (error) {
        // 同步阅读量失败不该影响页面，静默处理
        console.error('同步阅读量失败:', error);
      }
    },

    // 猜你喜欢：按收藏/浏览的分类偏好推荐，游客不请求（避免和列表内容重复）
    async getRecommendations() {
      try {
        const response = await http.get('/api/news/recommend', { params: { limit: 8 } })
        if (response.data && response.data.code === 200) {
          this.recommendations = response.data.data.list || []
        }
      } catch (error) {
        console.error('获取推荐失败:', error)
      }
    },

    // 获取新闻详情
    async getNewsDetail(id) {
      try {
        const response = await http.get('/api/news/detail', { params: { id } });
        
        if (response.data && response.data.code === 200) {
          // 设置新闻详情数据
          this.newsDetail = response.data.data;

        } else {
          console.error('获取新闻详情失败: 接口返回错误');
        }

      } catch (error) {
        console.error('获取新闻详情失败:', error);
      }
    },
    // 切换新闻分类
    changeCategory(categoryId) {
      if (this.currentCategory !== categoryId) {
        this.currentCategory = categoryId
        this.newsList = []
        this.finished = false
        this.getNewsList(true)
      }
    }
  }
})