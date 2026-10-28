# LiteApp Studio (AI 静态微应用开发与发布平台)

<div align="center">

![LiteApp Studio Logo](app/static_ui/favicon.svg)

### 极轻量、免构建、容器化的 AI 单页微应用工坊与静态资源托管门户

**零外部打包依赖** · **OpenAI 兼容流式生成** · **Zip Slip 安全防御** · **智能目录扁平化** · **Docker & Coolify 原生就绪**

</div>

---

## 🌟 项目简介

**LiteApp Studio** 是一个专为轻量微应用打造的全栈开发与托管平台。它集成了常用工具应用门户、AI 驱动的单文件 HTML 实时生成工坊以及支持单 HTML / 完整静态目录 ZIP 包的安全托管器。

无论是让大语言模型为你即刻生成一个番茄钟、Markdown 简历渲染器，还是把本地开发打包好的前端单页（Vue/React/Vanilla JS）打包成 ZIP 拖拽上线，LiteApp Studio 都能在秒级为你提供专属的独立运行沙盒与外链分享路由。

---

## 🚀 核心功能特性

### 1. 应用门户广场 (App Portal)
- **卡片式瀑布流展示**：直观展示应用标题、功能简介、分类 Tag、图标 Emoji、创建/更新时间以及累计访问次数。
- **实时过滤与检索**：支持分类 Pill 标签快速筛选，输入关键词即时防抖搜索。
- **一键独立运行**：每个微应用拥有标准化独立访问路径（`/s/{app_slug}/`），支持在新标签页全屏独立运行。
- **分享与生命周期管理**：支持一键复制分享链接、在线修改应用元信息、重新上传代码/文件热覆盖，以及一键彻底删除。

### 2. AI 创客工作台 (AI Studio)
- **OpenAI 兼容端点配置**：支持在 UI 界面增删查改任意兼容 OpenAI 规范的模型端点（如 DeepSeek、OneAPI、Ollama、Claude、GPT-4o 等），密钥后端安全存储，前端脱敏展示。
- **已发布微应用二次迭代编辑**：支持从广场一键将任意微应用源码载入 AI 工作台，保留全部代码与上下文，通过 Prompt 增量对话或编辑器手动微调，支持“覆盖更新原应用”或“另存为新微应用”。
- **沉浸式分屏交互**：
  - **左侧工作区**：Prompt 灵感提示词、多轮对话流、实时源码查看与编辑。
  - **右侧沙盒区**：原生 `iframe` 安全沙盒实时渲染，支持桌面端（100%）、平板（768px）、移动端（375px）多视口模拟切换与热重载。
- **SSE 流式代码输出**：通过 Server-Sent Events 流式接收大模型生成的 HTML 代码块，边生成边注入沙盒。
- **一键发布到门户**：满意后点击“发布到门户”，自动写入数据存储并生成专属访问路径。

### 3. 微应用版本快照与一键回滚 (Version Rollback)
- **自动版本归档**：初次发布、代码热覆盖、ZIP 包上传或 AI 工坊迭代时，系统自动对前序状态打上版本物理快照（存放在 `/app/data/backups/{app_slug}/v{N}/`）。
- **版本历史时间轴**：在广场卡片直接查看任意应用的版本号、更新说明与提交时间。
- **快照沙盒预览与一键回滚**：支持在独立窗口沙盒预览历史版本效果，并支持一键无损回滚，系统在回滚前自动建立保护性快照。

### 4. 智能微应用生成向导 (Agent / n8n / 表单生成器)
- **🤖 自定义 AI 对话智能体单页**：配置角色设定 (System Prompt)、问候语、推荐预设问题，一键生成类似 ChatGPT 的专业暗黑单页对话应用（基于平台已配置的模型端点免密流式对话）。
- **⚡ n8n 自动化流微应用**：
  - **n8n Chat 嵌入**：全屏自适应嵌入 n8n Webchat 窗口。
  - **n8n Webhook 触发与执行看板**：动态入参表单配置，一键触发 n8n 工作流并实时回显执行耗时、HTTP 状态码及格式化 JSON / Markdown 响应。
- **📝 智能数据采集表单生成引擎**：
  - **自然语言需求推导**：输入表单需求即可智能反推生成现代 Tailwind 表单（支持文本、下拉、单选、复选、邮箱、手机号等）。
  - **表格文件推断生成**：上传 CSV 或 Excel (.xlsx) 模板表格，自动识别表头与字段类型。
  - **数据收集与导出**：自带 LocalStorage 本地暂存、防误关草稿箱、一键导出 CSV 报表，并支持异步 POST 转发至飞书/钉钉/企业微信/n8n Webhook。

