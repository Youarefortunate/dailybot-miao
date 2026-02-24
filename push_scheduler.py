import asyncio
import os
import sys
from datetime import datetime

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from loguru import logger
from win32com.client import Dispatch
import winshell

# 确保能导入项目根目录的模块
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import main
from common.config import config
from token_storage import get_platform_storage, load_all_tokens


def refresh_all_tokens():
    """动态刷新配置启用的平台及所有用户的 access_token"""
    logger.info("开始刷新所有平台 Token...")
    try:
        tokens = load_all_tokens()
        # 这里的逻辑保持与原 push_scheduler.py 一致
        # load_all_tokens 返回的是各个平台的 token map
        for platform_key, platform_tokens in tokens.items():
            storage = get_platform_storage(platform_key)
            if not storage:
                continue
            for identifier in platform_tokens.keys():
                try:
                    storage.refresh_token(identifier)
                    logger.info(f"刷新 {platform_key} ({identifier}) 成功")
                except Exception as e:
                    logger.error(f"刷新 {platform_key} ({identifier}) 失败: {e}")
    except Exception as e:
        logger.error(f"加载/刷新 Token 过程中发生错误: {e}")


async def run_job():
    """执行推送日报/周报的完整流程"""
    logger.info("[定时任务] 触发自动推送流程...")
    # 1. 刷新 Token
    refresh_all_tokens()
    # 2. 调用核心业务逻辑
    try:
        await main.main()
        logger.info("[定时任务] 流程执行完毕。")
    except Exception as e:
        logger.error(f"[定时任务] 核心逻辑执行失败: {e}")


def is_date_match(config_dates, target_date: datetime):
    """判断 target_date 是否在 config_dates 定义的范围内"""
    if not config_dates:
        return False

    target_str = target_date.strftime("%Y-%m-%d")
    target_month = target_date.strftime("%Y-%m")

    for date_expr in config_dates:
        # 支持区间 2026-02-01/2026-02-15
        if "/" in date_expr:
            try:
                start_str, end_str = date_expr.split("/")
                # 处理简化格式如 2026-02
                if len(start_str) == 7:
                    start_str += "-01"
                if len(end_str) == 7:
                    end_str += "-28"  # 模糊匹配，后续用 strptime 校验

                start_dt = datetime.strptime(start_str, "%Y-%m-%d")
                end_dt = datetime.strptime(end_str, "%Y-%m-%d")
                if start_dt.date() <= target_date.date() <= end_dt.date():
                    return True
            except:
                continue
        # 支持精确日期 or 月份
        elif date_expr == target_str or date_expr == target_month:
            return True
    return False


def check_all_expired(tasks, target_date: datetime):
    """检查是否所有任务的日期都已处于过去（不包含今日）"""
    if not tasks:
        return True

    for task in tasks:
        dates = task.get("dates", [])
        if not dates:
            continue
        for date_expr in dates:
            try:
                # 取表达式中的最晚日期
                compare_str = date_expr.split("/")[-1]
                if len(compare_str) == 7:  # YYYY-MM
                    compare_dt = datetime.strptime(compare_str + "-01", "%Y-%m-%d")
                    # 月份比较需要特殊处理，只要目标月还没过或者就是当月
                    if target_date.strftime("%Y-%m") <= compare_str:
                        return False
                else:  # YYYY-MM-DD
                    compare_dt = datetime.strptime(compare_str, "%Y-%m-%d")
                    if target_date.date() <= compare_dt.date():
                        return False
            except:
                continue
    return True


def manage_windows_autostart(enabled: bool):
    """
    管理 Windows 开机自启（通过 Startup 文件夹 + VBS 隐身启动）
    """
    startup_path = winshell.startup()
    shortcut_path = os.path.join(startup_path, "DailyBotSilent.lnk")

    # 获取 run_silent.vbs 的绝对路径
    vbs_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "scripts", "run_silent.vbs"
    )

    if enabled:
        if not os.path.exists(shortcut_path):
            try:
                w_dir = os.path.dirname(os.path.abspath(__file__))

                shell = Dispatch("WScript.Shell")
                shortcut = shell.CreateShortCut(shortcut_path)
                # 目标设为 wscript.exe，参数为 vbs 路径
                shortcut.Targetpath = "wscript.exe"
                shortcut.Arguments = f'"{vbs_path}"'
                shortcut.WorkingDirectory = w_dir
                shortcut.save()
                logger.info(f"已创建静默启动快捷方式: {shortcut_path}")
            except Exception as e:
                logger.error(f"创建静默启动快捷方式失败: {e}")
    else:
        if os.path.exists(shortcut_path):
            try:
                os.remove(shortcut_path)
                logger.info(f"已移除静默启动快捷方式: {shortcut_path}")
            except Exception as e:
                logger.error(f"移除静默启动快捷方式失败: {e}")


def setup_scheduler():
    scheduler_cfg = config.get("scheduler", {})
    if not scheduler_cfg or not scheduler_cfg.get("enabled"):
        logger.warning("调度器未启用 (config.yaml: scheduler.enabled 为 false)")
        return

    # 管理自启动
    auto_start = scheduler_cfg.get("auto_start", False)
    manage_windows_autostart(auto_start)

    scheduler = BlockingScheduler()
    tasks = scheduler_cfg.get("tasks", [])
    default_time = scheduler_cfg.get("default_time", "18:20")

    def plan_today_jobs():
        now = datetime.now()
        logger.info(f"--- 规划今日 ({now.strftime('%Y-%m-%d')}) 的推送任务 ---")

        executed_today = False
        today_match_tasks = []

        for task in tasks:
            # 1. 检查日期
            if is_date_match(task.get("dates"), now):
                # 2. 检查星期
                weekdays = task.get("weekdays", [1, 2, 3, 4, 5, 6, 7])
                if now.isoweekday() in weekdays:
                    today_match_tasks.append(task)

        if today_match_tasks:
            for task in today_match_tasks:
                run_time = task.get("time", default_time)
                h, m = map(int, run_time.split(":"))
                # 如果该时间还没过，则安排运行
                if now.hour < h or (now.hour == h and now.minute < m):
                    logger.info(f"匹配到任务，安排在今日 {run_time} 执行")

                    scheduler.add_job(
                        lambda: asyncio.run(run_job()),
                        "date",
                        run_date=now.replace(hour=h, minute=m, second=0, microsecond=0),
                    )
                else:
                    logger.info(f"匹配到任务 {run_time}，但今日该时间已过，跳过。")
            executed_today = True

        # 3. 兜底逻辑：如果今日不匹配，或者所有配置已过期
        if not today_match_tasks:
            all_expired = check_all_expired(tasks, now)
            if all_expired:
                logger.info("所有配置日期已过期或未配置日期，触发保底逻辑。")
            else:
                logger.info("今日不符合任何任务的日期/星期规则，尝试保底逻辑。")

            h, m = map(int, default_time.split(":"))
            if now.hour < h or (now.hour == h and now.minute < m):
                logger.info(f"安排保底推送时间：今日 {default_time}")

                scheduler.add_job(
                    lambda: asyncio.run(run_job()),
                    "date",
                    run_date=now.replace(hour=h, minute=m, second=0, microsecond=0),
                )
            else:
                logger.info(f"保底时间 {default_time} 已过，今日无任务。")

    # 每天 00:00:05 执行一次规划
    scheduler.add_job(plan_today_jobs, CronTrigger(hour=0, minute=0, second=5))

    # 启动时立即执行一次规划
    plan_today_jobs()

    logger.info("调度服务已启动，按计划运行中...")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("调度服务已停止。")


if __name__ == "__main__":
    setup_scheduler()
