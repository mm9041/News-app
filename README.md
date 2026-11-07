# 新闻资讯（FastAPI + Vue 3）

移动端优先的新闻阅读练手项目：分类浏览、新闻详情与相关推荐、收藏、浏览历史、AI 问答（SSE 流式）。

后端是 FastAPI + SQLAlchemy 2.0 异步 + MySQL + Redis，前端是 Vue 3 + Vite + Vant 4。

## 技术栈

| 层 | 选型 |
|---|---|
| Web 框架 | FastAPI 0.141（async） |
| ORM / 驱动 | SQLAlchemy 2.0 + aiomysql |
| 数据库 | MySQL 8.0（utf8mb4） |
| 缓存 | Redis（分类、列表、详情、相关推荐、阅读量计数、限流） |
| 认证 | 自建 token（`user_token` 存 sha256）；浏览器走 httpOnly cookie，脚本可走 `Authorization` |
| 大模型 | httpx 转发 OpenAI 兼容接口，SSE 透传 |
| 前端 | Vue 3 + Vite + Pinia + Vue Router + Vant 4 + vue-i18n |

## 目录结构

```
FastAPIProject/
├── main.py                 # 应用入口、中间件、lifespan（阅读量回写任务）、/health、/metrics
├── database.sql            # 建库建表 + 示例数据（新装库以它为准）
├── alembic.ini             # 表结构增量迁移（连接串运行时从 .env 读）
├── migrations/             # Alembic 迁移脚本，0001 是空基线
├── requirements.txt
├── .env.example            # 配置模板
├── config/                 # 数据库/Redis/AI 的配置读取（都走 .env）
├── models/                 # SQLAlchemy 2.0 模型
├── schemas/                # Pydantic 请求/响应模型（camelCase alias 在这里桥接）
├── crud/                   # 数据访问层
│   ├── news_cache.py       # 列表/详情/相关推荐（含 extras 缓存）
│   ├── news_search.py      # 全文搜索（ngram + LIKE 兜底）
│   ├── news_views.py       # 阅读量增量叠加与回写
│   ├── recommend.py        # 个性化推荐
│   ├── like.py             # 点赞
│   ├── admin_news.py       # 后台新闻读写（含缓存失效）
│   └── ...
├── cache/                  # Redis key 约定与读写（分类、列表、详情 extras、阅读量计数）
├── routers/                # 路由（news / comment / tag / user / admin / ai ...）
├── utils/                  # 认证、响应体、异常、限流、日志、指标、健康探测
├── scripts/                # 运维脚本（schema 检查、压测、建管理员、AI 会话迁移）
├── tests/                  # pytest（连真实库的集成测试）
└── xwzx-news/              # 前端
    └── src/
        ├── api/http.js     # 统一 axios 实例（withCredentials、401 处理）
        ├── store/          # Pinia
        └── views/
```

## 快速开始

前置：Python 3.12、MySQL 8.0、Redis 6.2+（compose 用 8-alpine、CI 用 7）、Node 18+。

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
- 健康检查：`GET /health` —— MySQL 挂返回 503；Redis 挂只标 `degraded`、仍 200，
  需要「Redis 也必须活」的探针用 `GET /health?strict=true`
- 指标：`GET /metrics`（Prometheus 文本格式）。默认只允许**本机直连**，
  要从别的机器/容器抓就配 `METRICS_TOKEN`，请求带 `Authorization: Bearer <token>` 或 `?token=`

### 3. 启动前端

```bash
cd xwzx-news
npm install
npm run dev                       # http://localhost:5173
```

前端默认走**相对路径** `/api`，由 Vite 的 `server.proxy` 反代到 `http://127.0.0.1:8000`
（见 `xwzx-news/vite.config.js`）。这一步不是可选项：登录 token 在 httpOnly + SameSite=Lax
的 cookie 里，换成绝对地址后浏览器会当成跨站请求，cookie 根本不会发送。

后端换端口时改 `vite.config.js` 里的 `proxy.target` 即可。
非要直连绝对地址的话，在 `xwzx-news/.env` 里设：

```
VITE_API_BASE_URL=http://127.0.0.1:8001
```

同时后端 `.env` 的 `CORS_ALLOW_ORIGINS` 要包含前端实际地址 —— 但跨站 cookie 仍然不生效，
所以只在调试脚本类场景用。

