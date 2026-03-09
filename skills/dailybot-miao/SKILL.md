---
name: dailybot-miao
description: |
  DailyBotMiao 自动化日报系统。管理 GitLab commit 采集、AI 总结、飞书/企微推送及 RPA 自动填报。用于运行日报流水线、检查工作流状态、排查浏览器驱动或 OAuth 授权异常。
---

# DailyBotMiao 自动化日报系统

## 快速开始

### 运行日报流水线（优先方式）

使用 MCP 工具一键触发完整流程：

```
run_daily_report()  # 采集 → 总结 → 推送 → RPA 填报
get_enabled_workflows()  # 查看已启用的平台
get_system_config()  # 查看系统配置摘要
```

### 手动运行

如果 MCP 不可用：

```bash
cd D:\backup\DailyBot
python main.py
```

## 核心工作流

DailyBot 执行顺序：

1. **环境自检** - 检查 RPA 浏览器驱动是否安装
2. **OAuth 授权** - 等待飞书/企微授权 Token（60秒超时）
3. **数据采集** - 从 GitLab 抓取指定仓库的 Commit
4. **AI 总结** - 调用配置的 AI 模型生成日报
5. **消息推送** - 发送到已启用的平台
6. **RPA 填报** -（可选）自动填写企业微信日报表单

## 故障排除

### 浏览器驱动缺失

RPA 运行时需要 Chromium：

```bash
playwright install chromium
```

程序启动时会自动检测并尝试安装。

### OAuth 授权失效（飞书）

1. 程序会发送授权卡片到飞书
2. 用户在消息中点击授权按钮
3. 程序自动获取 Token 并继续执行

### 企业微信 RPA 失败

- 检查 config.yaml 中 platforms.wecom.rpa.form_url 是否正确
- 将 auto_submit 设为 false 便于人工核对
- 确认浏览器配置（browser_type, browser_user_data_dir）

### Scheduler 调度器

- 检查 logs/.scheduler.lock 确认服务运行状态
- 重启：scripts\DailyBot.bat
- 配置项见 reference.md

## 打包与部署

```bash
# 打包 EXE
scripts\build.bat
# 清理打包缓存
scripts\build.bat --clean
```

## 配置参考

详细配置项说明见 reference.md
