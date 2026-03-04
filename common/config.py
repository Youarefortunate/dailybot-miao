import os
import yaml
import json
import copy
from typing import Any
from loguru import logger
from dotenv import load_dotenv
from utils.path_helper import get_resource_path, get_app_dir


class Config:
    """
    项目配置类，负责从环境变量和 YAML 文件中读取配置项。
    初始化逻辑在构造函数中自动执行。
    """

    # 映射环境变量时自动忽略的顶层 YAML 键名
    IGNORE_CATEGORY_KEYS = ["platforms", "models", "crawler_sources"]

    def __init__(self):
        """
        构造时自动加载 .env 和 YAML 配置，并动态生成属性。
        """
        # 基础私有变量
        self._yaml_config = {}
        # 初始加载
        self.reload()

        # 其他常量
        self.APP_TENANT_TOKEN = os.getenv("APP_TENANT_TOKEN", "")

    def reload(self):
        """
        重新从 .env 和 YAML 加载配置，并刷新动态属性。
        """
        self.setup_env()
        self._yaml_config = self.load_yaml_config()
        self.generate_dynamic_attributes()

    def setup_env(self):
        """
        加载 .env 文件中的环境变量。
        """

        # 先尝试获取打包目录下的 .env (作为模板或默认)
        env_path = get_resource_path(".env")
        if os.path.exists(env_path):
            load_dotenv(env_path, override=True)

        # 再尝试加载程序运行目录下的 .env (用户自定义)
        local_env = os.path.join(get_app_dir(), ".env")
        if os.path.exists(local_env):
            load_dotenv(local_env, override=True)

    @staticmethod
    def load_yaml_config():
        """
        从 config.yaml 或 config/config.yaml 读取配置。
        支持外部化覆盖，优先级：当前执行目录 > config 子目录 > 内部打包路径。
        """

        # 1. 内部打包路径 (默认逻辑)
        yaml_path = get_resource_path(os.path.join("config", "config.yaml"))

        # 2. 外部运行目录路径 (允许用户外部覆盖)
        app_dir = get_app_dir()
        local_yaml_direct = os.path.join(app_dir, "config.yaml")  # 与 .env 同级
        local_yaml_subdir = os.path.join(app_dir, "config", "config.yaml")

        # 确定最终使用的路径
        if os.path.exists(local_yaml_direct):
            target_path = local_yaml_direct
        elif os.path.exists(local_yaml_subdir):
            target_path = local_yaml_subdir
        else:
            target_path = yaml_path

        if not os.path.exists(target_path):
            return {}

        try:
            with open(target_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
                return data if isinstance(data, dict) else {}
        except Exception as e:
            logger.warning(f"读取 config/config.yaml 失败: {e}")
            return {}

    def generate_dynamic_attributes(self):
        """
        基于 YAML 自动生成类实例的属性，支持环境覆盖。
        同时会扫描环境变量中未在 YAML 中声明的独立配置 (例如 _CRAWLER_SOURCES)。
        """
        # 第一阶段：基于 YAML 配置树生成属性
        for path, yaml_value in self.iter_yaml_paths("", self._yaml_config):
            attr_name = self.path_to_attr_name(path)

            # 使用更强大的 get 方法统一获取合并后的值 (它自带了环境变量探测逻辑)
            # 但对于普通叶子节点，这里可以简化处理，因为 get 也需要在树上寻找。
            # 不过最稳妥的是：统一调用 _get_value_for_attr(path, attr_name, yaml_value)

            env_key = self.path_to_env_key(path)
            env_val = os.getenv(env_key)

            # 特别兼容传统下划线命名 (例如 GITLAB_CRAWLER_SOURCES)
            if env_val is None:
                env_val = os.getenv(attr_name)

            # 特殊处理 crawler_sources 中的列表解析 (统一点号规范)
            if "crawler_sources" in path and path.endswith(".repos"):
                if env_val:
                    setattr(self, attr_name, self.parse_gitlab_crawler_sources(env_val))
                else:
                    setattr(self, attr_name, yaml_value or [])
                continue

            if env_val is not None:
                final_value = self._parse_env_value(env_val)
            else:
                final_value = yaml_value
            setattr(self, attr_name, final_value)

        # 第二阶段：补漏扫描纯环境变量配置
        # 针对在 .env 中配了，但在 yaml 里没写的平台源
        for env_k, env_v in os.environ.items():
            env_k_upper = env_k.upper()
            if env_k_upper.endswith("_REPOS"):
                # 如果这个属性还没被设置过，基于环境变量为其创建
                if not hasattr(self, env_k_upper):
                    setattr(self, env_k_upper, self.parse_gitlab_crawler_sources(env_v))

    def iter_yaml_paths(self, prefix, data):
        """
        递归遍历 YAML 路径。
        """
        if isinstance(data, dict):
            for k, v in data.items():
                new_prefix = f"{prefix}.{k}" if prefix else k
                yield from self.iter_yaml_paths(new_prefix, v)
        else:
            if prefix:
                yield prefix, data

    @classmethod
    def path_to_env_key(cls, path: str) -> str:
        """
        路径转环境变量名。
        """
        parts = path.split(".")
        if len(parts) > 1 and parts[0] in cls.IGNORE_CATEGORY_KEYS:
            parts = parts[1:]

        return ".".join(parts).upper()

    @classmethod
    def path_to_attr_name(cls, path: str) -> str:
        """
        路径转 Python 属性名 (使用下划线)。
        """
        parts = path.split(".")

        if len(parts) > 1 and parts[0] in cls.IGNORE_CATEGORY_KEYS:
            parts = parts[1:]

        return "_".join(parts).upper()

    @staticmethod
    def parse_gitlab_crawler_sources(repos_str: str):
        """
        解析 GITLAB_CRAWLER_SOURCES 字符串。
        """
        if not repos_str:
            return []
        repos = []
        for item in repos_str.split(","):
            item = item.strip()
            if ":" in item:
                path, branch = item.rsplit(":", 1)
                repos.append({"path": path.strip(), "branch": branch.strip()})
            else:
                repos.append({"path": item, "branch": "master"})
        return repos

    def get_crawler_source_platforms(self) -> list:
        """
        获取配置的所有采集源平台名称。
        """
        sources_cfg = self._yaml_config.get("crawler_sources", {})
        platforms = set(sources_cfg.keys()) if isinstance(sources_cfg, dict) else set()

        for env_key in os.environ.keys():
            if env_key.endswith("_REPOS"):
                platform_name = env_key.replace("_REPOS", "").lower()
                platforms.add(platform_name)

        return sorted(list(platforms))

    def get_merged_config(self, category: str, name: str) -> dict:
        """
        核心合并逻辑 (现已完全复用 get() 方法的链式取值与环境变量合并机制)。
        """
        path = f"{category}.{name}"
        res = self.get(path, default={})
        return res if isinstance(res, dict) else {}

    def get_platform(self, platform_name: str) -> dict:
        """
        根据平台名称获取配置。
        """
        return self.get_merged_config("platforms", platform_name)

    def get_model(self, model_key: str) -> dict:
        """
        根据模型 key 获取配置。
        """
        return self.get_merged_config("models", model_key)

    def get(self, path: str, default: Any = None) -> Any:
        """
        按路径 (基于 . 分隔) 动态获取 YAML 配置，并用环境变量覆盖 (若存在)。
        支持 .properties 风格的点号分隔环境变量，例如 WECOM.RPA.FORM_URL
        """
        # 1. 寻找配置路径的基准值并规范化路径
        keys = path.split(".")
        current = self._yaml_config
        found = True
        normalized_keys = keys

        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                found = False
                break

        if not found:
            for cat in self.IGNORE_CATEGORY_KEYS:
                temp_keys = [cat] + keys
                current = self._yaml_config
                found_cat = True
                for key in temp_keys:
                    if isinstance(current, dict) and key in current:
                        current = current[key]
                    else:
                        found_cat = False
                        break
                if found_cat:
                    found = True
                    normalized_keys = temp_keys
                    break

        base_val = current if found else default

        # 2. 构造环境变量对应的名（剥离分类前缀）
        # path="wecom" -> env_base_key="WECOM"
        # path="wecom.rpa" -> env_base_key="WECOM.RPA"
        env_base_key = self.path_to_env_key(".".join(normalized_keys))
        attr_name_key = self.path_to_attr_name(".".join(normalized_keys))

        # 3. 环境变量优先级最高：精确匹配 (不区分大小写)
        for env_key, env_val in os.environ.items():
            env_k_up = env_key.upper()
            if env_k_up == env_base_key or env_k_up == attr_name_key.upper():
                return self._parse_env_value(env_val)

        # 4. 如果基础值是字典，或者基础值不存在但环境中有前缀匹配项（支持动态注入整个字典分支）
        prefix_dot = f"{env_base_key}."
        prefix_under = f"{attr_name_key}_"

        has_env_prefix = any(
            k.upper().startswith(prefix_dot) or k.upper().startswith(prefix_under)
            for k in os.environ.keys()
        )

        if isinstance(base_val, dict) or (base_val is None and has_env_prefix):
            data = copy.deepcopy(base_val) if isinstance(base_val, dict) else {}

            # 扫描所有环境变量进行合并
            for env_key, env_val in os.environ.items():
                env_key_upper = env_key.upper()
                remaining = ""
                # 尝试点号前缀匹配 (WECOM.RPA.FORM_URL)
                if env_key_upper.startswith(prefix_dot):
                    remaining = env_key_upper[len(prefix_dot) :]
                # 尝试下划线前缀匹配 (WECOM_RPA_FORM_URL)
                elif env_key_upper.startswith(prefix_under):
                    # 将后面的下划线尝试转回点号层级以应用到字典
                    # 这里是一个折中，主要为了兼顾在字典装配时使用旧式环境变量
                    remaining = env_key_upper[len(prefix_under) :].replace("_", ".")

                if remaining:
                    self._inject_env_value(data, remaining, env_val)
            return data

        return base_val

    def _inject_env_value(self, data: dict, env_path: str, value: Any):
        """
        递归注入环境变量值。env_path 是大写的点号路径。
        """
        parts = env_path.split(".")

        # 优先匹配现有键名 (不区分大小写)
        current_data_keys = {k.upper(): k for k in data.keys()}

        # 尝试匹配现有键 (贪婪匹配)
        for i in range(len(parts), 0, -1):
            key_upper = ".".join(parts[:i])
            if key_upper in current_data_keys:
                actual_key = current_data_keys[key_upper]
                if i == len(parts):
                    # 叶子节点
                    data[actual_key] = self._parse_env_value(value)
                    return
                elif isinstance(data[actual_key], dict):
                    # 中间层
                    self._inject_env_value(data[actual_key], ".".join(parts[i:]), value)
                    return

        # 兜底：创建新路径
        target = data
        for pk in parts[:-1]:
            pk_lower = pk.lower()
            if pk_lower not in target or not isinstance(target[pk_lower], dict):
                target[pk_lower] = {}
            target = target[pk_lower]
        target[parts[-1].lower()] = self._parse_env_value(value)

    @staticmethod
    def _parse_env_value(val: Any) -> Any:
        """尝试自动解析 JSON 字符串（数组或对象）"""
        if isinstance(val, str):
            val_s = val.strip()
            if val_s.startswith(("{", "[")):
                try:
                    return json.loads(val_s)
                except:
                    pass
        return val


# 导出全局单例配置对象，实例化时会自动触发初始化
config = Config()
