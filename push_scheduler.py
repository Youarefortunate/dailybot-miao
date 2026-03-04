import asyncio
import atexit
import os
import subprocess
import sys
from datetime import datetime
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from loguru import logger
import psutil
from common.config import config
from utils.path_helper import get_app_dir, get_resource_path


async def run_job():
    """执行推送日报/周报的完整流程"""
    # 延迟导入 main 以显著提升启动速度
    import main

    logger.info("[定时任务] 触发自动推送流程...")
    try:
        await main.main()
        logger.info("[定时任务] 流程执行完毕。")
    except Exception as e:
        logger.error(f"[定时任务] 核心逻辑执行失败: {e}")


def is_date_match(config_dates, target_date: datetime):
    """判断 target_date 是否在 config_dates 定义的范围内。如果未配置日期，则默认为每天都匹配。"""
    if not config_dates:
        return True

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


def check_singleton(is_service: bool = False):
    """
    检查并管理单例模式，解决启动器与服务进程的竞态条件。
    :param is_service: 是否为后台服务模式
    :return: (bool, int) -> (是否通过检测, 冲突的 PID)
    """
    # 只有 is_service 且非 is_once 且不冲突时，才写入锁
    # 使用 get_app_dir() 获取 .exe 物理同级目录，避免写入临时目录
    app_dir = get_app_dir()
    lock_file = os.path.join(app_dir, "logs", ".scheduler.lock")
    os.makedirs(os.path.dirname(lock_file), exist_ok=True)

    # 1. 检测旧实例并尝试清理
    if os.path.exists(lock_file):
        try:
            with open(lock_file, "r") as f:
                content = f.read().strip()
                old_pid = int(content) if content else None

            if old_pid and psutil.pid_exists(old_pid):
                proc = psutil.Process(old_pid)
                # 校验是否为 Python 进程（避免误杀）
                if "python" in proc.name().lower():
                    if not is_service:
                        logger.info(
                            f"检测到正在运行的旧实例 (PID: {old_pid})，正在终止..."
                        )
                        proc.terminate()
                        try:
                            # 给 5 秒优雅退出的时间
                            proc.wait(timeout=5)
                        except psutil.TimeoutExpired:
                            logger.warning(
                                f"旧实例 (PID: {old_pid}) 未能及时退出，强制杀死..."
                            )
                            proc.kill()

                        # 【关键】启动器必须确保物理删除锁文件，否则新服务进程会读到旧 PID
                        if os.path.exists(lock_file):
                            try:
                                os.remove(lock_file)
                                logger.debug("已物理删除旧锁文件。")
                            except Exception as e:
                                logger.error(f"无法删除旧锁文件: {e}")
                    else:
                        # 服务进程模式：如果发现锁文件中的 PID 不是自己，则冲突
                        if old_pid != os.getpid():
                            return False, old_pid
            else:
                # 如果 PID 已不存在，启动器直接删掉僵尸锁文件
                if not is_service:
                    try:
                        os.remove(lock_file)
                        logger.debug("已清理残留的僵尸锁文件。")
                    except:
                        pass
        except Exception as e:
            logger.debug(f"校验旧锁文件时发生异常: {e}")

    # 2. 只有服务进程 (Service) 有权正式写入进程锁
    if is_service:
        try:
            with open(lock_file, "w") as f:
                f.write(str(os.getpid()))

            def remove_lock():
                if os.path.exists(lock_file):
                    try:
                        with open(lock_file, "r") as f:
                            content = f.read().strip()
                            if content and int(content) == os.getpid():
                                os.remove(lock_file)
                                logger.debug(
                                    f"服务正常退出，已清理锁文件 (PID: {os.getpid()})"
                                )
                    except:
                        pass

            atexit.register(remove_lock)
            logger.info(f"服务运行中，已锁定进程 (PID: {os.getpid()})")
        except Exception as e:
            logger.error(f"服务进程写入锁文件失败: {e}")

    return True, os.getpid()


