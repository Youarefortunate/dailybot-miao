import json
import common.logger  # noqa: F401 (触发全局日志配置)
from loguru import logger as log
import threading
import time
from datetime import datetime
import uvicorn
from api import apis
from common import config
from request.hooks import use_request
from common import load_all_tokens
from oauth import oauth_platform_manager
from crawlers import CrawlerFactory
from workflows import WorkflowFactory
from exceptions import handle_logic_exception


def collect_all_reports():
    """采集所有支持平台的提交数据，并汇总文本"""
    log.info("📋 正在采集所有平台的提交记录...")

    report_text = ""
    configured_platforms = config.get_repo_platforms()

    for platform in configured_platforms:
        crawler = CrawlerFactory.get_crawler(platform)
        if not crawler:
            log.warning(
                f"⚠️ 仓库配置中定义了 {platform}，但系统中未找到对应的爬虫实现，已跳过。"
            )
            continue

        log.info(f"🔍 正在执行 {platform} 平台的采集任务...")
        platform_upper = platform.upper()
        target_user = getattr(config, f"{platform_upper}_TARGET_USER", None)

        commits_map = crawler.crawl(target_user=target_user)
        if not commits_map:
            continue

        # 生成提交部分文本
        platform_report = f"\n  平台: {crawler.get_platform_name()}\n"
        for repo_name, date_groups in commits_map.items():
            platform_report += f"    仓库: {repo_name}\n"
            for date_str in sorted(date_groups.keys(), reverse=True):
                platform_report += f"      📅 日期: {date_str}\n"
                for msg in date_groups[date_str]:
                    platform_report += f"        - {msg}\n"

        report_text += platform_report

    return report_text


@handle_logic_exception
def run_reporting_logic():
    """多平台并行工作流逻辑：采集 → 平台反馈开始 → AI 总结 → 平台更新结果"""
    log.info("🎬 开始执行报告生成流程...")

    # 0. 加载启用的工作流，默认启动feishu
    enabled_workflow_names = getattr(config, "ENABLED_WORKFLOWS", ["feishu"])
    active_workflows = []
    for wf_name in enabled_workflow_names:
        wf = WorkflowFactory.get_workflow(wf_name)
        if wf and wf.prepare():
            active_workflows.append(wf)

    if not active_workflows:
        log.warning("⚠️ 没有可用的工作流，中止任务。")
        return

    # 1. 数据采集
    raw_report = collect_all_reports()
    if not raw_report:
        log.warning("📭 今日没有任何可汇报的数据。")
        # 即使没有数据，也尝试通知各平台以便展示“暂无记录”
        for wf in active_workflows:
            try:
                # 传入空内容，触发工作流的暂无记录展示逻辑
                wf.on_report_success("[]", {"raw_report": ""})
            except Exception as e:
                log.error(f"发送暂无记录通知失败: {e}")
        return

    log.info("🍟 采集到以下原始报文内容：")
    print("-" * 50)
    print(raw_report)
    print("-" * 50)
    log.info(f"📊 采集完成，准备请求 AI 总结...")

    # 2. 各平台起始反馈 (如发送占位卡片)
    wf_contexts = []
    for wf in active_workflows:
        ctx = wf.on_report_start(raw_report)
        wf_contexts.append((wf, ctx))

    # 3. 各平台独立进行 AI 总结与分发最终结果
    for wf, ctx in wf_contexts:
        summary = wf.summarize(raw_report)
        wf.on_report_success(summary, ctx)


def main():
    # 1. 启动 WebServer (OAuth 授权需要)
    server_thread = threading.Thread(
        target=lambda: uvicorn.run(
            oauth_platform_manager.app, host="0.0.0.0", port=8001
        ),
        daemon=True,
    )
    server_thread.start()

    # 2. 授权等待逻辑 (简化并通用化)
    timeout_seconds = 60
    start_wait = time.time()

    # 提前准备工作流（由于 Feishu 需要引导，这里会触发引导）
    enabled_workflow_names = getattr(config, "ENABLED_WORKFLOWS", ["feishu"])

    log.info("⏳ 检查环境就绪状态...")
    while True:
        # 如果检测到任意授权成功，则尝试开始
        if load_all_tokens():
            log.info("✨ 授权检测通过。")
            break

        if time.time() - start_wait > timeout_seconds:
            log.warning("⏱️ 授权轮询超时。")
            # 如果是 feishu 以外的平台可能不需要 token，这里我们根据实际情况决定是否继续
            break

        # 触发工作流准备（针对飞书会发送引导卡片，由于有单例检测，多次调用不会重复发送）
        for wf_name in enabled_workflow_names:
            wf = WorkflowFactory.get_workflow(wf_name)
            if wf:
                wf.prepare()

        time.sleep(10)

    # 3. 执行核心逻辑
    try:
        run_reporting_logic()
    except Exception as e:
        log.error(f"❌ 程序执行异常: {e}")


if __name__ == "__main__":
    main()
