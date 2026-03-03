import os
import asyncio
import random
from abc import ABC, abstractmethod
from typing import Any, Dict
from playwright.async_api import async_playwright, BrowserContext, Page
from loguru import logger
from playwright_stealth import Stealth
from .rpa_manager import rpa_manager


class BaseRPA(ABC):
    """
    RPA 业务控制基类
    """

    RPA_NAME = "unknown"

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if cls.RPA_NAME != "unknown":
            rpa_manager.register(cls.RPA_NAME, cls)

    def __init__(self, config: dict):
        self.config = config
        self.playwright = None
        self.browser_context = None
        self.page = None

        # 频率控制相关
        platform_config = self.config.get(self.RPA_NAME, {})
        rpa_config = platform_config.get("rpa", {})

        # 0.1 (最快) - 1 (模拟真人)
        raw_speed = rpa_config.get("speed", 1)
        try:
            self.speed_val = float(raw_speed)
            if not (0.1 <= self.speed_val <= 1.0):
                logger.warning(
                    f"[{self.RPA_NAME}] speed 值 {raw_speed} 不在 0.1 - 1 范围内，回退至 1"
                )
                self.speed_val = 1.0
        except (ValueError, TypeError):
            logger.warning(f"[{self.RPA_NAME}] speed 值 {raw_speed} 非法，回退至 1")
            self.speed_val = 1.0

        # 获取更易读的速度描述（移除 1.0 后的小数点）
        display_speed = (
            int(self.speed_val)
            if self.speed_val == int(self.speed_val)
            else self.speed_val
        )
        logger.debug(f"[{self.RPA_NAME}] 自动化速度倍率已设置为: {display_speed}")

        # 外部化配置读取
        self.form_url = rpa_config.get("form_url", "")
        self.max_retry = rpa_config.get("max_retry", 1)

    async def _human_sleep(self, base_delay: float = 1.0):
        """
        模拟真人随机延迟
        :param base_delay: 基础延迟时间(秒)
        """
        # 使用数值倍率进行调整
        delay = base_delay * self.speed_val
        # 增加 20% - 70% 的随机扰动，使点击间隔不固定
        jitter = delay * random.uniform(0.2, 0.7)
        total_delay = delay + jitter

        logger.trace(
            f"[{self.RPA_NAME}] 模拟真人延迟: {total_delay:.2f}s (base: {base_delay}s, speed_val: {self.speed_val})"
        )
        await asyncio.sleep(total_delay)

    async def _init_browser(self):
        """初始化 Playwright 浏览器并加载用户配置"""
        self.playwright = await async_playwright().start()

        # 提取平台通用配置逻辑
        platform_config = self.config.get(self.RPA_NAME, {})
        rpa_config = platform_config.get("rpa", {})

        browser_type = rpa_config.get("browser_type", "chrome")
        user_data_dir = rpa_config.get("browser_user_data_dir")
        executable_path = rpa_config.get("browser_executable_path")

        # 默认路径处理
        if not user_data_dir:
            user_data_dir = os.path.abspath(
                os.path.join(os.getcwd(), ".browser_profiles", browser_type)
            )

        if not os.path.exists(user_data_dir):
            os.makedirs(user_data_dir, exist_ok=True)
            logger.info(f"[{self.RPA_NAME}] 创建用户数据目录: {user_data_dir}")

        logger.info(
            f"[{self.RPA_NAME}] 正在启动浏览器 ({browser_type}), 用户数据目录: {user_data_dir}"
        )

        launch_params = {
            "user_data_dir": user_data_dir,
            "headless": False,
            "viewport": {"width": 1920, "height": 1080},
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "args": [
                "--start-maximized",
                "--disable-blink-features=AutomationControlled",  # 关键：尝试隐藏自动化受控特征
            ],
            "ignore_default_args": ["--enable-automation"],  # 进一步隐藏
        }
        # 获取浏览器执行路径
        final_path = await self._get_executable_path(browser_type, executable_path)
        if final_path:
            launch_params["executable_path"] = final_path
        else:
            # 最终兜底：使用 channel 机制
            launch_params["channel"] = (
                "chrome" if browser_type == "chrome" else "msedge"
            )
            logger.debug(
                f"[{self.RPA_NAME}] 未找到物理可执行文件，将使用 Playwright Channel: {launch_params['channel']}"
            )

        # 启动持久化上下文
        self.browser_context = await self.playwright.chromium.launch_persistent_context(
            **launch_params
        )
        self.page = await self.browser_context.new_page()
        # 注入 stealth 擦除 webdriver 等指纹特征
        await Stealth().apply_stealth_async(self.page)
        logger.debug(f"[{self.RPA_NAME}] 浏览器初始化完成")

    async def _get_executable_path(
        self, browser_type: str, user_specified_path: str = None
    ) -> str:
        """
        健壮的浏览器路径寻找策略
        :param browser_type: 浏览器类型 (chrome/msedge)
        :param user_specified_path: 用户指定的路径
        :return: 最终确定的物理路径，若未找到则返回 None
        """

        final_executable_path = None
        user_path_exists = False
        user_path_mismatch = False

        # 常见内置标准路径预定义 (Windows)
        default_paths = {
            "chrome": [
                r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
                os.path.expandvars(
                    r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"
                ),
            ],
            "msedge": [
                r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
                r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
                os.path.expandvars(
                    r"%LOCALAPPDATA%\Microsoft\Edge\Application\msedge.exe"
                ),
            ],
        }

        # 1. 预校验用户指定的路径
        if user_specified_path:
            if os.path.exists(user_specified_path):
                user_path_exists = True
                path_lower = user_specified_path.lower()
                # 检查类型是否匹配 (指鹿为马预防)
                if (browser_type == "chrome" and "edge" in path_lower) or (
                    browser_type == "msedge" and "chrome" in path_lower
                ):
                    user_path_mismatch = True
                    logger.warning(
                        f"[{self.RPA_NAME}] 警告：配置为 {browser_type} 但指定的路径指向了另一个浏览器: {user_specified_path}"
                    )

                # 如果既存在又匹配，直接采用
                if not user_path_mismatch:
                    final_executable_path = user_specified_path
                    logger.debug(
                        f"[{self.RPA_NAME}] 使用用户指定的匹配路径: {final_executable_path}"
                    )
            else:
                logger.warning(
                    f"[{self.RPA_NAME}] 指定的浏览器路径不存在: {user_specified_path}"
                )

        # 2. 如果没指定、指定的路径不存在、或者指定的路径类型不匹配，则尝试内置标准路径
        if not final_executable_path:
            logger.info(
                f"[{self.RPA_NAME}] 正在尝试自动寻找内置标准路径 ({browser_type})..."
            )
            search_list = default_paths.get(browser_type, [])
            for p in search_list:
                if os.path.exists(p):
                    final_executable_path = p
                    logger.info(
                        f"[{self.RPA_NAME}] 成功在标准位置找到 {browser_type}: {final_executable_path}"
                    )
                    break

        # 3. 如果内置搜索仍然失败，但用户指定了一个虽然“看起来不对”但“确实存在”的路径，作为最后的物理路径尝试
        if not final_executable_path and user_path_exists:
            final_executable_path = user_specified_path
            logger.warning(
                f"[{self.RPA_NAME}] 未能找到标准路径，回退使用用户指定的物理路径（尽管可能类型不符）: {final_executable_path}"
            )

        return final_executable_path

    @abstractmethod
    async def _handle_login(self) -> bool:
        """处理登录逻辑（由子类实现）"""
        pass

    @abstractmethod
    async def fill_form(self, report_data: Dict[str, Any]):
        """执行表单填充逻辑（由子类实现）"""
        pass

    async def run(self, report_data: Dict[str, Any]):
        """
        RPA 运行入口（模板方法设计模式）
        """
        # 首先确保浏览器已启动
        try:
            await self._init_browser()
        except Exception as e:
            logger.error(f"[{self.RPA_NAME}] 浏览器初始化失败: {e}")
            raise

        try:
            # 执行登录逻辑并检查状态
            if not await self._handle_login():
                logger.error(
                    f"[{self.RPA_NAME}] 登录初始化流程异常中止，请检查页面状态。"
                )
                return

            # 执行填报
            await self.fill_form(report_data)

            logger.info(
                f"[{self.RPA_NAME}] 所有数据填充任务执行完毕，等待 2 分钟后自动关闭浏览器..."
            )
            await asyncio.sleep(120)

        except Exception as e:
            # 针对用户手动关闭浏览器的情况进行静默处理，并提供友好的日志提示
            err_msg = str(e)
            if (
                "Target page, context or browser has been closed" in err_msg
                or "Browser closed" in err_msg
            ):
                logger.warning(
                    f"[{self.RPA_NAME}] 检测到浏览器窗口已被手动关闭，RPA 流程提前结束。"
                )
            else:
                logger.error(f"[{self.RPA_NAME}] RPA 运行过程中发生异常: {e}")
                raise
        finally:
            await self.close()

        logger.info(f"[{self.RPA_NAME}] RPA 任务流程结束。")

    async def close(self):
        """清理资源"""
        if self.browser_context:
            await self.browser_context.close()
        if self.playwright:
            await self.playwright.stop()
        logger.debug(f"[{self.RPA_NAME}] Playwright 资源已释放")
