import os
import sys
import time
import subprocess
import atexit
import psutil
import winshell
from datetime import datetime
from win32com.client import Dispatch
from loguru import logger

# 确保能导入 common.config
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from common.config import config
from utils.path_helper import get_app_dir


class WindowsTaskScheduler:
    """
    使用 Windows schtasks 命令管理开机自启任务
    """

    TASK_NAME = "DailyBotAutoStart"

    @classmethod
    def setup(cls, auto_start: bool):
        """
        根据配置启用或禁用开机自启
        """
        if auto_start:
            # 优先尝试计划任务，失败则回退到启动文件夹
            if not cls._create_task():
                cls._create_startup_shortcut()
        else:
            cls._delete_task()
            cls._delete_startup_shortcut()

    @classmethod
    def _create_task(cls):
        """
        创建登录时启动的任务
        """
        app_dir = get_app_dir()
        bat_path = os.path.join(app_dir, "scripts", "DailyBot.bat")
        powershell_cmd = f"powershell.exe -ExecutionPolicy Bypass -WindowStyle Hidden -Command \"& '{bat_path}' --service\""

        cmd = [
            "schtasks",
            "/Create",
            "/SC",
            "ONLOGON",
            "/TN",
            cls.TASK_NAME,
            "/TR",
            powershell_cmd,
            "/F",
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=False)
            if result.returncode == 0:
                logger.info(f"已成功创建 Windows 计划任务: {cls.TASK_NAME}")
                return True
            else:
                stderr_msg = result.stderr.strip()
                if "Access is denied" in stderr_msg:
                    logger.debug(
                        "权限不足，无法创建计划任务(schtasks)，将自动使用启动文件夹替代方案。"
                    )
                else:
                    logger.debug(f"计划任务创建受阻: {stderr_msg}")
                return False
        except Exception:
            return False

    @classmethod
    def _create_startup_shortcut(cls):
        """
        回退方案：在 Windows 启动文件夹创建快捷方式
        """
        try:
            app_dir = get_app_dir()
            startup_path = winshell.startup()
            shortcut_path = os.path.join(startup_path, f"{cls.TASK_NAME}.lnk")

            # 寻找 pythonw.exe
            python_exe = sys.executable
            pythonw_exe = python_exe.lower().replace("python.exe", "pythonw.exe")
            if not os.path.exists(pythonw_exe):
                pythonw_exe = python_exe

            shell = Dispatch("WScript.Shell")
            shortcut = shell.CreateShortCut(shortcut_path)
            shortcut.Targetpath = pythonw_exe
            # 运行当前脚本并带上 --service 参数
            shortcut.Arguments = f'"{os.path.abspath(__file__)}" --service'
            shortcut.WorkingDirectory = app_dir
            shortcut.WindowStyle = 7  # Minimized/Hidden style
            shortcut.save()
            logger.info(f"已通过启动文件夹实现开机自启: {shortcut_path}")
            return True
        except Exception as e:
            logger.error(f"所有开机自启方案均失败: {e}")
            return False

    @classmethod
    def _delete_task(cls):
        """
        删除计划任务
        """
        cmd = ["schtasks", "/Delete", "/TN", cls.TASK_NAME, "/F"]
        try:
            subprocess.run(cmd, capture_output=True, text=True, check=False)
        except Exception:
            pass

    @classmethod
    def _delete_startup_shortcut(cls):
        """
        删除启动文件夹中的快捷方式
        """
        try:
            startup_path = winshell.startup()
            shortcut_path = os.path.join(startup_path, f"{cls.TASK_NAME}.lnk")
            if os.path.exists(shortcut_path):
                os.remove(shortcut_path)
                logger.info("已移除启动文件夹中的自启快捷方式。")
        except Exception:
            pass