## 配置项

| 变量 | 默认 | 说明 |
|---|---|---|
| `DB_*` | 见 `.env.example` | MySQL 连接；`DB_ECHO=true` 可打 SQL |
| `CORS_ALLOW_ORIGINS` | 5173/5174 的 localhost 与 127.0.0.1 | 逗号分隔，**不要再用 `*`** |
| `REDIS_CONNECT_TIMEOUT` / `REDIS_SOCKET_TIMEOUT` | 0.5 | 必须设小，Redis 挂了要快速降级 |
| `COOKIE_SECURE` | false | 上 HTTPS 后置 true，否则 cookie 明文传输 |
| `METRICS_TOKEN` | 空 | 空表示 `/metrics` 只允许本机直连；非空则要求 Bearer token |
| `VIEW_FLUSH_INTERVAL` | 30 | 阅读量增量回写间隔（秒） |
| `LOG_LEVEL` | INFO | 日志级别；每行都带 request_id |
| `AI_CHAT_URL` / `AI_API_KEY` / `AI_MODEL` | — | OpenAI 兼容接口；Key 只在后端 |
| `AI_ALLOWED_MODELS` | 空 | 允许客户端切换的模型；空表示只能用 `AI_MODEL` |
| `AI_TIMEOUT` | 120 | 上游超时（秒） |

## 接口一览

所有业务响应统一为 `{code, message, data}`。成功时 HTTP 状态码与 `code` 一致：
创建资源返回 **201** 并通过 `Location` 指向新资源；删除、更新返回 200；
参数错误、未登录、权限不足、不存在、唯一约束冲突和限流分别返回
**422 / 401 / 403 / 404 / 409 / 429**。这些错误均已写入 OpenAPI。

| 方法 | 路径 | 鉴权 | 说明 |
|---|---|---|---|
| GET | `/api/news/categories` | 否 | 分类列表（缓存 2h） |
| GET | `/api/news?categoryId&page&pageSize` | 否 | 列表，按发布时间倒序 |
| GET | `/api/news/search?keyword&page&pageSize` | 否 | 全文搜索（标题/摘要/正文） |
| GET | `/api/news/suggest?keyword` | 否 | 搜索联想（标题前缀，最多 10 条） |
| GET | `/api/news/{news_id}` | 否 | 详情 + 相关推荐 + 点赞状态，并把阅读量 +1 |
| GET | `/api/news/recommend?limit` | 否 | 猜你喜欢；登录后按兴趣推荐，游客给热门 |
| PUT | `/api/news/{news_id}/like` | 是 | 点赞（幂等） |
| DELETE | `/api/news/{news_id}/like` | 是 | 取消点赞（幂等） |
| GET | `/api/comment?newsId&page&pageSize` | 否 | 一级评论分页，每条带出回复 |
| POST | `/api/comment` | 是 | 发表评论 / 回复（传 `parentId`），返回 201 |
| DELETE | `/api/comment/{comment_id}` | 是 | 删除评论（本人或管理员，级联删回复） |
| GET | `/api/tag/hot?limit` | 否 | 标签墙（按引用次数） |
| GET | `/api/tag/{tag_id}/news?page` | 否 | 某标签下的新闻 |
| GET | `/api/source/{source_id}/news?page` | 否 | 某报纸来源下的新闻 |
| GET/POST/DELETE | `/api/follow*` | 部分 | 关注作者：关注/取关/状态/我关注的作者（需登录）、作者新闻（公开） |
| POST | `/api/upload/image` | 是 | 上传图片（≤5MB，JPG/PNG/GIF/WebP），返回 201 |
| GET | `/api/notification?page&pageSize` | 是 | 通知列表，附带未读数 |
| GET | `/api/notification/unread-count` | 是 | 未读数 |
| PATCH | `/api/notification/{notification_id}` | 是 | 更新通知状态，body `{"isRead": true}` |
| PATCH | `/api/notification` | 是 | 全部标记已读，body `{"isRead": true}` |
| POST | `/api/user/register` | 否 | 注册（限 5 次/分/IP），返回 201 |
| POST | `/api/user/login` | 否 | 登录（限 10 次/分/IP） |
| GET | `/api/user/me` | 是 | 当前用户 |
| PATCH | `/api/user/me` | 是 | 部分更新昵称/头像/简介 |
| PUT | `/api/user/password` | 是 | 改密码（限 5 次/分） |
| POST | `/api/user/logout` | 否 | 退出：删除库里的 token 行 + 清 cookie |
| GET/POST/DELETE | `/api/favorite[/{news_id}]` | 是 | 收藏检查/新增（201）/删除/列表/清空 |
| GET/POST/DELETE | `/api/history[/{news_id}]` | 是 | 历史新增/列表/删除/清空 |
| POST | `/api/ai/chat` | 是 | AI 对话（SSE），限 20 次/分 |
| GET | `/api/ai/history?page&pageSize` | 是 | 聊天记录（倒序） |
| POST | `/api/ai/conversations` | 是 | 新建会话，返回 201 |
| GET | `/api/ai/conversations?page` | 是 | 会话列表（只含有消息的） |
| GET | `/api/ai/conversations/{conversation_id}` | 是 | 会话的消息流 |
| DELETE | `/api/ai/conversations/{conversation_id}` | 是 | 删除会话（级联删消息） |
| GET | `/api/admin/news?page&pageSize&keyword` | 管理员 | 后台新闻列表（**含正文**） |
| GET | `/api/admin/news/{news_id}` | 管理员 | 单条详情（编辑回填用） |
| POST | `/api/admin/news` | 管理员 | 新建新闻，返回 201 |
| PUT | `/api/admin/news/{news_id}` | 管理员 | 更新（PUT 语义，整份覆盖） |
| DELETE | `/api/admin/news/{news_id}` | 管理员 | 删除 |
| GET | `/api/admin/stats?days&top` | 管理员 | 看板：总览 / 趋势 / 分类 / 热门 |
| GET | `/api/admin/users?page&pageSize&keyword` | 管理员 | 用户列表（带评论数） |
| PATCH | `/api/admin/users/{user_id}` | 管理员 | 部分更新 `banned` / `isAdmin` |
| DELETE | `/api/admin/users/{user_id}` | 管理员 | 删除用户（级联清其数据） |

