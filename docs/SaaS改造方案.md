# SpeakWise SaaS 改造方案

## 决策摘要

| 决策 | 选择 |
|------|------|
| API Key 模型 | 用户自带 Key（不承担 LLM 费用） |
| 部署方式 | PaaS 平台（Render / Railway / Fly.io） |
| 用户认证 | 邮箱 + 密码注册登录（JWT） |
| 数据库 | SQLite → PostgreSQL |
| 前端路由 | useState 切换 → React Router |

---

## 整体架构变化

```
桌面版 (当前)                     SaaS 版 (目标)
─────────────────────────       ─────────────────────────
Electron 壳 → 前端加载          纯 Web 前端 (Vite)
Python 子进程 → 后端启动         独立 uvicorn 进程 (Docker)
SQLite 单文件 → 数据库            PostgreSQL (PaaS 托管)
单用户隐式 → 用户隔离             JWT + users 表 + user_id 全量表
useState → 页面切换              React Router (URL 路由)
全局 llm_client → LLM 调用       每请求独立 client (消除竞态)
内存 dict → 限流/并发锁          数据库级锁（后续可升级 Redis）
```

---

## 第 1 层：删除 Electron 依赖（~1h）

**删除文件/目录**：
- `electron/`（main.js, preload.js, overlay*.js, overlay.html）
- `frontend/src/types/electron.d.ts`

**修改配置**：
- `frontend/vite.config.ts`：`base: "./"` → `base: "/"`
- 移除 `window.speakwise` 类型引用（已有浏览器 fallback）

**影响**：提词器悬浮窗（copilot overlay）功能移除——这是桌面端独占功能，浏览器无法实现透明置顶窗口。其余全部功能保留。

---

## 第 2 层：数据库迁移 SQLite → PostgreSQL（~0.5d）

**依赖变更**：
```toml
# pyproject.toml 新增
"psycopg2-binary>=2.9"
```

**连接层**（`backend/src/db/connection.py`）：
- `DATABASE_URL` 从 `sqlite:///data/copilot.db` → `postgresql://user:pass@host:5432/speakwise`（环境变量注入）
- 移除 `connect_args={"check_same_thread": False}`
- 移除 10+ 个手动 `ALTER TABLE` 迁移块
- `init_db()` 简化为纯 `SQLModel.metadata.create_all(engine)`

**模型层**：无需改动——SQLModel 是数据库无关的，所有模型定义保持不变。

---

## 第 3 层：用户认证体系（~1d）

### 新增表结构

```sql
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);
```

### 现有表改造

```sql
-- user_profiles 加用户隔离
ALTER TABLE user_profiles ADD COLUMN user_id INTEGER REFERENCES users(id);

-- api_keys 从全局(profile_id=0) 改为按用户隔离
ALTER TABLE api_keys ADD COLUMN user_id INTEGER REFERENCES users(id);
UPDATE api_keys SET user_id = (SELECT id FROM users LIMIT 1); -- 迁移现有数据
```

### 新增端点

| 端点 | 用途 |
|------|------|
| `POST /api/auth/register` | 注册 `{email, password}` → JWT |
| `POST /api/auth/login` | 登录 `{email, password}` → JWT |

### JWT 中间件

```python
from fastapi import Depends, HTTPException
from jose import JWTError, jwt

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    session: Session = Depends(get_session)
) -> User:
    payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    user = session.get(User, payload["sub"])
    if not user: raise HTTPException(401)
    return user
```

### 端点改造——所有现有 API 加用户隔离

全部 ~40 个端点从 `get_active_profile(session)` 改为 `get_active_profile(session, current_user.id)`：

```python
# 之前
profile = profile_service.get_active_profile(session)

# 之后
profile = profile_service.get_active_profile(session, current_user.id)
```

`get_active_apikey()` 从全局查询改为按用户查询：
```python
# 之前
k = db.exec(select(ApiKey).where(ApiKey.is_active == True)).first()

# 之后
k = db.exec(select(ApiKey).where(
    ApiKey.user_id == current_user.id,
    ApiKey.is_active == True
)).first()
```

---

## 第 4 层：消除全局状态（~0.5d）

### 问题 1：全局 `llm_client` 单例的竞态条件

