<div align="center">
  <img src="./assest/preview/logo.png" width="200" alt="DailyBot Logo">
  <h1>🐱 日报喵 (DailyBot)</h1>
  <p><b>工业级 · 全异步 · 插件化 · AI 驱动的日报自动化专家</b></p>
  <br />
  <a href="https://www.python.org/"><img src="https://img.shields.io/badge/python-3.9+-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python"></a>
  <img src="https://img.shields.io/badge/asyncio-httpx-brightgreen?style=flat-square&logo=asyncio&logoColor=white" alt="Asyncio">
  <a href="https://fastapi.tiangolo.com/"><img src="https://img.shields.io/badge/fastapi-v0.100+-009688?style=flat-square&logo=fastapi&logoColor=white" alt="FastAPI"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue?style=flat-square" alt="License"></a>
  <img src="https://img.shields.io/badge/AI-DeepSeek%20%7C%20Gemini%20%7C%20Doubao-red?style=flat-square" alt="AI">
</div>

---

## 🌟 项目背景与简介

### 1. 为什么会有“日报喵”？
在现代软件开发流程中，开发者往往需要跨多个平台（GitLab, Jira, Redmine）记录自己的工作足迹。每到下班时分，手动整理成百上千条提交记录并撰写出一份逻辑清晰、重点突出的日报，往往耗时耗力。

**日报喵 (DailyBot)** 应运而生。它不仅是一个脚本，更是一个**智能化的工作伙伴**。它能自动潜入您的代码库，提取当日成果，通过 AI 智脑进行语义润色，并以最专业的形式推送到您的办公平台（飞书、企业微信等）。

### 2. 核心价值
- **自动化采集**：告别手动翻阅 Git Commit。
- **智能总结**：AI 自动过滤碎片化代码信息，提炼出具有业务价值的成果陈述。
- **极致体验**：支持 RPA 自动化填报，实现从采集到填报的全流程闭环。

---

## 🔥 核心特色功能

### 1. ⚡ 全链路异步深度重构
- **极速性能**：全程采用 `httpx` + `asyncio`，从 API 调用到数据落盘全异步化。
- **高并发支持**：多仓库采集任务通过 `asyncio.gather` 并行执行，即便有数十个仓库也能在秒级完成。

### 2. 🛡️ 智能 OAuth 引导 (Nudge)
- **Token 闭环管理**：实时监测 Token 有效性。若检测到未授权，系统会自动向群聊发送 **“智能引导卡片”**。
- **零中断授权**：用户仅需点击卡片按钮，系统即时捕获凭据并自动恢复工作流，无需人工干预配置文件。

### 3. 🧩 极致解耦的“插件化”架构
- **解耦设计**：支持动态扫描并加载 `Crawlers`（采集器）、`RPA`（执行器）和 `Providers`（AI 供应商）。
- **声明式 API**：仿前端 Axios 的声明式设计，业务逻辑只需关心调用，认证注入与异常拦截全自动化处理。

### 4. 🤖 智脑请求共享机制
- **模型去重**：若多个推送平台配置了相同的 AI 模型（如都用豆包），系统会自动合并请求。在单次运行中，相同模型的 AI 请求仅触发一次，极大节省 Token 消耗并保持总结的一致性。

---

## 🏗️ Fix(有bug): 极致打包与分发 (EXE)

日报喵支持**单体 EXE 极致分发方案**：

### 1. 傻瓜式运行
- **免安装环境**：生成的 `DailyBot.exe` 可以在未部署 Python 的环境下直接运行。
- **自动初始化**：程序内置浏览器环境自检。如果开启了 RPA 填报但缺少驱动，**程序会在首次启动时自动通过后台下载安装 Chromium**，实现真正的“开箱即用”。

### 2. 如何打包？
如果您进行了二次开发，可以运行以下命令重新生成执行文件：
```bash
# 安装打包依赖
pip install pyinstaller

# 执行一键打包逻辑 (配置文件已整理至 scripts 目录)
pyinstaller scripts/DailyBot.spec --clean --noconfirm
```
成品将生成在 `dist/` 目录下，包含 `DailyBot.exe` 及必需的配置模板。