不在 `/api` 前缀下的三个：`GET /`（占位，返回 Hello World）、`GET /health`（依赖探测）、
`GET /metrics`（Prometheus 文本，默认仅本机可访问）。

旧客户端的 `PATCH /api/user`、通知的 `PUT .../read`、`PUT .../read-all` 以及后台
`PUT .../ban`、`PUT .../admin` 仍在运行时保留，但已从 OpenAPI 隐藏，新代码应使用上表路径。

### REST 约定与保留的 RPC 风格

- 新闻、评论、收藏、历史、AI 会话使用「集合 + `/{id}`」资源路径；点赞用幂等的
  `PUT/DELETE /api/news/{id}/like`，创建用 `POST` + 201 + `Location`。
- 登录、登出、AI 对话、上传等接口天然具有命令语义，保留为动作式端点，这是常见的
  pragmatic REST 取舍，不为了形式纯度额外包一层虚假资源。
- 当前前缀仍有单复数混用（`/api/comment`、`/api/user` 等）。全量改名会破坏现有前端、
  脚本和测试，因此不在本轮做；若未来对外开放 API，应在 `/api/v2` 中统一为复数资源，
  并让旧路径以 Deprecated alias 过渡。
- 删除接口仍返回 200 + 统一响应体，没有改成 204，因为前端和测试依赖 `message` /
  `data` 判断结果；这是有意保留的契约。

鉴权：浏览器走 **httpOnly cookie**（登录/注册时下发 `access_token`，JS 读不到，XSS 偷不走）；
脚本 / curl 仍可用 `Authorization: <token>`（带不带 `Bearer ` 前缀都行）。两条通道都支持。

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
- **AI 会话**：`ai_conversation` + `ai_chat.conversation_id`，一个会话下多轮问答。
  首次提问时后端自动建会话（标题取首条提问前 30 字），并把 id 通过 SSE 响应头
  `X-Conversation-Id` 回传，前端不用额外发一次「创建会话」请求。
  历史数据由 `scripts/migrate_ai_conversations.py` 按「同用户 + 间隔 30 分钟」补了会话。
