# 新闻资讯（FastAPI + Vue 3）

移动端优先的新闻阅读练手项目：分类浏览、新闻详情与相关推荐、收藏、浏览历史、AI 问答（SSE 流式）。

后端是 FastAPI + SQLAlchemy 2.0 异步 + MySQL + Redis，前端是 Vue 3 + Vite + Vant 4。

## 技术栈

| 层 | 选型 |
|---|---|
| Web 框架 | FastAPI 0.141（async） |
| ORM / 驱动 | SQLAlchemy 2.0 + aiomysql |
| 数据库 | MySQL 8.0（utf8mb4） |
| 缓存 | Redis（分类、列表、阅读量计数、限流） |
| 认证 | 自建 token（`user_token` 表，库里存 sha256） |
| 大模型 | httpx 转发 OpenAI 兼容接口，SSE 透传 |
| 前端 | Vue 3 + Vite + Pinia + Vue Router + Vant 4 + vue-i18n |

## 目录结构

```
FastAPIProject/
├── main.py                 # 应用入口、lifespan（阅读量回写任务）、CORS
├── database.sql            # 建库建表 + 示例数据（表结构以它为准）
├── requirements.txt
├── .env.example            # 配置模板
├── models/                 # SQLAlchemy 2.0 模型
├── schemas/                # Pydantic 请求/响应模型（camelCase alias 在这里桥接）
├── crud/                   # 数据访问层
│   ├── news_cache.py       # 列表/详情/相关推荐
│   ├── news_search.py      # 全文搜索（ngram + LIKE 兜底）
│   ├── news_views.py       # 阅读量增量叠加与回写
│   ├── admin_news.py       # 后台新闻读写（含缓存失效）
│   └── ...
├── cache/                  # Redis 操作（分类、列表、阅读量计数）
├── routers/                # 路由
├── utils/                  # 认证、响应体、异常、限流、日志
├── scripts/                # 运维脚本（schema 检查）
└── xwzx-news/              # 前端
    └── src/
        ├── api/http.js     # 统一 axios 实例（token 注入、401 处理）
        ├── store/          # Pinia
        └── views/
```

## 快速开始

前置：Python 3.12、MySQL 8.0、Redis 6.2+、Node 18+。

### 1. 初始化数据库

```bash
mysql -u root -p < database.sql
```

会创建 `news_app` 库、建表并灌入示例新闻与分类。

### 2. 启动后端

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows；macOS/Linux 用 source .venv/bin/activate
python -m pip install -r requirements.txt
copy .env.example .env            # 然后填 DB_PASSWORD、AI_API_KEY
uvicorn main:app --port 8000
```

- 接口文档：<http://127.0.0.1:8000/docs>
- 健康检查：`GET /`

### 3. 启动前端

```bash
cd xwzx-news
npm install
npm run dev                       # http://localhost:5173
```

前端默认请求 `http://127.0.0.1:8000`，改端口时在 `xwzx-news/.env` 里写：

```
VITE_API_BASE_URL=http://127.0.0.1:8001
```

同时后端 `.env` 的 `CORS_ALLOW_ORIGINS` 要包含前端的实际地址。

## 配置项

| 变量 | 默认 | 说明 |
|---|---|---|
| `DB_*` | 见 `.env.example` | MySQL 连接；`DB_ECHO=true` 可打 SQL |
| `CORS_ALLOW_ORIGINS` | 5173/5174 的 localhost 与 127.0.0.1 | 逗号分隔，**不要再用 `*`** |
| `REDIS_CONNECT_TIMEOUT` / `REDIS_SOCKET_TIMEOUT` | 0.5 | 必须设小，Redis 挂了要快速降级 |
| `VIEW_FLUSH_INTERVAL` | 30 | 阅读量增量回写间隔（秒） |
| `LOG_LEVEL` | INFO | 日志级别；每行都带 request_id |
| `AI_CHAT_URL` / `AI_API_KEY` / `AI_MODEL` | — | OpenAI 兼容接口；Key 只在后端 |
| `AI_ALLOWED_MODELS` | 空 | 允许客户端切换的模型；空表示只能用 `AI_MODEL` |
| `AI_TIMEOUT` | 120 | 上游超时（秒） |

## 接口一览

所有响应统一为 `{code, message, data}`，参数错误（422）、未登录（401）、限流（429）也走这个结构。