```python
# 当前（有问题）：全局单例，每次请求 reconfigure
llm_client = LLMClient()  # client.py:92

# SaaS（修复）：每请求创建独立实例
def get_llm_client(user_id: int, session: Session) -> LLMClient:
    key = get_active_apikey(session, user_id)
    return LLMClient(api_key=key["api_key"], base_url=..., model=key["model"])
```

### 问题 2：`_active_generations` 内存 dict 跨进程不可见

```python
# 当前：进程内 dict
_active_generations: dict[int, bool] = {}  # generate.py:19

# SaaS：数据库表
CREATE TABLE active_generations (
    session_id INTEGER PRIMARY KEY,
    worker_id VARCHAR(100),
    started_at TIMESTAMP DEFAULT NOW()
);
# 插入时用 ON CONFLICT 防重复，请求结束时 DELETE
```

### 问题 3：`_rate_limit` 内存 dict 跨进程不可见

```python
# 当前：进程内 dict
_rate_limit: dict[int, list[float]] = {}  # generate.py:21

# SaaS：数据库查询
SELECT COUNT(*) FROM messages
WHERE session_id = ? AND role = 'user'
  AND created_at > datetime('now', '-30 seconds')
```

---

## 第 5 层：前端路由改造（~0.5d）

### 安装

```bash
npm install react-router-dom
```

### App.tsx 改动

```tsx
// 之前：7 个条件渲染
{page === "conversation" && <ConversationPage ... />}
{page === "profile" && <ProfilePage />}
...

// 之后：React Router
<Routes>
  <Route path="/" element={<ConversationPage ... />} />
  <Route path="/profile" element={<ProfilePage />} />
  <Route path="/jd" element={<JDPage />} />
  <Route path="/review" element={<ReviewPage />} />
  <Route path="/interview" element={<InterviewPage />} />
  <Route path="/prompts" element={<PromptTemplatePage />} />
  <Route path="/settings" element={<SettingsPage />} />
  <Route path="/login" element={<LoginPage />} />
  <Route path="/register" element={<RegisterPage />} />
</Routes>
```

### 导航方式变更

```tsx
// 之前：CustomEvent
window.dispatchEvent(new CustomEvent("navigate", { detail: "settings" }));

// 之后：useNavigate
const navigate = useNavigate();
navigate("/settings?highlight=llm");
```

### Sidebar 导航

`<NavLink>` 替代 `onClick + setPage`，自动高亮当前路由。

---

## 第 6 层：部署配置（~0.5d）

### Dockerfile

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY backend/ ./backend/
COPY frontend/dist/ ./static/
RUN pip install -r requirements.txt
CMD ["uvicorn", "backend.src.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 环境变量

| 变量 | 用途 | 示例值 |
|------|------|--------|
| `DATABASE_URL` | PostgreSQL 连接串 | `postgresql://user:pass@host:5432/speakwise` |
| `JWT_SECRET` | JWT 签名密钥 | `openssl rand -hex 32` |
| `CORS_ORIGINS` | 允许的前端域名 | `https://speakwise.example.com` |
| `DATA_DIR` | 数据目录 | `/data`（Docker volume） |

### Render 部署

```yaml
# render.yaml
services:
  - type: web
    name: speakwise-api
    env: python
    buildCommand: pip install -r requirements.txt
    startCommand: uvicorn backend.src.main:app --host 0.0.0.0 --port $PORT
    envVars:
      - key: DATABASE_URL
        fromDatabase:
          name: speakwise-db
          property: connectionString
      - key: JWT_SECRET
        generateValue: true

databases:
  - name: speakwise-db
    plan: free
```

---

## 不做的部分

- **提词器（Copilot Overlay）**：浏览器无法创建透明置顶窗口，移除
- **PyInstaller 打包**：服务器不需要
- **pyarmor 代码加密**：SaaS 不暴露二进制
- **用户间社交/协作功能**：保持单用户独立使用

---

## 总工时估算：3-4 天

| 层 | 内容 | 工时 |
|----|------|:---:|
| 1 | 删除 Electron | 1h |
| 2 | SQLite → PostgreSQL | 4h |
| 3 | 用户认证 + 全量端点改造 | 8h |
| 4 | 消除全局状态（竞态） | 4h |
| 5 | React Router | 4h |
| 6 | Docker + 部署配置 | 4h |
| **合计** | | **~25h** |