- **缓存**：分类 2h、列表 30min、**详情 2~3 分钟（TTL 带随机抖动）**，读时回填。
  详情缓存顺带处理了三件事：查不到的 id 写 30 秒空值缓存（防穿透）、
  过期瞬间用 Redis 互斥锁只放一个请求回源（防击穿）、TTL 加抖动避免同批失效（防雪崩）。
  详情页的**标签与相关推荐**单独缓存（`news:extras:{id}`，同 TTL），命中后详情只剩一次点赞查库；
  后台改/删新闻会同时清掉这两个 key。
- **认证**：`user_token` 只存 `sha256(token)`，明文只在登录/注册响应里返回一次；7 天有效；每用户一条，重新登录会顶掉旧 token（多端互踢）。
  浏览器端 token 放在 **httpOnly + SameSite=Lax** 的 cookie 里（`access_token`），前端不再写 localStorage，
  启动时靠 `GET /api/user/me` 探活恢复登录态；`POST /api/user/logout` 会删库里的 token 行并清 cookie。
  开发态前端必须走 Vite 的 `server.proxy`（见 `vite.config.js`）保持同源，否则跨站请求不会带 Lax cookie。
- **限流**：基于 Redis 的滑动窗口（ZSET + Lua，判断与写入在同一段脚本里），Redis 故障时放行（保护措施不能把业务拦死）。
- **健康检查**：`GET /health` 把 MySQL 当硬依赖（挂了返回 503），Redis 当可选的加速层（挂了只标 `degraded`、仍返回 200，否则负载均衡会把功能完全正常的实例摘掉）；需要「Redis 也必须活」的探针用 `GET /health?strict=true`。
- **前端请求**：统一走 `src/api/http.js`，只配 `withCredentials`，不再往 header 里塞 token；
  401 时全局清登录态并跳登录页（启动时的会话探活带 `skipAuthRedirect`，游客不会被弹窗）。
- **搜索**：`news` 表上建了 ngram 全文索引，查询用 `BOOLEAN MODE` 的短语匹配。
  单字关键词（`ngram_token_size=2` 切不出来）和英文短词（实测 `NASA` 的 MATCH 得分是 0）
  会回退到 LIKE，原因写在 `crud/news_search.py` 顶部注释里。
- **评论**：只有两级（评论 + 回复）。回复的 `parent_id` 始终指向一级评论，
  「回复给谁」单独记在 `reply_to_user_id`，所以不会出现无限嵌套。
  列表公开可读，`canDelete` 由后端算好（本人或管理员），前端不做二次判断。
- **标签**：自由文本，最多 5 个/篇，靠 `tag.name` 与 `(news_id, tag_id)` 两个唯一索引去重。
- **点赞**：`news_like` 表 `(user_id, news_id)` 唯一索引，PUT/DELETE 都是幂等的
  （没用 toggle，就是怕弱网重试把状态翻回去）。点赞数不冗余到 `news` 表，实时 COUNT。
- **收藏 / 浏览历史**：写入前先判 `news` 是否存在（不存在返回 404，不再靠外键报错兜成 400）；
  取消收藏幂等（没收藏过也返回 200）；历史记录靠 `(user_id, news_id)` 唯一索引做
  `ON DUPLICATE KEY UPDATE`，同一篇新闻看多少次都只有一条、只更新时间。
  唯一约束冲突的文案按约束名分别返回（重复收藏不会再弹出「用户名已存在」）。
- **推荐**：收藏权重 3、浏览权重 1，取 Top3 分类的未读新闻，不足用热门补齐（同样排除已读）；
  游客或新用户直接给全站热门。
- **图片上传**：类型按**文件头魔数**判断，不看文件名和 Content-Type（改后缀绕不过去）；
  文件名由服务端用 uuid 生成，杜绝路径穿越；单个文件 ≤5MB。
- **通知**：接收者是 `news.user_id`（后台发布时记录）。评论、点赞触发；自己操作自己的不通知；
  重复点赞（幂等）只通知一次。没有实时推送，进「消息通知」页时才拉取。

## Docker 部署

不想装 MySQL / Redis / Python 环境时，用 compose 一次起全套：

```bash
docker compose up -d --build
```

**宿主机端口刻意错开**，可以和本机已装的服务共存：

| 宿主机 | 容器 | 服务 |
|---|---|---|
| 13306 | 3306 | MySQL |
| 16379 | 6379 | Redis |
| 18000 | 8000 | 后端 |
| 8080 | 80 | 前端 |