---

## 🏗️ 技术架构全景图

```mermaid
graph TD
    subgraph "1. 环境自检 (System Checker)"
        START[程序启动] --> ENV[Playwright 驱动检测]
        ENV -->|未就绪| INSTALL[自动补全 Chromium]
        ENV & INSTALL --> OAUTH_CHECK[OAuth 授权检测]
    end

    subgraph "2. 智能采集 (Crawlers)"
        OAUTH_CHECK -->|授权通过| C_FACTORY[Crawler Factory]
        C_FACTORY -->|异步并行| GL["GitLab (Async)"]
        C_FACTORY -->|Upcoming| GH["GitHub"]
        GL & GH --> RAW_DATA[原始 Commits 汇总]
    end

    subgraph "3. 智脑中心 (Providers)"
        RAW_DATA -->|去重合并请求| AI_FACTORY[AI Factory]
        AI_FACTORY -->|Doubao| DB[豆包 Pro]
        AI_FACTORY -->|DeepSeek| DS[DeepSeek V3]
        AI_FACTORY -->|Gemini| GM[Gemini 1.5]
        DB & DS & GM --> SUMMARY[AI 生成总结内容]
    end

    subgraph "4. 推送工作流 (Workflows)"
        SUMMARY --> WF_FACTORY[Workflow Factory]
        WF_FACTORY --> FS[飞书卡片推送]
        WF_FACTORY --> WC[企业微信推送]
    end

    subgraph "5. 自动化填报 (RPA Executor)"
        FS & WC --> RPA_FACTORY[RPA Factory]
        RPA_FACTORY -->|驱动| PW[Playwright Engine]
        PW --> SUBMIT[自动打开表单 & 模拟点击提交]
    end

    style START fill:#f9f,stroke:#333,stroke-width:2px
    style SUBMIT fill:#00ff00,stroke:#333
```

---

## 📂 项目结构解析

```text
DailyBot/
├── main.py              # 🚀 核心入口：控制全链路流转与浏览器自动环境初始化
├── push_scheduler.py    # ⏰ 守护进程：基于 Cron 规则的定时推送服务
├── config/              # ⚙️ 配置中心：config.yaml 静态配置存放
├── scripts/             # 🛠️ 运维脚本：PyInstaller 打包配置 (.spec) 与启动脚本
├── api/                 # 📡 接口定义：各平台声明式 API 映射
├── crawlers/            # 🔍 智能采集：各平台 Commits 爬虫实现
├── rpa/                 # 🖱️ 自动化执行：Playwright 驱动的表单自动填报逻辑
├── providers/           # 🤖 模型适配：各 AI 大模型的 Payload 与解析器
├── request/             # 🌐 通讯方案：底层 httpx 异步封装与平台拦截器
├── token_storage/       # 🗄️ 凭据存储：支持 Redis 或文件驱动
└── utils/               # 🔧 核心组件：动态模块发现器 (DynamicManager) 与路径助手
```

---

## 🚀 极简上手指南

### 环境准备

```powershell
# 克隆项目并进入
git clone https://github.com/your-repo/DailyBot.git
cd DailyBot

# 创建并激活虚拟环境 (Windows)
python -m venv .venv
.\.venv\Scripts\activate

# 安装全量依赖
pip install -r requirements.txt
```

---

## ⚙️ 配置指南

### 1. 在项目根目录创建.env环境配置文件

配置优先级：外部`.env`配置 > 外部`config.yaml` > 内部`.env`配置 > 内部`config.yaml`

