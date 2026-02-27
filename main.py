import json
import asyncio
import subprocess
import sys
import os
import traceback
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


async def ensure_playwright_browsers():
    """
    检查并自动安装 Playwright 浏览器驱动 (Chromium)
    实现傻瓜式运行：如果检测到 RPA 开启但环境不就绪，自动下载驱动。
    """
    # 1. 快速检查：是否有任一平台启用了 RPA
    any_rpa_enabled = False
    for p_name in config.get_repo_platforms():
        if config.get_platform(p_name).get("rpa", {}).get("enabled", False):
            any_rpa_enabled = True
            break

    if not any_rpa_enabled:
        return

    log.info("🧪 [系统] 正在准备自动化运行环境...")

    # 2. 调用 playwright 内置驱动进行安装
    # 在打包环境下，不能使用 sys.executable -m playwright
    # 必须直接找到 playwright 的驱动二进制文件
    try:
        from playwright._impl._driver import compute_driver_executable

        driver_exe = compute_driver_executable()
        if not os.path.exists(driver_exe):
            log.warning(f"⚠️ [系统] 未找到内置驱动路径: {driver_exe}")
            return

        cmd = [str(driver_exe), "install", "chromium"]
        process = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        log.info("⏳ [系统] 正在进行环境自检与驱动补全，请稍候...")
        stdout, stderr = await process.communicate()

        if process.returncode == 0:
            log.info("✅ [系统] 浏览器环境已就绪。")
        else:
            err_msg = stderr.decode()
            log.warning(
                f"⚠️ [系统] 环境初始化未完全成功 (Code: {process.returncode}): {err_msg}"
            )

    except Exception as e:
        log.error(f"❌ [系统] 尝试自动辅助安装浏览器驱动时出错: {e}")


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

    # 3. 准备模型请求任务 (去重：同模型只请求一次)
    model_tasks = {}

    async def get_model_summary(m_name: str):
        """确保同模型只发起一次请求，并共享结果"""
        if m_name in model_tasks:
            return await model_tasks[m_name]

        async def _do_request():
            log.info(f"🤖 [AI] 正在为模型供应商 {m_name} 生成统一总结内容...")
            # 寻找第一个使用该模型的工作流来执行具体的 AI 业务逻辑
            sample_wf = next(
                wf
                for wf in active_workflows
                if config.get_platform(wf.WORKFLOW_NAME).get("ai_model") == m_name
            )
            return await sample_wf.summarize(raw_report)

        task = asyncio.create_task(_do_request())
        model_tasks[m_name] = task
        return await task

    # 4. 并行派发结果并执行 RPA 自动化 (非阻塞模式：谁先好谁先走)
    async def finalize_workflow_async(wf, ctx):
        try:
            m_name = config.get_platform(wf.WORKFLOW_NAME).get("ai_model")
            if not m_name:
                log.error(f"❌ [工作流: {wf.WORKFLOW_NAME}] 配置错误：未定义 ai_model")
                return

            # 等待所属模型的总结结果 (如果其他工作流已经启动了该模型的请求，此处会共享等待)
            summary = await get_model_summary(m_name)
            if not summary:
                log.error(f"❌ 工作流 {wf.WORKFLOW_NAME} 未能获取到总结结果")
                return

            # [非阻塞流转日志] 一旦某个模型好了，立即告知并触发后续
            log.info(
                f"✨ [AI总结完毕] 平台 {wf.WORKFLOW_NAME} 所需模型 {m_name} 已就绪，准备执行下一步动作..."
            )

            # 成功回调 (如发送通知)
            log.info(f"🚀 正在推送到平台: {wf.WORKFLOW_NAME}")
            await wf.on_report_success(summary, ctx)

            # 尝试触发 RPA 自动化
            await trigger_rpa(wf.WORKFLOW_NAME, summary)

        except Exception as e:
            log.error(f"工作流 {wf.WORKFLOW_NAME} 最终处置失败: {e}")

    # 💡 打印开启了 RPA 的平台状态提示
    for wf in active_workflows:
        platform_config = config.get_platform(wf.WORKFLOW_NAME)
        if platform_config.get("rpa", {}).get("enabled", False):
            log.info(
                f"⚡ [RPA检测] {wf.WORKFLOW_NAME} 已开启自动化填报，响应后将即刻启动..."
            )

    # 启动所有工作流的终结任务 (并发运行，互不干扰)
    await asyncio.gather(*(finalize_workflow_async(wf, ctx) for wf, ctx in wf_contexts))


@handle_logic_exception
async def main():
    # 0. 环境自检：如果启用了 RPA，确保浏览器驱动已安装 (傻瓜式运行)
    await ensure_playwright_browsers()

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
        print("\n" + "!" * 60)
        print("【运行时错误】程序执行过程中发生崩溃：")
        traceback.print_exc()
        print("!" * 60)
        try:
            log.exception(f"Fatal error: {e}")
        except:
            pass
        input("\n按 Enter 键退出程序...")