- 前端 <http://localhost:8080>，后端 <http://localhost:18000>，账号 `admin / admin`
- 容器之间用服务名互访（`mysql:3306` / `backend:8000`），宿主机映射只影响你从外部访问
- 首次启动会自动执行 `database.sql`，建表并灌入示例新闻
- 数据库和上传的图片都在 named volume 里，`docker compose down` 不丢数据，加 `-v` 才会删
- 前端构建时把 `VITE_API_BASE_URL` 设成空串，请求走 nginx 反代到后端，因此**不经过 CORS**
- 后端以非 root（UID 10001）运行，镜像自带 `HEALTHCHECK`（探 `/health`）；
  compose 里前端要等后端 `service_healthy` 才启动
- 要接真实的大模型，先在项目根 `.env` 里配好 `AI_CHAT_URL` / `AI_API_KEY`，compose 会读

## 测试

```bash
python -m pip install -r requirements-dev.txt
python -m pytest
```

> `pytest.ini` 里已经有 `addopts = -q`，命令行**别再传 `-q`** —— 叠成 `-qq` 会把
> 「N passed」汇总行一起压掉，只剩失败列表。

测试会连本地 MySQL（读为主），写操作只创建临时用户并在用例内清理。

## CI

`.github/workflows/ci.yml` 在每次 push / PR 时跑两个 job：

- **backend**：起 mysql:8.0 + redis:7 service → 导入 `database.sql` → `check_schema` → `pytest`
- **frontend**：`npm ci` + `npm run build`

## 压测

```bash
python scripts/loadtest.py --path "/api/news/detail?id=45" --concurrency 20 --duration 8
```

在 20 并发、本机 MySQL、压测客户端与服务端**同机**的条件下实测
（2026-11-04，`scripts/loadtest.py`，每个接口跑 8 秒）：

| 接口 | QPS | P50 | P95 |
|---|---|---|---|
| 详情（缓存 + 1 次查库） | 175 | 110 ms | 141 ms |
| 列表（缓存 + 分页） | 177 | 111 ms | 136 ms |
| 搜索（FULLTEXT 单查询） | 169 | 112 ms | 151 ms |

三个接口的 QPS 都落在 170~180，说明 20 并发下的瓶颈已经**不是某条 SQL**，
而是单进程（Python 序列化 + 事件循环）本身 —— 客户端和服务端还抢同一个 CPU。

改造前详情要查点赞、相关推荐、标签三次，P50 明显高于列表；把后两者并入缓存后
（只剩一次点赞查库）已经和列表持平。数值仅供同机横向对比，别当容量规划依据。

## 表结构变更（Alembic）

新装库仍然是 `mysql < database.sql` 一次建好 15 张表和种子数据；Alembic 只记录**之后的增量**。

```bash
python -m alembic current                    # 当前版本
python -m alembic stamp 0001                 # 已有库接入：标记到基线，不执行任何 DDL
python -m alembic revision --autogenerate -m "说明"
python -m alembic upgrade head
python -m alembic check                      # 模型与库是否一致（可进 CI）
```

`0001` 是**空基线**（`upgrade()` 里只有 pass），因为建表这件事仍然归 `database.sql`。
两处已知取舍写在 `migrations/env.py` 里：

- **不比外键**：库里的外键是显式命名的（`fk_news_category`），模型里是匿名 `ForeignKey(...)`，
  否则每轮 autogenerate 都会报一轮 remove+add 的空操作。改外键要手写迁移。
- 索引方向、全文索引这类 DDL `autogenerate` 表达不出来，生成后**务必人工过一遍**。

## 已知限制

- **回写任务是单进程假设**：`main.py` 里的后台任务在多 worker 部署时会重复扫同一批增量，需要加分布式锁。
- **限流按 IP**：本地直连时读 `request.client.host`；容器里 uvicorn 开了 `--proxy-headers`，
  反代后能拿到真实 IP，但 `--forwarded-allow-ips=*` 信任所有来源，**后端不能直接暴露公网**。
- **前端新闻列表只支持顺序加载**：`store/modules/news.js` 用显式 `page` 加
  `requestSeq` 推进分页并丢弃旧请求，不支持任意跳页；跳页需要后端提供稳定游标或独立页码查询。
