# DailyBot 配置参考

## config.yaml 完整配置项

### platforms - 推送平台配置

| 配置项 | 说明 | 示例值 |
|--------|------|--------|
| platforms.feishu.app_id | 飞书应用 ID | cli_xxx |
| platforms.feishu.app_secret | 飞书应用密钥 | xxx |
| platforms.feishu.bot_token | 飞书机器人 Token | xxx |
| platforms.feishu.target_chat_id | 目标群聊 ID | oc_xxx |
| platforms.feishu.tasklist_guid | 飞书任务清单 GUID | xxx |
| platforms.feishu.oauth_redirect_uri | OAuth 回调地址 | http://127.0.0.1:8001/feishu/callback |
| platforms.wecom.corp_id | 企业 ID | wwxxx |
| platforms.wecom.corp_secret | 企业应用密钥 | xxx |

### platforms.wecom.rpa - 企业微信 RPA 配置

| 配置项 | 说明 | 示例值 |
|--------|------|--------|
| rpa.enabled | 是否启用 RPA | true/false |
| rpa.speed | 自动化速度 (0.1-1) | 1 |
| rpa.max_retry | 最大重试次数 | 1 |
| rpa.auto_submit | 是否自动提交 | true/false |
| rpa.auto_cleanup | 是否自动清理缺陷行 | true/false |
| rpa.browser_type | 浏览器类型 | chrome/msedge |
| rpa.form_url | 企业微信日报 URL | https://work.weixin.qq.com/... |
| rpa.browser_user_data_dir | 浏览器用户数据目录 | .browser_profiles/chrome |
| rpa.browser_executable_path | 浏览器可执行文件路径 | C:\\Program Files\\... |

### models - AI 模型配置

支持的模型类型：doubao, glm, deepseek, kimi, gemini

```yaml
models:
  模型名:
    name: 显示名称
    api_key: API 密钥
    base_url: API 地址
    models: []
    params:
      timeout: 60  # 超时时间(秒)
```

### crawler_sources - 数据源配置

```yaml
crawler_sources:
  gitlab:
    token: GitLab 私有 Token
    base_url: http://git.b2bwings.com
    target_user: 目标用户
    repos:
      - path: 仓库路径
        branch: 分支名
        name: 显示名称
        crawl_dates:  # 可选，指定日期
          - 2026-01-01
          - 2026-01-04, 2026-01-05
    camouflage:  # 伪装配置
      enabled: true
      threshold: 4
      max_items: 5
      lookback_days: 14
      cooldown_days: 10
```

### enabled_workflows - 启用的工作流

```yaml
enabled_workflows: [feishu]  # 或 [feishu, wecom]
```

### scheduler - 调度器配置

```yaml
scheduler:
  enabled: true
  auto_start: true  # 开机自启
  default_time: 18:20  # 默认执行时间
  tasks:
    - time: 18:20
      weekdays: [1, 2, 3, 4, 5]  # 周一到周五
```

### redis - Token 存储配置

```yaml
redis:
  host: 127.0.0.1
  port: 6379
  password:
  database: 0
```

## 环境变量

| 变量名 | 说明 |
|--------|------|
| DAILYBOT_CONFIG_PATH | 配置文件路径 (默认 config/config.yaml) |

## 日志

- 日志路径: logs/dailybot_YYYY-MM-DD.log
- 日志级别: config.yaml 中 log.level 配置

## MCP 工具

| 工具名 | 功能 |
|--------|------|
| run_daily_report | 触发完整日报流程 |
| get_enabled_workflows | 获取已启用的工作流 |
| get_system_config | 获取系统配置摘要 |

## 目录结构

```
DailyBot/
├── config/
│   └── config.yaml        # 主配置文件
├── logs/                   # 日志目录
├── .browser_profiles/      # 浏览器配置目录
├── crawlers/               # 数据采集模块
├── workflows/              # 工作流模块
├── rpa/                    # RPA 模块
├── providers/              # AI 模型提供方
├── api/                    # 第三方 API 封装
├── oauth/                  # OAuth 授权
├── main.py                 # 主入口
└── scripts/
    ├── DailyBot.bat       # Windows 后台运行脚本
    └── build.bat           # 打包脚本
```
