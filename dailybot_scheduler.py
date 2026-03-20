"""
DailyBot Windows 定时调度器

职责：
1. 管理 Windows 定时任务（schtasks）和开机自启动（注册表）
2. 响应定时触发，执行核心业务逻辑
3. 支持调试命令行参数

用法：
    DailyBot.exe              # 同步配置（注册/删除定时任务和自启动），静默退出
    DailyBot.exe --trigger    # 执行核心业务逻辑（由定时任务调用）
    DailyBot.exe --status     # 查看当前任务注册状态（分配控制台窗口）
    DailyBot.exe --uninstall  # 清理所有已注册的任务和自启动
"""

import argparse
import asyncio
import ctypes
import logging
import os
import subprocess
import sys
import winreg

from utils.path_helper import get_app_dir

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

TASK_NAME_PREFIX = "DailyBot"
REGISTRY_KEY_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
REGISTRY_VALUE_NAME = "DailyBot"
LOCK_FILE_NAME = ".dailybot.lock"

WEEKDAY_MAP = {
    1: "MON",
    2: "TUE",
    3: "WED",
    4: "THU",
    5: "FRI",
    6: "SAT",
    7: "SUN",
}

WEEKDAY_LABEL = {
    1: "周一",
    2: "周二",
    3: "周三",
    4: "周四",
    5: "周五",
    6: "周六",
    7: "周日",
}


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------


def get_exe_path():
    """获取当前可执行文件的完整路径"""
    if getattr(sys, "frozen", False):
        return os.path.abspath(sys.executable)
    return os.path.abspath(__file__)


def is_frozen():
    """是否在 PyInstaller 打包环境中运行"""
    return getattr(sys, "frozen", False)


def ensure_console():
    """
    在打包无窗口模式下分配控制台窗口。
    """
    if not is_frozen():
        return

    ATTACH_PARENT_PROCESS = -1
    # 尝试附加到父进程的控制台（如在 cmd 或 PowerShell 中运行）
    # 如果失败（例如由任务计划程序启动），则独立分配一个新窗口
    if ctypes.windll.kernel32.AttachConsole(ATTACH_PARENT_PROCESS) == 0:
        ctypes.windll.kernel32.AllocConsole()

    ctypes.windll.kernel32.SetConsoleTitleW("DailyBot")
    # 设置控制台代码页为 UTF-8 防止乱码
    ctypes.windll.kernel32.SetConsoleOutputCP(65001)

    # 启用 ANSI 颜色支持 (ENABLE_VIRTUAL_TERMINAL_PROCESSING)
    STD_OUTPUT_HANDLE = -11
    handle = ctypes.windll.kernel32.GetStdHandle(STD_OUTPUT_HANDLE)
    mode = ctypes.c_ulong()
    if ctypes.windll.kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
        ctypes.windll.kernel32.SetConsoleMode(handle, mode.value | 0x0004)

    # 重新绑定标准 I/O 到控制台
    sys.stdout = open("CONOUT$", "w", encoding="utf-8")
    sys.stderr = open("CONOUT$", "w", encoding="utf-8")
    sys.stdin = open("CONIN$", "r", encoding="utf-8")


def setup_logging():
    """配置调度器专用日志（写入文件，不依赖业务层的 loguru）"""
    log_dir = os.path.join(get_app_dir(), "logs")
    os.makedirs(log_dir, exist_ok=True)

    log_file = os.path.join(log_dir, "scheduler.log")

    # 防止重复添加 handler
    logger = logging.getLogger("DailyBot.Scheduler")
    if not logger.handlers:
        logger.setLevel(logging.DEBUG)

        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
        )
        logger.addHandler(file_handler)

    return logger


def load_scheduler_config():
    """加载 config.yaml 中的 scheduler 配置段"""
    from common import config

    scheduler = config.get("scheduler", {})
    return {
        "enabled": scheduler.get("enabled", False),
        "auto_start": scheduler.get("auto_start", False),
        "default_time": scheduler.get("default_time", "18:00"),
        "tasks": scheduler.get("tasks") or [],
    }