def manage_windows_autostart(enabled: bool, is_service: bool = False):
    """
    管理 Windows 开机自启（通过 Startup 文件夹 + PowerShell 隐身启动）
    """
    import winshell
    from win32com.client import Dispatch

    app_dir = get_app_dir()

    startup_path = winshell.startup()
    shortcut_name = "DailyBotScheduler.lnk"
    shortcut_path = os.path.join(startup_path, shortcut_name)
    bat_path = os.path.join(app_dir, "scripts", "DailyBot.bat")

    if enabled:
        try:
            shell = Dispatch("WScript.Shell")
            shortcut = shell.CreateShortCut(shortcut_path)

            # 检测是否在打包环境中运行
            if getattr(sys, "frozen", False):
                # 如果是打包环境，直接运行 .exe 自身
                target_exe = sys.executable
                powershell_args = f"-ExecutionPolicy Bypass -WindowStyle Hidden -Command \"& '{target_exe}' --service\""
                shortcut.Targetpath = target_exe
                shortcut.Arguments = "--service"
            else:
                # 源码环境：通过 PowerShell 直接调用 .bat
                # 使用 & 符号调用路径，并添加 -ExecutionPolicy Bypass 确保执行权限
                powershell_args = f"-ExecutionPolicy Bypass -WindowStyle Hidden -Command \"& '{bat_path}' --service\""
                shortcut.Targetpath = "powershell.exe"
                shortcut.Arguments = powershell_args
            shortcut.WorkingDirectory = app_dir
            shortcut.IconLocation = "powershell.exe,0"
            shortcut.save()
            logger.info(f"已更新静默启动快捷方式: {shortcut_path}")

            # 如果当前不是以 service 模式运行，且开启了自启，则立即后台化并退出前台进程
            if not is_service:
                powershell_cmd = f"powershell.exe {powershell_args}"
                # CREATE_NO_WINDOW = 0x08000000, DETACHED_PROCESS = 0x00000008
                subprocess.Popen(
                    powershell_cmd, shell=True, creationflags=0x08000000 | 0x00000008
                )

                logger.info("检测到开启自启配置，已立即在后台拉起静默实例。")
                logger.info("本窗口即将自动关闭，调度服务将持续在后台运行。")
                sys.exit(0)
            else:
                logger.info("当前已处于后台服务模式，调度正常运行中。")

        except Exception as e:
            logger.error(f"管理自启动过程发生错误: {e}")
    else:
        if os.path.exists(shortcut_path):
            try:
                os.remove(shortcut_path)
                logger.info(f"已移除静默启动快捷方式: {shortcut_path}")
                logger.info(
                    "提示：若需彻底停止后台运行的旧实例，请在任务管理器中结束 Python 进程。"
                )
            except Exception as e:
                logger.error(f"移除静默启动快捷方式失败: {e}")


def setup_scheduler():
    scheduler_cfg = config.get("scheduler", {})
    if not scheduler_cfg or not scheduler_cfg.get("enabled"):
        logger.warning("调度器未启用 (config.yaml: scheduler.enabled 为 false)")
        return

    # 1. 检测运行模式
    is_service = "--service" in sys.argv
    is_once = "--once" in sys.argv

    # 1.1 单次运行模式直接调用 main
    if is_once:
        logger.info("[手动任务] 立即执行一次上报流程...")
        import main

        asyncio.run(main.main())
        return

    # 2. 单例检测与热重载逻辑
    # 如果是手动双击运行 (not is_service)，则由 check_singleton 负责清理旧进程
    # 只有 is_service 为 True 时，才会执行正式的锁文件写入
    is_running, pid = check_singleton(is_service=is_service)
    if not is_running:
        logger.warning(f"检测到已有调度实例正在后台运行 (PID: {pid})，请勿重复启动。")
        sys.exit(0)

    # 3. 管理自启动
    auto_start = scheduler_cfg.get("auto_start", False)
    manage_windows_autostart(auto_start, is_service)

    scheduler = BlockingScheduler()
    tasks = scheduler_cfg.get("tasks", [])
    default_time = scheduler_cfg.get("default_time", "18:20")

    def plan_today_jobs():
        now = datetime.now()
        logger.info(f"--- 规划今日 ({now.strftime('%Y-%m-%d')}) 的推送任务 ---")

        today_match_tasks = []
        date_matched_tasks = []

        for task in tasks:
            # 1. 检查日期
            if is_date_match(task.get("dates"), now):
                date_matched_tasks.append(task)
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
        else:
            # 3. 兜底逻辑：只有在今日没有任何任务属于“计划内”时，才触发保底逻辑。
            # 如果 date_matched_tasks 不为空，说明今天本来是有任务的，只是被星期过滤了，此时不应保底触发。
            if not date_matched_tasks:
                all_expired = check_all_expired(tasks, now)
                if all_expired:
                    logger.info("所有配置日期已过期或未配置日期，触发保底逻辑。")
                else:
                    logger.info("今日不符合任何任务的日期规则，尝试保底逻辑。")

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
            else:
                logger.info("今日任务已由星期规则排除，无需保底触发，进入静默状态。")

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