```properties
# 飞书应用配置
FEISHU_APP_ID=飞书appid
FEISHU_APP_SECRET=飞书秘钥
FEISHU_OAUTH_REDIRECT_URI=http://127.0.0.1:8001/feishu/callback # 授权配置回调地址
FEISHU_BASE_URL=https://open.feishu.cn # 请求库配置
# 机器人推送配置
FEISHU_TARGET_CHAT_ID=推送机器人id
FEISHU_STANDUP_TIME=09:00
FEISHU_STANDUP_TIMEZONE=Asia/Shanghai

# 豆包大模型配置
DOUBAO_API_KEY=火山方舟API Key
DOUBAO_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
DOUBAO_MODEL=doubao-seed-1-8-251228

# 智普GLM
GLM_API_KEY=火山方舟API Key
GLM_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
GLM_MODEL=glm-4-7-251222

# DeepSeek
DEEPSEEK_API_KEY=火山方舟API Key
DEEPSEEK_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
DEEPSEEK_MODEL=deepseek-v3-2-251201

# Kimi K2
KIMI_API_KEY=火山方舟API Key
KIMI_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
KIMI_MODEL=kimi-k2-thinking-251104

# Gemini
GEMINI_API_KEY=Google AI Studio上面的API Key
GEMINI_BASE_URL=https://generativelanguage.googleapis.com/v1beta
GEMINI_MODEL=gemini-3-flash-preview

LOG_LEVEL=INFO

# GitLab 配置
GITLAB_TOKEN=gitlab访问token
GITLAB_TARGET_USER=你的gitlab仓库对应git的用户名

# redis配置
REDIS_HOST=127.0.0.1
REDIS_PORT=6379
```

### 2. 火山方舟 (豆包 AI) 获取流程

日报喵默认推荐使用豆包模型，其针对中文总结进行了深度优化，且新用户拥有丰厚的免费额度。