### 5. 手动上传与智能部署器 (Manual Uploader)
- **模式 A（单 HTML 上传/源码粘贴）**：直接拖拽单文件 `.html` 或粘贴源码，自动保存为标准 `index.html`。
- **模式 B（静态目录 ZIP 压缩包上传）**：支持上传包含 HTML/CSS/JS/图片/字体等完整前端资源的 `.zip` 压缩包。
- **企业级解压安全与智能扁平化**：
  - **防范 Zip Slip 攻击**：严格禁止包含 `..` 相对路径或绝对路径的危险条目，确保所有解压条目收敛在受控目录下。
  - **防止 Zip 炸弹**：校验解压总容量上限（默认 50MB）。
  - **智能扁平化 (Flatten Root Directory)**：若压缩包根目录下无 `index.html` 而是包裹了单层子文件夹（例如 `dist/` 或 `my-project-master/`），系统会自动将子目录内容提升至根目录，确保相对路径资源不丢失。

### 4. 路由规范化与访问统计
- **末尾斜杠强制重定向**：访问 `/s/{app_slug}` 时自动 307 重定向至 `/s/{app_slug}/`，彻底解决浏览器解析相对路径静态资源（如 `./assets/style.css`）时的路径错乱问题。
- **访问计数**：访问应用主页时，系统原子累加该应用的浏览量。

### 5. 权限与鉴权体系 (Admin Auth)
- 应用广场与 `/s/{app_slug}/` 微应用访问完全公开。
- 进入 AI 工作台生成代码、发布/覆盖/删除应用、增删模型配置均需验证管理员密码（通过环境变量 `ADMIN_PASSWORD` 设定）。

---

## 🏗️ 架构与目录结构

```text
LiteApp/
├── app/
│   ├── __init__.py
│   ├── main.py                     # FastAPI 应用入口、生命周期钩子、全局路由与静态 UI 挂载
│   ├── core/                       # 核心基础组件
│   │   ├── config.py               # 环境变量配置管理 (Settings 单例)
│   │   ├── logger.py               # 统一格式化日志记录器 (禁止裸 print)
│   │   └── security.py             # 管理员 Token 鉴权、HMAC-SHA256 签名与依赖注入
│   ├── model/                      # 数据模型与建表 SQL
│   │   └── models.py               # apps 表与 llm_providers 表 DDL
│   ├── schema/                     # Pydantic 校验模型
│   │   ├── app_schema.py           # 微应用 CRUD 校验模型与 Slug 正则校验
│   │   ├── llm_schema.py           # LLM 提供商配置模型与 API Key 脱敏工具
│   │   └── auth_schema.py          # 鉴权登录请求/响应模型
│   ├── repository/                 # 数据持久化仓储层
│   │   ├── database.py             # SQLite 连接池配置 (开启 WAL 模式) 与默认 Demo 初始化
│   │   ├── app_repo.py             # 微应用数据库 CRUD 与访问计数器原子累加
│   │   └── llm_repo.py             # 大模型配置 CRUD 与激活切换
│   ├── service/                    # 业务逻辑服务层
│   │   ├── app_service.py          # 微应用创建、静态文件持久化、版本快照与一键回滚
│   │   ├── zip_service.py          # ZIP 解包安全防御 (Zip Slip) 与智能扁平化算法
│   │   ├── llm_service.py          # System Prompt、OpenAI 兼容 SSE 流式请求与元信息生成
│   │   └── generator_service.py    # 智能体单页、n8n 看板与动态数据采集表单生成引擎
│   ├── api/                        # 控制器路由层
│   │   ├── deps.py                 # FastAPI 依赖注入 (verify_admin_token)
│   │   ├── auth.py                 # 登录鉴权路由 (/api/auth)
│   │   ├── apps.py                 # 微应用管理、源码读取、版本快照与回滚路由 (/api/apps)
│   │   ├── llm.py                  # 大模型管理与 AI 流式调用路由 (/api/llm, /api/ai)
│   │   ├── sites.py                # 静态微应用分发与重定向路由 (/s/{app_slug}/*)
│   │   └── generator.py            # 智能体、n8n 看板与表单应用生成路由 (/api/generator)
│   └── static_ui/                  # 前端静态单页应用
│       ├── index.html              # Vue 3 + TailwindCSS + Lucide + Marked + Highlight.js 单页
│       └── favicon.svg             # 平台矢量 Favicon
├── data/                           # 持久化数据目录 (Docker 容器内为 /app/data)
│   ├── studio.db                   # SQLite 数据库文件
│   ├── sites/                      # 各微应用静态文件存放目录 (/sites/{app_slug}/)
│   └── backups/                    # 各微应用版本历史快照归档目录 (/backups/{app_slug}/v{N}/)
├── Dockerfile                      # 生产级 Docker 镜像构建文件
├── docker-compose.yml              # Docker Compose 本地测试与编排配置
├── requirements.txt                # Python 依赖清单
├── .env.example                    # 环境变量模板
└── README.md                       # 说明文档
```

---

## 🛠️ 本地快速开发与调试

### 1. 准备环境
确保本地已安装 Python ≥ 3.10（推荐 3.11+）。

