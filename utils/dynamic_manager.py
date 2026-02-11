import functools
import importlib
import os
import pkgutil
import threading
from loguru import logger


class BaseDynamicManager:
    """
    通用动态管理器基类
    支持精准延迟加载 (Targeted Lazy Loading)、动态扫描和线程安全
    """

    def __init__(
        self, impl_dir_path: str, module_prefix: str, name_templates: list = None
    ):
        """
        初始化管理器
        :param impl_dir_path: 具体实现类所在的目录绝对路径
        :param module_prefix: 导入时使用的模块前缀 (例如 "crawlers.impl")
        :param name_templates: 命名模板列表，例如 ["{key}_crawler", "{key}"]
        """
        self._impl_dir_path = impl_dir_path
        self._module_prefix = module_prefix
        self._name_templates = name_templates or ["{key}"]
        self._registry = {}
        self._lock = threading.RLock()
        self._fully_discovered = False

    @staticmethod
    def ensure_discovery(func):
        """
        装饰器：在执行某些需要全量信息的函数前，确保已执行全量扫描
        """

        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            self._ensure_fully_discovered()
            return func(self, *args, **kwargs)

        return wrapper

    def register(self, key: str, cls):
        """
        注册类到管理器
        """
        with self._lock:
            self._registry[key.lower()] = cls
            logger.debug(f"[{self.__class__.__name__}] 注册成功: {key}")

    def get_class(self, key: str):
        """
        获取指定 key 对应的类。采用三级查找策略：
        1. 缓存查找
        2. 精准尝试导入 (Targeted Load)
        3. 全目录扫描 (Full Discover)
        """
        if not key:
            return None

        key_lower = key.lower()

        # 1. 第一级：缓存查找
        if key_lower in self._registry:
            return self._registry[key_lower]

        # 2. 第二级：精准尝试导入 (根据约定猜测模块名)
        if not self._fully_discovered:
            with self._lock:
                if key_lower not in self._registry:
                    self._try_targeted_import(key_lower)

        if key_lower in self._registry:
            return self._registry[key_lower]

        # 3. 第三级：如果精准导入没找到，则进行全量扫描（仅执行一次）
        self._ensure_fully_discovered()

        return self._registry.get(key_lower)

    def _try_targeted_import(self, key: str):
        """
        尝试几种可能的模块命名约定进行精准导入
        """
        for template in self._name_templates:
            try:
                mod_name = template.format(key=key)
                module_path = f"{self._module_prefix}.{mod_name}"
                importlib.import_module(module_path)
                # 导入成功后，如果子类有 __init_subclass__ 自动注册逻辑，则 registry 会被填充
                if key in self._registry:
                    return
            except (ImportError, ModuleNotFoundError, KeyError):
                continue

    def _ensure_fully_discovered(self):
        """
        全量扫描目录下的所有模块
        """
        if self._fully_discovered:
            return

        with self._lock:
            if self._fully_discovered:
                return

            logger.info(
                f"[{self.__class__.__name__}] 执行全量模块发现: {self._impl_dir_path}"
            )
            try:
                if os.path.exists(self._impl_dir_path):
                    for _, name, is_pkg in pkgutil.iter_modules([self._impl_dir_path]):
                        if not is_pkg:
                            try:
                                importlib.import_module(f"{self._module_prefix}.{name}")
                            except Exception as e:
                                logger.error(f"加载模块 {name} 失败: {e}")
                self._fully_discovered = True
            except Exception as e:
                logger.error(f"扫描目录 {self._impl_dir_path} 出错: {e}")

    @ensure_discovery
    def get_all_keys(self) -> list:
        """
        获取所有已注册的 key
        """
        return list(self._registry.keys())