1. **注册与登录**：访问 [火山方舟控制台](https://console.volcengine.com/ark/region:ark+cn-beijing/endpoint)。

   ![image-20260227112429070](assest/preview/image-20260227112429070.png)

   两处地方任意一处即可进入

   ![image-20260227112506649](assest/preview/image-20260227112506649.png)

   ![image-20260227112551022](assest/preview/image-20260227112551022.png)

2. **开通服务**：搜索并点击“豆包”系列模型（如 `doubao-pro-32k`），点击“立即开通”。

   ![image-20260227112738395](assest/preview/image-20260227112738395.png)

3. **获取 API Key**：在左侧导航栏【API Key 管理】中点击“创建 API Key”，复制生成的密钥到`.env`里面的`DOUBAO_API_KEY`

   ![image-20260227112809695](assest/preview/image-20260227112809695.png)

4. **获取base_url和模型名称**：

   - 点击已经开通的模型名称进入【】页面，点击“创建”。

     ![image-20260227113800615](assest/preview/image-20260227113800615.png)

     ![image-20260227113855539](assest/preview/image-20260227113855539.png)

     将获取到的信息依次填写到对应的配置

     ![image-20260227113955479](assest/preview/image-20260227113955479.png)

   - > 新用户通常享有 **50 万免费 Token** 额度，建议优先开启“安心体验模式”以防意外扣费。

### 2. GitLab 配置流程
为了自动提取您的代码记录，需要配置 GitLab 访问凭据：

1. **生成 Token**：
   - 登录您的 GitLab，进入个人设置 -> **Access Tokens**。

     ![image-20260227114125080](assest/preview/image-20260227114125080.png)

   - 创建一个新的 Token，名称随意

   - **Scopes 建议全选** (至少包含 `read_api` 和 `read_repository`)。

     ![image-20260227114309706](assest/preview/image-20260227114309706.png)

   - 复制生成的 `Personal Access Token`。

     ![image-20260227114419766](assest/preview/image-20260227114419766.png)

2. **确认用户名**：`GITLAB_TARGET_USER` 填入您的 GitLab 登录用户名（用于精准过滤您的提交）。查看当前仓库使用的：

   ```bash
   git config user.name
   git config user.email
   ```

3. **启动项目**：

```bash
# 手动单次运行
python main.py

# 生产环境常驻运行 (基于 Cron 调度)
python push_scheduler.py
```

---

## 🐳 TODO(待完善): Docker 快速部署

如果您希望在 Linux 服务器上快速部署，或避免本地 Python 环境冲突，可以使用 Docker 方案。

1. **环境准备**：确保已安装 Docker 和 Docker-compose。
2. **配置环境变量**：参考上文配置好 `.env` 文件。
3. **一键启动**：
   ```bash
   # 进入项目根目录执行
   docker-compose -f docker/docker-compose.yml up -d
   ```
4. **管理指令**：
   ```bash
   # 查看实时日志
   docker-compose -f docker/docker-compose.yml logs -f dailybot
   
   # 停止并移除容器
   docker-compose -f docker/docker-compose.yml down
   ```
> Docker 镜像基于 Playwright 官方 Python 镜像构建，已内置所需的浏览器核心，无需额外安装驱动。

---

---

## 🛠️ 配置文件手册

日报喵支持高度灵活的配置，您可以根据需要通过外置的 `.env` 或 `config/config.yaml` 进行定义。

### 1. 配置优先级
**环境配置挂载 > 外部工作目录配置 > 打包目录内置配置**
即：外部 `.env` > 外部 `config.yaml` > 内部 `.env` > 内部 `config.yaml`。

### 2. 环境变量 (`.env`) 详解
这些变量支持直接覆盖 YAML 中的对应点位，适合在本地部署或容器化环境中使用。
| 变量名 | 类型 | 说明 |
| :--- | :--- | :--- |
| **全平台通用** | | |
| `LOG_LEVEL` | String | 日志输出级别 (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| **GitLab 数据采集** | | |
| `GITLAB_TOKEN` | String | GitLab 的 Personal Access Token (需 `read_api` 权限) |
| `GITLAB_TARGET_USER` | String | 目标作者用户名，用于过滤 Commit 记录 |
| `GITLAB_BASE_URL` | String | 自建 GitLab 的域名地址 |
| `GITLAB_REPOS` | String | (可选) 动态仓库，格式：`repo_path:branch,repo_path:branch` |
| **飞书推送平台** | | |
| `FEISHU_APP_ID` | String | 飞书应用的 App ID |
| `FEISHU_APP_SECRET` | String | 飞书应用的 App Secret |
| `FEISHU_TARGET_CHAT_ID` | String | 接收卡片的飞书群聊 ID |
| **企业微信推送平台** | | |
| `WECOM_CORP_ID` | String | 企业微信 CorpID |
| `WECOM_CORP_SECRET` | String | 企业微信应用 Secret |
| `WECOM_RPA_FORM_URL` | String | 企业微信日报填写页面的 URL |
| **AI 模型秘钥 (火山方舟等)** | | |
| `DOUBAO_API_KEY` | String | 豆包 Pro API 密钥 |
| `GLM_API_KEY` | String | 智谱 GLM-4 API 密钥 |
| `DEEPSEEK_API_KEY` | String | DeepSeek API 密钥 |
| `KIMI_API_KEY` | String | Kimi (Moonshot) API 密钥 |
| `GEMINI_API_KEY` | String | Google Gemini API 密钥 |
| **Redis 存储 (可选)** | | |
| `REDIS_HOST` | String | Redis 地址 |
| `REDIS_PORT` | Int | Redis 端口 (默认 6379) |
| `REDIS_PASSWORD` | String | Redis 密码 |

### 3. YAML 配置 (`config.yaml`) 详解

| 路径 | 类型 | 说明 | 默认/示例 |
| :--- | :--- | :--- | :--- |
| **全平台通用** | | | |
| `enabled_workflows` | List | 数组，定义哪些平台将执行推送 (如 `["feishu", "wecom"]`) | `[]` |
| **飞书 (feishu)** | | | |
| `platforms.feishu.ai_model` | String | 该推送平台使用的 AI 模型参考 key | `doubao` |
| `platforms.feishu.app_id` | String | 飞书应用的 App ID | `${FEISHU_APP_ID}` |
| `platforms.feishu.app_secret` | String | 飞书应用的 App Secret | `${FEISHU_APP_SECRET}` |
| `platforms.feishu.target_chat_id` | String | 接收日报卡片的群聊 ID | `oc_xxx` |
| `platforms.feishu.standup_time` | String | 每日推送的标准时刻 | `09:00` |
| `platforms.feishu.standup_timezone` | String | 时区设置 | `Asia/Shanghai` |
| `platforms.feishu.base_url` | String | 飞书开放平台地址 | `https://open.feishu.cn` |
| **企业微信 (wecom)** | | | |
| `platforms.wecom.ai_model` | String | 绑定的 AI 模型 key | `doubao` |
| `platforms.wecom.rpa.enabled` | Bool | 是否启用 Playwright 自动填报 | `true` |
| `platforms.wecom.rpa.speed` | Float | 模拟真人操作速度 (0.1 最快, 1 最慢) | `1` |
| `platforms.wecom.rpa.max_retry` | Int | 页面刷新重试次数 | `1` |
| `platforms.wecom.rpa.auto_submit` | Bool | 是否直接点击“提交”按钮 | `false` |
| `platforms.wecom.rpa.browser_type` | String | 内核选择: `chrome` 或 `msedge` | `chrome` |
| `platforms.wecom.rpa.form_url` | String | 企业微信日报汇总表单的 URL | `https://doc.weixin.qq.com/...` |
| `platforms.wecom.rpa.browser_executable_path` | String | 浏览器二进制文件的绝对路径 (留空则自动搜索) | `C:\Program Files\...` |
| **AI 模型 (models)** | | | |
| `models.xxx.name` | String | 模型的友好显示名称 | `豆包大模型` |
| `models.xxx.base_url` | String | 模型 API 的基础 URL | `https://ark...` |
| `models.xxx.model` | String | 模型名称或接入点 ID (Endpoint ID) | `ep-xxx` |
| `models.xxx.params.temperature` | Float | 生成多样性控制参数 | `0.7` |
| `models.xxx.params.timeout` | Int | 请求超时秒数 | `60` |
| **仓库源 (repos)** | | | |
| `repos.gitlab.base_url` | String | GitLab 服务器地址 | `http://git.xxx.com` |
| `repos.gitlab.target_user` | String | 核心开发者用户名 (自动过滤记录) | `liangan` |
| `repos.gitlab.repos[].path` | String | 仓库路径 (Group/Repo) | `frontend/admin` |
| `repos.gitlab.repos[].branch` | String | 监听的分支 (支持逗号分隔多个) | `master, dev` |
| `repos.gitlab.repos[].name` | String | 日报头部展示的项目名 | `管理后台` |
| `repos.gitlab.repos[].crawl_dates` | List | (可选) 指定爬取的历史日期 | `["2024-01-01"]` |
| **调度与日志 (scheduler/log)** | | | |
| `scheduler.enabled` | Bool | 是否开启本地定时任务定时器 | `true` |
| `scheduler.auto_start` | Bool | Windows 开机是否静默启动 | `true` |
| `scheduler.default_time` | String | 兜底执行时刻 | `18:20` |
| `scheduler.tasks` | List | 详细任务数组 (可定义 time, weekdays, dates) | `见示例` |
| `log.level` | String | 控制台输出等级 (`DEBUG`/`INFO`/`ERROR`) | `INFO` |
| `log.file_level` | String | 文件存储等级 (推荐 `DEBUG`) | `DEBUG` |
| `log.rotation` | String | 日志切割逻辑 (如 `00:00` 表示每天) | `00:00` |
| `log.retention` | String | 日志保留时长 | `7 days` |
| `log.path` | String | 日志文件存放模板 | `logs/dailybot_{time}.log` |
| **Redis (redis)** | | | |
| `redis.host` | String | Redis 存储地址 | `127.0.0.1` |
| `redis.port` | Int | 端口 | `6379` |
| `redis.password` | String | 认证密码 | `""` |
| `redis.database` | Int | 数据库 ID | `0` |

---

## 完整的 `config.yaml` 示例

您可以参考以下模版在 `config/config.yaml` 中进行业务配置。**敏感信息建议通过 `.env` 注入，而不是直接写在这里。**

```yaml
# ==========================================
# 🐱 日报喵 (DailyBot) 完整配置示例
# ==========================================

# --- 1. 业务推送平台配置 ---
platforms:
  feishu:
    ai_model: "doubao"                 # 绑定的模型 key (对应 models 下的名称)
    app_id: "${FEISHU_APP_ID}"        # 飞书应用 ID
    app_secret: "${FEISHU_APP_SECRET}" # 飞书应用密钥
    target_chat_id: "oc_xxx"          # 接收日报卡片的群聊 ID
    oauth_redirect_uri: "http://127.0.0.1:8001/feishu/callback"
    standup_time: "09:00"

  wecom:
    ai_model: "doubao"
    rpa:                               # 企业微信增强: 浏览器自动填报配置
      enabled: true                   # 是否启动 RPA
      speed: 1.0                      # 行为速度倍率 (0.1-1.0)
      max_retry: 1                    # 加载失败重试次数
      auto_submit: false              # 是否自动点击“提交提交”
      browser_type: "chrome"          # "chrome" 或 "msedge"
      form_url: "https://doc.weixin.qq.com/..." # 日报采集表单链接
      browser_executable_path: "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"

# --- 2. AI 模型供应商配置 ---
models:
  doubao:
    name: "豆包大模型"
    api_key: "${DOUBAO_API_KEY}"
    base_url: "https://ark.cn-beijing.volces.com/api/v3"
    model: "ep-xxx-xxx"               # 接入点 Endpoint ID
    params: { timeout: 60 }

  glm:
    name: "智谱 GLM"
    api_key: "${GLM_API_KEY}"
    base_url: "https://ark.cn-beijing.volces.com/api/v3"
    model: "glm-4-xxx"
    params: { timeout: 60 }

  deepseek:
    name: "DeepSeek V3"
    api_key: "${DEEPSEEK_API_KEY}"
    base_url: "https://ark.cn-beijing.volces.com/api/v3"
    model: "deepseek-v3-xxx"

  gemini:
    name: "Gemini 1.5 Flash"
    api_key: "${GEMINI_API_KEY}"
    base_url: "https://generativelanguage.googleapis.com/v1beta"
    model: "gemini-1.5-flash"

# --- 3. 代码仓库数据源 ---
repos:
  gitlab:
    token: "${GITLAB_TOKEN}"          # 你的 Personal Access Token
    base_url: "http://git.xxx.com"    # 公司 GitLab 地址
    target_user: "your_username"      # 用于过滤你的提交记录
    repos:                            # 仓库扫描配置
      - path: "dev/project-a"
        branch: "master"
        name: "后端核心"
      - path: "dev/project-b"
        branch: "test, develop"
        name: "前端小程序"

# --- 4. 全局开关与系统任务调度 ---
enabled_workflows: ["feishu", "wecom"] # 启用哪些工作流

scheduler:
  enabled: true                        # 启用 APScheduler 定时任务
  auto_start: true                    # Windows 开机自启动 (静默 VBS 模式)
  default_time: "18:20"                # 兜底执行时间
  tasks:
    - time: "18:30"                   # 特定时间
      weekdays: [1, 2, 3, 4, 5]        # 运行星期 (1-7)
    - dates: ["2026-02-28"]             # 特定日期
      time: "10:00"

log:
  level: "INFO"                        # 控制台输出级别
  file_level: "DEBUG"                  # 写入文件级别 (详细)
  rotation: "00:00"                    # 每天零点滚动日志
  retention: "7 days"                  # 保留最近 7 天的日志

redis:                                 # 可选：配置后用于存储 OAuth Token (避免频繁文件读写)
  host: "127.0.0.1"
  port: 6379
  password: ""
  database: 0
```