```bash
# 进入项目根目录
cd d:\DEV\LiteApp

# 创建并激活虚拟环境 (可选)
python -m venv venv
# Windows:
venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

### 2. 配置环境变量
复制环境配置模板：
```bash
cp .env.example .env
```
根据需要修改 `.env` 中的参数，如管理员密码：
```env
ADMIN_PASSWORD=admin888
DATA_DIR=./data
DEFAULT_OPENAI_BASE_URL=https://api.openai.com/v1
DEFAULT_OPENAI_API_KEY=sk-xxxx
DEFAULT_OPENAI_MODEL=gpt-4o
```

### 3. 启动服务
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

启动后在浏览器打开：
- 门户主页与工作台：`http://localhost:8000/`
- Swagger API 接口文档：`http://localhost:8000/api/docs`
- 预置示例应用直接访问：`http://localhost:8000/s/welcome-timer/`

---

## 🐳 Docker 容器化部署

### 方式 A：Docker 快速构建与运行

```bash
# 构建镜像
docker build -t liteapp-studio:latest .

# 启动容器并挂载持久化目录
docker run -d \
  --name liteapp-studio \
  -p 8000:8000 \
  -e ADMIN_PASSWORD=your_secure_password \
  -e DEFAULT_OPENAI_BASE_URL=https://api.deepseek.com/v1 \
  -e DEFAULT_OPENAI_API_KEY=sk-your-key \
  -e DEFAULT_OPENAI_MODEL=deepseek-chat \
  -v $(pwd)/data:/app/data \
  --restart unless-stopped \
  liteapp-studio:latest
```

### 方式 B：Docker Compose 一键启动

```bash
docker compose up -d
```

查看日志与健康状态：
```bash
docker compose logs -f
curl http://localhost:8000/api/health
```

---

## ☁️ 在自建 Coolify 平台上部署

LiteApp Studio 专为 Coolify 平台原生优化，部署步骤极为简单：

1. **进入 Coolify 控制台**：
   - 进入你的 Project -> Environment，点击 **+ New Resource** -> **Git Repository** 或 **Docker Compose**。
2. **连接代码仓库**：
   - 填写本项目 Git 仓库地址。
3. **选择构建方式**：
   - **方式一（推荐 Dockerfile 模式）**：
     - Build Pack 选择 **Dockerfile**。
     - Port 填写 `8000`。
   - **方式二（Docker Compose 模式）**：
     - Build Pack 选择 **Docker Compose**，直接识别项目内的 `docker-compose.yml`。
4. **配置持久化数据卷 (Persistent Storage)**：
   - 在 Coolify 对应应用的 **Storages** 面板中，添加持久化卷挂载：
     - **Destination Path**: `/app/data`
     - **Source Volume**: `liteapp-data` (或自定义主机卷)
   - *此步骤确保容器重新拉取更新镜像时，已发布的站点文件和 SQLite 数据库永不丢失！*
5. **配置环境变量 (Environment Variables)**：
   - `ADMIN_PASSWORD`: 你的高强度管理员密码
   - `DEFAULT_OPENAI_BASE_URL`: 大模型 API 地址
   - `DEFAULT_OPENAI_API_KEY`: 大模型 API 密钥
   - `DEFAULT_OPENAI_MODEL`: 默认模型标识
6. **配置域名与 HTTPS**：
   - 在 **Domains** 处绑定你的自定义域名（例如 `apps.yourdomain.com`），Coolify 会自动申请并配置 Let's Encrypt SSL 证书。
7. **点击 Deploy**：
   - 构建完成后，访问你的域名即可直接体验 LiteApp Studio！

---

## 🔐 安全防御深度说明

| 防御场景 | 对应防护机制 |
| :--- | :--- |
| **Zip Slip 目录穿越攻击** | 解包时严格解析每个条目路径，拒绝 `..` 相对路径和绝对路径，双重通过 `relative_to` 边界校验 |
| **Zip 炸弹防御** | 遍历条目尺寸并校验总解包体积，超过 `MAX_UPLOAD_SIZE_MB` (默认 50MB) 立即中断拒绝 |
| **静态应用路径穿越** | 静态路由解析中使用 `Path.resolve()` 并强制校验必须属于 `/app/data/sites/{slug}/` 目录树内 |
| **相对路径丢失导致 404** | 强制执行 `/s/{slug}` 到 `/s/{slug}/` 的 307 重定向，保障浏览器正确拼接相对资源路径 |
| **API 密钥泄漏** | 大模型 API Key 全程存储在后端 SQLite，所有 API 查询均自动脱敏返回（如 `sk-abc...1234`） |
| **接口防盗刷** | AI 流式生成、文件上传、应用覆盖与删除接口均通过 `verify_admin_token` 严格保护 |

---

## 📄 开源许可证

本项目基于 [MIT License](LICENSE) 开源发布。