class SchedulerEngine:
    """
    调度引擎：负责时间匹配与任务触发
    """

    def __init__(self):
        self.last_executed_date = ""
        self.last_executed_time = ""
        self.pid_file = os.path.join(get_app_dir(), "logs", "scheduler.pid")

    def _acquire_lock(self):
        """
        单例保护：确保只有一个调度进程
        """
        os.makedirs(os.path.dirname(self.pid_file), exist_ok=True)
        if os.path.exists(self.pid_file):
            try:
                with open(self.pid_file, "r") as f:
                    old_pid = int(f.read().strip())

                if psutil.pid_exists(old_pid):
                    proc = psutil.Process(old_pid)
                    cmdline = " ".join(proc.cmdline())
                    if "dailybot_scheduler" in cmdline:
                        logger.warning(
                            f"检测到已有调度进程正在运行 (PID: {old_pid})，程序退出。"
                        )
                        return False

                # 如果 PID 不存在，则是僵尸锁
                os.remove(self.pid_file)
            except Exception:
                pass

        with open(self.pid_file, "w") as f:
            f.write(str(os.getpid()))

        atexit.register(self._release_lock)
        return True

    def _release_lock(self):
        """
        释放 PID 锁
        """
        if os.path.exists(self.pid_file):
            try:
                with open(self.pid_file, "r") as f:
                    pid = int(f.read().strip())
                if pid == os.getpid():
                    os.remove(self.pid_file)
                    logger.info("已释放 PID 锁文件。")
            except:
                pass

    def _get_today_tasks(self):
        """
        解析 config.yaml，获取今日有效的时间点
        """
        sc = config.get("scheduler", {})
        tasks = sc.get("tasks", [])
        default_time = sc.get("default_time", "18:20")

        now = datetime.now()
        today_str = now.strftime("%Y-%m-%d")
        weekday = now.isoweekday()

        scheduled_times = set()
        for t in tasks:
            match_date = False
            if "dates" in t and today_str in t["dates"]:
                match_date = True
            if "weekdays" in t and weekday in t["weekdays"]:
                match_date = True
            if "dates" not in t and "weekdays" not in t:
                match_date = True

            if match_date:
                scheduled_times.add(t.get("time", default_time))

        if not scheduled_times:
            scheduled_times.add(default_time)

        return sorted(list(scheduled_times))

    def _trigger_main(self):
        """
        调用主程序
        """
        logger.info("[触发] 满足定时规则，正在启动 DailyBot 主流程...")
        try:
            app_dir = get_app_dir()
            python_exe = os.path.join(app_dir, ".venv", "Scripts", "python.exe")
            if not os.path.exists(python_exe):
                python_exe = sys.executable

            subprocess.Popen(
                [python_exe, "main.py"],
                cwd=app_dir,
                creationflags=0x00000008 | 0x08000000,
            )
        except Exception as e:
            logger.error(f"启动主流程失败: {e}")

    def _cleanup_old_process(self):
        """
        热重启支持：检测并杀死正在运行的旧后台进程
        """
        if not os.path.exists(self.pid_file):
            return

        try:
            with open(self.pid_file, "r") as f:
                content = f.read().strip()
                if not content:
                    os.remove(self.pid_file)
                    return
                old_pid = int(content)

            if psutil.pid_exists(old_pid):
                proc = psutil.Process(old_pid)
                cmdline = " ".join(proc.cmdline())
                if "dailybot_scheduler" in cmdline:
                    logger.info(
                        f"检测到正在运行的旧进程 (PID: {old_pid})，正在进行热重启..."
                    )
                    proc.terminate()
                    # 等待进程退出
                    for _ in range(10):
                        if not psutil.pid_exists(old_pid):
                            break
                        time.sleep(0.5)
                    if psutil.pid_exists(old_pid):
                        proc.kill()
                    logger.info("旧进程已终止。")

            # 准备启动新进程前，清理旧 PID 文件
            if os.path.exists(self.pid_file):
                os.remove(self.pid_file)
        except Exception as e:
            logger.debug(f"清理旧进程时出错: {e}")
            if os.path.exists(self.pid_file):
                try:
                    os.remove(self.pid_file)
                except:
                    pass

    def run(self):
        """
        主循环
        """
        is_service = "--service" in sys.argv

        # 1. 优先应用自启动配置
        auto_start = config.get("scheduler.auto_start", False)
        WindowsTaskScheduler.setup(auto_start)

        if not is_service:
            # 手动执行模式：支持热重启逻辑
            self._cleanup_old_process()

            app_dir = get_app_dir()
            pythonw_exe = os.path.join(app_dir, ".venv", "Scripts", "pythonw.exe")
            if not os.path.exists(pythonw_exe):
                pythonw_exe = sys.executable  # 最终兜底使用 python.exe

            logger.info("正在将调度服务切换至后台运行...")
            script_path = os.path.abspath(__file__)
            boot_log = os.path.join(app_dir, "logs", "scheduler_boot.log")

            # 使用 utf-8-sig (带 BOM) 确保 Windows 记事本等工具不乱码
            with open(boot_log, "a", encoding="utf-8-sig") as f:
                f.write(f"\n--- Booting at {datetime.now()} ---\n")
                f.write(f"PythonW: {pythonw_exe}\n")
                f.flush()

                subprocess.Popen(
                    [pythonw_exe, script_path, "--service"],
                    cwd=app_dir,
                    stdout=f,
                    stderr=f,
                    creationflags=0x00000008 | 0x08000000,
                )

            logger.info("已成功推送配置并启动后台服务。本窗口将在 3 秒后关闭。")
            time.sleep(3)
            sys.exit(0)

        # 2. 以下为 --service 服务模式逻辑
        if not self._acquire_lock():
            sys.exit(0)

        logger.info("调度引擎已启动 (后台服务)，进入任务监听状态...")

        while True:
            try:
                now = datetime.now()
                today_str = now.strftime("%Y-%m-%d")
                curr_time_str = now.strftime("%H:%M")

                target_times = self._get_today_tasks()

                if curr_time_str in target_times:
                    if (
                        self.last_executed_date != today_str
                        or self.last_executed_time != curr_time_str
                    ):
                        self._trigger_main()
                        self.last_executed_date = today_str
                        self.last_executed_time = curr_time_str

                time.sleep(30)
            except KeyboardInterrupt:
                break
            except Exception as e:
                logger.error(f"调度循环发生异常: {e}")
                time.sleep(60)


if __name__ == "__main__":
    import common.logger

    engine = SchedulerEngine()
    engine.run()