# ---------------------------------------------------------------------------
# 注册表管理（开机自启动）
# ---------------------------------------------------------------------------


def register_startup(exe_path, log):
    """将 DailyBot 写入注册表实现开机自启动"""
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            REGISTRY_KEY_PATH,
            0,
            winreg.KEY_SET_VALUE,
        )
        winreg.SetValueEx(key, REGISTRY_VALUE_NAME, 0, winreg.REG_SZ, f'"{exe_path}"')
        winreg.CloseKey(key)
        log.info(f"✅ 已注册开机自启动: {exe_path}")
        return True
    except Exception as e:
        log.error(f"❌ 注册开机自启动失败: {e}")
        return False


def remove_startup(log):
    """从注册表中删除 DailyBot 开机自启动项"""
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            REGISTRY_KEY_PATH,
            0,
            winreg.KEY_SET_VALUE,
        )
        winreg.DeleteValue(key, REGISTRY_VALUE_NAME)
        winreg.CloseKey(key)
        log.info("✅ 已移除开机自启动")
        return True
    except FileNotFoundError:
        log.info("ℹ️ 开机自启动项不存在，无需移除")
        return True
    except Exception as e:
        log.error(f"❌ 移除开机自启动失败: {e}")
        return False


def check_startup():
    """检查开机自启动注册表项，返回已注册的值或 None"""
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, REGISTRY_KEY_PATH, 0, winreg.KEY_READ
        )
        value, _ = winreg.QueryValueEx(key, REGISTRY_VALUE_NAME)
        winreg.CloseKey(key)
        return value
    except FileNotFoundError:
        return None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# schtasks 管理（定时触发）
# ---------------------------------------------------------------------------


def get_registered_task_names():
    """查询所有已注册的 DailyBot schtasks 任务名"""
    try:
        result = subprocess.run(
            ["schtasks", "/query", "/fo", "CSV", "/nh"],
            capture_output=True,
            text=True,
            encoding="gbk",
        )
        task_names = []
        for line in result.stdout.strip().split("\n"):
            if not line or TASK_NAME_PREFIX not in line:
                continue
            # CSV 格式: "\\任务名","下次运行时间","状态"
            raw_name = line.split(",")[0].strip('"')
            # 去掉前导的 \\ 前缀
            name = raw_name.lstrip("\\")
            if name.startswith(TASK_NAME_PREFIX):
                task_names.append(name)
        return task_names
    except Exception:
        return []


def remove_task(task_name, log):
    """删除单个 schtasks 任务"""
    try:
        result = subprocess.run(
            f'schtasks /delete /tn "{task_name}" /f',
            shell=True,
            capture_output=True,
            text=True,
            encoding="gbk",
        )
        if result.returncode == 0:
            log.info(f"✅ 已删除定时任务: {task_name}")
            return True
        log.warning(f"⚠️ 删除任务 {task_name} 失败: {result.stderr.strip()}")
        return False
    except Exception as e:
        log.error(f"❌ 删除任务 {task_name} 异常: {e}")
        return False


def remove_all_tasks(log):
    """删除所有以 DailyBot 为前缀的 schtasks 任务"""
    task_names = get_registered_task_names()
    for name in task_names:
        remove_task(name, log)
    if not task_names:
        log.info("ℹ️ 没有发现已注册的定时任务")


