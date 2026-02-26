import json
import asyncio
import common.logger  # noqa: F401 (触发全局日志配置)
from loguru import logger as log
from datetime import datetime
import uvicorn
from api import apis
from common import config
from request.hooks import use_request
from token_storage import load_all_tokens
from oauth import oauth_platform_manager
from crawlers import CrawlerFactory
from workflows import WorkflowFactory
from rpa.modules.rpa_factory import RPAFactory
from exceptions import handle_logic_exception
from request.core.http_request import HttpRequest


async def collect_all_reports():
    """采集所有支持平台的提交数据，并汇总文本 (异步并行化)"""
    log.info("📋 正在采集所有平台的提交记录...")

    report_text = ""
    configured_platforms = config.get_repo_platforms()
    crawl_tasks = []

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
        crawl_tasks.append(crawler.crawl(target_user=target_user))

    if not crawl_tasks:
        return ""

    # 并发执行所有平台的采集
    results = await asyncio.gather(*crawl_tasks)

    for i, commits_map in enumerate(results):
        if not commits_map:
            continue

        platform = configured_platforms[i]
        platform_report = f"\n  平台: {platform.upper()}\n"
        for repo_name, date_groups in commits_map.items():
            platform_report += f"    仓库: {repo_name}\n"
            for date_str in sorted(date_groups.keys(), reverse=True):
                platform_report += f"      📅 日期: {date_str}\n"
                for msg in date_groups[date_str]:
                    platform_report += f"        - {msg}\n"

        report_text += platform_report

    return report_text


async def trigger_rpa(platform_name: str, summary_json: str):
    """
    根据配置动态触发 RPA 流程
    """
    try:
        # 1. 检查配置是否启用
        platform_config = config.get_platform(platform_name)
        rpa_enabled = platform_config.get("rpa", {}).get("enabled", False)

        if not rpa_enabled:
            return

        log.info(f"🚀 [RPA] 检测到 {platform_name} 已启用自动化填报，正在准备执行...")

        # 2. 解析 AI 生成的结构化数据
        try:
            report_data = json.loads(summary_json)
        except Exception as e:
            log.error(f"❌ [RPA] AI 返回数据非合法 JSON，跳过 RPA 流程: {e}")
            return

        # 3. 获取 RPA 实例
        rpa_instance = RPAFactory.get_rpa(platform_name, config._yaml_config)
        if not rpa_instance:
            log.warning(f"⚠️ [RPA] 未发现 {platform_name} 的 RPA 驱动实现，已跳过。")
            return

        # 4. 执行 RPA 逻辑 (异步执行，不阻塞主流程日志)
        # 注意：此处直接 await，因为 process_summary 已经在 gather 中异步运行
        await rpa_instance.run(report_data)

    except Exception as e:
        log.error(f"❌ [RPA] {platform_name} 自动化执行发生异常: {e}")


async def run_reporting_logic():
    """全异步工作流：采集 -> AI 总结 -> 推送"""
    log.info("🎬 开始执行报告生成流程...")

    enabled_workflow_names = getattr(config, "ENABLED_WORKFLOWS")
    active_workflows = []

    # 初始化工作流
    for wf_name in enabled_workflow_names:
        wf = WorkflowFactory.get_workflow(wf_name)
        if wf and await wf.prepare():
            active_workflows.append(wf)

    if not active_workflows:
        log.warning("⚠️ 没有可用的工作流，中止任务。")
        return

    # 1. 异步数据采集
    raw_report = await collect_all_reports()
    if not raw_report:
        log.warning("📭 今日没有任何可汇报的数据。")
        for wf in active_workflows:
            try:
                await wf.on_report_success("[]", {"raw_report": ""})
            except Exception as e:
                log.error(f"发送暂无记录通知失败: {e}")
        return

    log.info("🐠 采集到以下原始报文内容：")
    print("-" * 50)
    print(raw_report)
    print("-" * 50)

    # 2. 并行起始反馈
    wf_contexts = []
    start_tasks = [wf.on_report_start(raw_report) for wf in active_workflows]
    contexts = await asyncio.gather(*start_tasks)
    for i, ctx in enumerate(contexts):
        wf_contexts.append((active_workflows[i], ctx))

    # 3. 并行 AI 总结与成功回调
    async def process_summary(wf, ctx):
        try:
            platform_config = config.get_platform(wf.WORKFLOW_NAME)
            rpa_enabled = platform_config.get("rpa", {}).get("enabled", False)
            if rpa_enabled:
                log.info(
                    f"⚡ [RPA] {wf.WORKFLOW_NAME} RPA 已开启，待 AI 总结后即刻启动..."
                )

            summary = await wf.summarize(raw_report)
            await wf.on_report_success(summary, ctx)

            # 4. 尝试触发 RPA 自动化 (如果已启用)
            await trigger_rpa(wf.WORKFLOW_NAME, summary)

        except Exception as e:
            log.error(f"工作流 {wf} 处理失败: {e}")

    await asyncio.gather(*(process_summary(wf, ctx) for wf, ctx in wf_contexts))


@handle_logic_exception
async def main():
    # 1. 启动 WebServer (OAuth 授权需要)
    config_server = uvicorn.Config(
        oauth_platform_manager.app, host="0.0.0.0", port=8001, log_level="error"
    )
    server = uvicorn.Server(config_server)
    server_task = asyncio.create_task(server.serve())

    # 2. 授权等待逻辑
    timeout_seconds = 60
    start_wait = datetime.now()

    log.info("⏳ 检查环境就绪状态...")
    enabled_workflow_names = getattr(config, "ENABLED_WORKFLOWS")

    try:
        while True:
            tokens_map = await load_all_tokens()
            if any(v for v in tokens_map.values()):
                log.info("✨ 授权检测通过。")
                break

            if (datetime.now() - start_wait).total_seconds() > timeout_seconds:
                log.warning("⏱️ 授权轮询超时。")
                break

            # 触发工作流准备
            for wf_name in enabled_workflow_names:
                wf = WorkflowFactory.get_workflow(wf_name)
                if wf:
                    await wf.prepare()

            await asyncio.sleep(5)

        # 3. 执行核心逻辑
        await run_reporting_logic()
    finally:
        # 清理资源
        log.info("🧹 程序运行结束，清理资源...")
        try:
            await HttpRequest.close_all()
            server.should_exit = True
            # 给 ProactorEventLoop 留出一点缓冲时间来清理管道
            await asyncio.sleep(0.5)
            await server_task
        except:
            pass


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
    except Exception as e:
        log.exception(f"Fatal error: {e}")