| 方法 | 路径 | 鉴权 | 说明 |
|---|---|---|---|
| GET | `/api/news/categories` | 否 | 分类列表（缓存 2h） |
| GET | `/api/news/list?categoryId&page&pageSize` | 否 | 列表，按发布时间倒序 |
| GET | `/api/news/search?keyword&page&pageSize` | 否 | 全文搜索（标题/摘要/正文） |
| GET | `/api/news/detail?id` | 否 | 详情 + 相关推荐，并把阅读量 +1 |
| POST | `/api/user/register` | 否 | 注册（限 5 次/分/IP） |
| POST | `/api/user/login` | 否 | 登录（限 10 次/分/IP） |
| GET | `/api/user/info` | 是 | 当前用户 |
| PUT | `/api/user/update` | 是 | 改昵称/头像/简介 |
| PUT | `/api/user/password` | 是 | 改密码（限 5 次/分） |
| GET/POST/DELETE | `/api/favorite/*` | 是 | 收藏检查/增删/列表/清空 |
| GET/POST/DELETE | `/api/history/*` | 是 | 历史增删/列表/清空 |
| POST | `/api/ai/chat` | 是 | AI 对话（SSE），限 20 次/分 |
| GET | `/api/ai/history?page&pageSize` | 是 | 聊天记录（倒序） |
| GET | `/api/admin/news?page&pageSize&keyword` | 管理员 | 后台新闻列表（**含正文**） |
| GET | `/api/admin/news/{id}` | 管理员 | 单条详情（编辑回填用） |
| POST | `/api/admin/news` | 管理员 | 新建新闻 |
| PUT | `/api/admin/news/{id}` | 管理员 | 更新（PUT 语义，整份覆盖） |
| DELETE | `/api/admin/news/{id}` | 管理员 | 删除 |

鉴权头：`Authorization: <token>`，带不带 `Bearer ` 前缀都行。

## 管理后台

管理接口要求 `user.is_admin = 1`。把某个用户设为管理员：

```bash
python scripts/make_admin.py <用户名>
# 取消：python scripts/make_admin.py <用户名> --revoke
```

设置后该用户重新登录，「我的」页就会出现「新闻管理」入口（`/admin/news`），
可以新建、编辑、删除新闻。**写操作会自动清掉对应分类的列表缓存**，前台立即可见。

前端入口只是体验层拦截，真正的校验在后端 `get_current_admin`：
未登录返回 401，登录了但不是管理员返回 403。

## 几个设计要点

- **阅读量**：详情页只 `INCR view:delta:{id}`，不写库也不清列表缓存；读的时候 `库内值 + 未回写增量`；后台每 30 秒批量回写并 `DECRBY`。Redis 不可用时退回直写数据库。列表缓存里存的是**数据库原值**，否则命中缓存会把同一份增量重复累加。
- **缓存**：分类 2h、列表 30min，读时回填。后台直接改 `news` 表后，列表最多 30 分钟仍是旧数据，需手动清 `news_list:*`。
- **认证**：`user_token` 只存 `sha256(token)`，明文只在登录/注册响应里返回一次；7 天有效；每用户一条，重新登录会顶掉旧 token（多端互踢）。
- **限流**：基于 Redis 固定窗口，Redis 故障时放行（保护措施不能把业务拦死）。
- **前端请求**：统一走 `src/api/http.js`，token 由 `main.js` 注入，401 全局清登录态并跳登录页。
- **搜索**：`news` 表上建了 ngram 全文索引，查询用 `BOOLEAN MODE` 的短语匹配。
  单字关键词（`ngram_token_size=2` 切不出来）和英文短词（实测 `NASA` 的 MATCH 得分是 0）
  会回退到 LIKE，原因写在 `crud/news_search.py` 顶部注释里。

## 测试

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

测试会连本地 MySQL（读为主），写操作只创建一个临时用户并在用例内清理。

## 已知限制

- **表结构无版本管理**：以 `database.sql` 为准，没有 Alembic；改表后跑 `python scripts/check_schema.py` 检查 ORM 与库是否漂移。
- **回写任务是单进程假设**：`main.py` 里的后台任务在多 worker 部署时会重复扫同一批增量，需要加分布式锁。
- **限流按 IP**：直接读 `request.client.host`，放在反向代理后面会变成所有用户共享一个桶，需要解析 `X-Forwarded-For`。
- **前端分页号取自 `newsList.length`**：只支持顺序加载，不适合跳页。