def register_schtask(task_name, time_str, exe_path, log, weekdays=None):
    """
    注册单个 schtasks 定时任务。

    :param task_name: 任务名称
    :param time_str: 触发时间，格式 "HH:MM"
    :param exe_path: 可执行文件路径
    :param log: 日志记录器
    :param weekdays: 可选的工作日列表 [1..7]，为 None 时注册为每天
    """
    trigger_cmd = f'\\"{exe_path}\\" --trigger'

    if weekdays:
        day_str = ",".join(WEEKDAY_MAP[d] for d in sorted(weekdays) if d in WEEKDAY_MAP)
        cmd = (
            f'schtasks /create /tn "{task_name}" '
            f"/sc WEEKLY /d {day_str} /st {time_str} "
            f'/tr "{trigger_cmd}" /f'
        )
        schedule_desc = f"每周 {day_str}"
    else:
        cmd = (
            f'schtasks /create /tn "{task_name}" '
            f"/sc DAILY /st {time_str} "
            f'/tr "{trigger_cmd}" /f'
        )
        schedule_desc = "每天"

    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, encoding="gbk"
        )
        if result.returncode == 0:
            log.info(f"✅ 已注册定时任务: {task_name} ({schedule_desc} {time_str})")
            return True
        log.error(f"❌ 注册任务 {task_name} 失败: {result.stderr.strip()}")
        return False
    except Exception as e:
        log.error(f"❌ 注册任务 {task_name} 异常: {e}")
        return False


# ---------------------------------------------------------------------------
# 配置同步（核心调度编排）
# ---------------------------------------------------------------------------


def sync_tasks(scheduler_config, log):
    """
    根据当前 config.yaml 的 scheduler 配置，一次性同步所有定时任务和自启动项。

    策略：先全量清理旧任务 → 再按新配置注册，保证幂等。
    """
    enabled = scheduler_config.get("enabled", False)
    auto_start = scheduler_config.get("auto_start", False)
    default_time = scheduler_config.get("default_time", "18:00")
    tasks = scheduler_config.get("tasks") or []

    exe_path = get_exe_path()

    if not enabled:
        log.info("ℹ️ 调度器已禁用 (scheduler.enabled=false)，清理所有任务")
        remove_all_tasks(log)
        remove_startup(log)
        return

    # 1. 处理开机自启动
    if auto_start:
        register_startup(exe_path, log)
    else:
        remove_startup(log)

    # 2. 全量清理旧任务后重新注册（保证配置变更实时生效）
    remove_all_tasks(log)

    # 3. 注册定时任务
    if not tasks:
        # 未配置具体任务，使用 default_time 兜底，每天运行
        register_schtask(f"{TASK_NAME_PREFIX}_Default", default_time, exe_path, log)
    else:
        registered_times = set()
        for idx, task in enumerate(tasks):
            time_str = task.get("time", default_time)
            weekdays = task.get("weekdays")
            task_name = f"{TASK_NAME_PREFIX}_Task_{idx}"
            register_schtask(task_name, time_str, exe_path, log, weekdays)
            registered_times.add(time_str)

        # 如果 default_time 未被任何 task 覆盖，额外注册为每日兜底
        if default_time not in registered_times:
            register_schtask(
                f"{TASK_NAME_PREFIX}_Default",
                default_time,
                exe_path,
                log,
            )

    log.info("🎉 定时任务同步完成")


# ---------------------------------------------------------------------------
# 触发执行（被 schtasks 调用）
# ---------------------------------------------------------------------------


def execute_trigger(log):
    """
    执行 DailyBot 核心业务逻辑。

    通过 filelock 保证同一时刻只有一个实例在运行，
    避免多个定时任务同时触发导致的冲突。
    """
    from filelock import FileLock, Timeout

    lock_path = os.path.join(get_app_dir(), LOCK_FILE_NAME)
    lock = FileLock(lock_path, timeout=10)

    try:
        with lock:
            log.info("🚀 定时任务触发，开始执行核心业务逻辑...")
            from main import main

            asyncio.run(main())
            log.info("✅ 核心业务逻辑执行完毕")
    except Timeout:
        log.warning("⚠️ 另一个 DailyBot 实例正在运行，本次触发跳过")
    except Exception as e:
        log.error(f"❌ 业务逻辑执行失败: {e}", exc_info=True)


