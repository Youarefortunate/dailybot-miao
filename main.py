import json
import logger  # noqa: F401 (触发全局日志配置)
from loguru import logger as log
import threading
import time
from datetime import datetime
import uvicorn
from api import apis
from config import config
from request.hooks import use_request
from token_store import load_all_tokens
from feishu_oauth_fastapi import app, send_auth_nudge, get_tenant_token
from services.ai_service import summarize_with_doubao
from crawlers import CrawlerFactory


def collect_all_reports():
    """采集所有支持平台的提交数据，并汇总文本"""
    log.info("📋 正在采集所有平台的提交记录...")

    report_text = ""
    # 从配置文件中动态获取已配置的仓库平台（如 gitlab, gitee）
    configured_platforms = config.get_repo_platforms()

    for platform in configured_platforms:
        # 通过工厂获取爬虫实例（工厂会根据 impl 目录动态发现）
        crawler = CrawlerFactory.get_crawler(platform)
        if not crawler:
            log.warning(
                f"⚠️ 配置文件中定义了 {platform}，但系统中未找到对应的爬虫实现，已跳过。"
            )
            continue

        log.info(f"🔍 正在执行 {platform} 平台的采集任务...")

        # 针对每个平台获取其特定的 target_user 配置（如果存在）
        # 规律：平台名大写 + _TARGET_USER
        platform_upper = platform.upper()
        target_user = getattr(config, f"{platform_upper}_TARGET_USER", None)

        commits_map = crawler.crawl(target_user=target_user)

        if not commits_map:
            log.info(f"📭 {platform} 平台本次无符合条件的提交记录。")
            continue

        # 生成提交部分文本
        platform_report = f"\n  平台: {crawler.get_platform_name()}\n"
        for repo_name, date_groups in commits_map.items():
            platform_report += f"    仓库: {repo_name}\n"
            # 排序日期，最近的靠前展示
            for date_str in sorted(date_groups.keys(), reverse=True):
                platform_report += f"      📅 日期: {date_str}\n"
                for msg in date_groups[date_str]:
                    platform_report += f"        - {msg}\n"

        report_text += platform_report

    if not report_text:
        log.info("📭 今日没有发现任何平台的有效提交记录。")
        return ""

    log.info(f"✅ 所有平台提交记录采集完成。")
    return report_text


def run_reporting_logic():
    """核心日报生成与推送逻辑：采集 → AI 总结 → 推送"""
    log.info("🎬 开始执行日报生成流程...")

    # ===== 第一阶段：数据采集 =====
    raw_report = collect_all_reports()

    if not raw_report:
        log.warning("📭 今日没有任何可汇报的数据。")
        return
    log.info(f"📊 准备请求 AI 总结的原始报告内容:\n{'-'*30}\n{raw_report}\n{'-'*30}")

    if not config.FEISHU_TARGET_CHAT_ID:
        log.warning("未配置 FEISHU_TARGET_CHAT_ID，总结流程中止。")
        return

    tenant_token = get_tenant_token()
    headers = {"Authorization": f"Bearer {tenant_token}"}

    # 1. 发送“正在总结”占位卡片
    placeholder_card = {
        "header": {
            "title": {"tag": "plain_text", "content": "🤖 正在生成总结..."},
            "template": "blue",
        },
        "elements": [
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": "☕ 正在为您优化汇报内容，请稍候...",
                },
            }
        ],
    }

    send_req = use_request(apis.feishu_app_im.send_message)
    res = send_req.fetch(
        {
            "receive_id": config.FEISHU_TARGET_CHAT_ID,
            "content": json.dumps(placeholder_card),
            "msg_type": "interactive",
            "headers": headers,
        }
    )

    message_id = res.get("data", {}).get("message_id")
    if not message_id:
        log.warning("无法获取占位卡片 message_id，将直接进行总结。")

    log.info("🤖 正在请求 AI 总结...")
    try:
        summary = summarize_with_doubao(raw_report)
    except Exception as e:
        error_msg = str(e)
        log.error(f"AI 总结出错: {error_msg}")
        summary = (
            f"⚠️ **AI 总结服务异常，已展示原始数据**\n"
            f"> 错误原因: `{error_msg}`\n\n"
            f"{raw_report}"
        )

    # ===== 第三阶段：更新消息内容 =====
    card = {
        "header": {
            "title": {"tag": "plain_text", "content": "📊 每日工作总结"},
            "template": "blue",
        },
        "elements": [{"tag": "div", "text": {"tag": "lark_md", "content": summary}}],
    }

    if message_id:
        update_req = use_request(apis.feishu_app_im.update_message)
        update_req.fetch(
            {
                "message_id": message_id,
                "content": json.dumps(card),
                "headers": headers,
            }
        )
        log.info(f"✅ 日报已原位更新 (ID: {message_id})")
    else:
        # 如果获取不到 message_id，退回到普通发送
        send_req.fetch(
            {
                "receive_id": config.FEISHU_TARGET_CHAT_ID,
                "content": json.dumps(card),
                "msg_type": "interactive",
                "headers": headers,
            }
        )
        log.info("✅ 日报已发送 (旧模式)")


def main():
    # 1. 启动内嵌 WebServer (子线程)
    server_thread = threading.Thread(
        target=lambda: uvicorn.run(app, host="0.0.0.0", port=8001), daemon=True
    )
    server_thread.start()

    # 2. 授权检测循环
    start_time = time.time()
    nudge_sent = False
    timeout_seconds = 60  # 1 分钟超时

    while True:
        tokens = load_all_tokens()
        if tokens:
            log.info(f"✨ 发现 {len(tokens)} 个有效授权，准备开始工作...")
            break

        # 检查超时
        elapsed = time.time() - start_time
        if elapsed > timeout_seconds:
            log.warning(f"⏱️ 授权超时 ({timeout_seconds}s)，程序自动退出。请稍后重试。")
            return

        if not nudge_sent:
            log.info("🔍 未发现有效授权，正在发送引导卡片...")
            success, reason = send_auth_nudge()
            if not success:
                return
            nudge_sent = True
            log.info(f"⏳ 等待用户授权中 (最长等待 {timeout_seconds}s)...")

        # 每 10 秒重检一次
        time.sleep(10)

    # 3. 执行日报生成与推送
    try:
        run_reporting_logic()
    except Exception as e:
        log.error(f"❌ 日报生成出错: {e}")


if __name__ == "__main__":
    main()