# ---------------------------------------------------------------------------
# 状态查询（交互调试）
# ---------------------------------------------------------------------------


def show_status(scheduler_config):
    """在控制台中打印当前调度器的完整状态信息（配置 + 注册表 + 定时任务）"""
    enabled = scheduler_config.get("enabled", False)
    auto_start = scheduler_config.get("auto_start", False)
    default_time = scheduler_config.get("default_time", "N/A")
    tasks = scheduler_config.get("tasks") or []

    print("=" * 60)
    print("  DailyBot 调度器状态")
    print("=" * 60)

    # --- 配置 ---
    print(f"\n📋 配置:")
    print(f"  scheduler.enabled:      {enabled}")
    print(f"  scheduler.auto_start:   {auto_start}")
    print(f"  scheduler.default_time: {default_time}")
    print(f"  scheduler.tasks:        {len(tasks)} 个")
    for idx, task in enumerate(tasks):
        weekdays = task.get("weekdays") or []
        dates = task.get("dates") or []
        wd_str = (
            ", ".join(WEEKDAY_LABEL.get(d, "?") for d in weekdays)
            if weekdays
            else "每天"
        )
        dt_str = ", ".join(dates) if dates else "无"
        print(
            f"    [{idx}] 时间={task.get('time', 'N/A')}  "
            f"工作日={wd_str}  日期={dt_str}"
        )

    # --- 开机自启动 ---
    startup_value = check_startup()
    print(f"\n🔑 开机自启动:")
    if startup_value:
        print(f"  ✅ 已注册: {startup_value}")
    else:
        print(f"  ❌ 未注册")

    # --- 定时任务 ---
    task_names = get_registered_task_names()
    print(f"\n⏰ 已注册的定时任务:")
    if task_names:
        for name in task_names:
            print(f"  ✅ {name}")
    else:
        print(f"  ❌ 无已注册的定时任务")

    # --- 运行环境 ---
    print(f"\n🖥️ 运行环境:")
    print(f"  打包模式: {'是' if is_frozen() else '否 (源码模式)'}")
    print(f"  可执行路径: {get_exe_path()}")
    print(f"  工作目录:   {get_app_dir()}")

    print("\n" + "=" * 60)

    # 打包模式下暂停，让用户看到输出
    if is_frozen():
        input("\n按 Enter 键关闭...")


# ---------------------------------------------------------------------------
# 卸载
# ---------------------------------------------------------------------------


def do_uninstall(log):
    """清理所有已注册的定时任务和自启动项"""
    log.info("🗑️ 正在卸载所有 DailyBot 定时任务...")
    remove_all_tasks(log)
    remove_startup(log)

    print("✅ 已清理所有 DailyBot 定时任务和自启动项")
    log.info("✅ 卸载完成")

    if is_frozen():
        input("\n按 Enter 键关闭...")


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------


def main():
    # schtasks 启动时默认在 system32，必须切换到 exe 所在目录
    os.chdir(get_app_dir())

    parser = argparse.ArgumentParser(description="DailyBot 定时调度器")
    parser.add_argument(
        "--trigger",
        action="store_true",
        help="执行核心业务逻辑（由定时任务调用）",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="查看当前任务注册状态",
    )
    parser.add_argument(
        "--uninstall",
        action="store_true",
        help="清理所有已注册的任务和自启动",
    )
    args = parser.parse_args()

    if args.trigger or args.status or args.uninstall:
        ensure_console()

    log = setup_logging()
    scheduler_config = load_scheduler_config()

    if args.trigger:
        execute_trigger(log)
    elif args.status:
        show_status(scheduler_config)
    elif args.uninstall:
        do_uninstall(log)
    else:
        # 默认模式：静默同步配置后退出
        log.info("🔄 开始同步调度器配置...")
        sync_tasks(scheduler_config, log)


if __name__ == "__main__":
    main()
