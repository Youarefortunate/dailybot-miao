import os
import yaml
import json
import copy
from typing import Any
import re
from loguru import logger
from dotenv import load_dotenv
from utils.path_helper import get_resource_path, get_app_dir


class Config:
    """
    项目配置类，负责从环境变量和 YAML 文件中读取配置项。
    初始化逻辑在构造函数中自动执行。
    """

    # 项目版本号
    VERSION = "1.1.2"

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
        优先级：外部运行目录下的 .env > 内部打包路径下的 .env (二者选其一，独占模式)。
        """
        # 1. 优先尝试加载程序运行目录下的 .env (用户自定义)
        local_env = os.path.join(get_app_dir(), ".env")
        if os.path.exists(local_env):
            load_dotenv(local_env, override=True)
            return

        # 2. 如果外部没有，则尝试获取打包目录下的 .env (作为模板或默认)
        env_path = get_resource_path(".env")
        if os.path.exists(env_path):
            load_dotenv(env_path, override=True)

    @staticmethod
    def load_yaml_config():
        """
        从 config.yaml 或 config/config.yaml 读取配置。
        支持外部化覆盖，优先级：当前执行目录 > config 子目录 > 内部打包路径 (独占模式)。
        """
        app_dir = get_app_dir()
        local_yaml_direct = os.path.join(app_dir, "config.yaml")  # 与 .env 同级
        local_yaml_subdir = os.path.join(app_dir, "config", "config.yaml")
        yaml_path_internal = get_resource_path(os.path.join("config", "config.yaml"))

        # 确定最终使用的路径 (独占逻辑：只要外部有，就不看内部)
        if os.path.exists(local_yaml_direct):
            target_path = local_yaml_direct
        elif os.path.exists(local_yaml_subdir):
            target_path = local_yaml_subdir
        elif os.path.exists(yaml_path_internal):
            target_path = yaml_path_internal
        else:
            return {}

        try:
            with open(target_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
                return data if isinstance(data, dict) else {}
        except Exception as e:
            logger.warning(f"读取配置失败 ({target_path}): {e}")
            return {}

    def generate_dynamic_attributes(self):
        """
        基于 YAML 自动生成类实例的属性，支持环境覆盖。
        使用 get() 方法确保属性访问与 get() 方法得到的一致。
        """
        # 第一阶段：基于 YAML 配置树生成属性
        for path, yaml_value in self.iter_yaml_paths("", self._yaml_config):
            attr_name = self.path_to_attr_name(path)

            # 使用更强大的 get 方法统一获取合并后的值 (包含 Properties 风格数组解析)
            final_value = self.get(path)

            # 特殊处理 crawler_sources 中的列表解析 (兼容逗号分隔字符串)
            if "crawler_sources" in path and path.endswith(".repos"):
                if isinstance(final_value, str):
                    final_value = self.parse_gitlab_crawler_sources(final_value)

            setattr(self, attr_name, final_value)

        # 第二阶段：补漏扫描纯环境变量配置
        # 针对在 .env 中配了，但在 yaml 里没写的平台源
        for env_k, env_v in os.environ.items():
            env_k_upper = env_k.upper()
            if "REPOS" in env_k_upper:
                # 兼容多种格式：CRAWLER_SOURCES.GITHUB.REPOS[0].PATH, GITHUB_REPOS 等
                parts = env_k_upper.replace(".", "_").replace("[", "_").split("_")
                platform_name = ""
                try:
                    # 寻找 REPOS 所在的索引位置
                    for i, p in enumerate(parts):
                        if p == "REPOS" and i > 0:
                            prev_part = parts[i - 1]
                            if prev_part not in ["SOURCES", "CRAWLER"]:
                                platform_name = prev_part.lower()
                                break
                except:
                    pass

                if platform_name:
                    attr_name = f"{platform_name.upper()}_REPOS"
                    if not hasattr(self, attr_name):
                        res = self.get(f"crawler_sources.{platform_name}.repos")
                        if isinstance(res, str):
                            res = self.parse_gitlab_crawler_sources(res)
                        setattr(self, attr_name, res or [])

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
        同步支持 YAML 定义和环境变量 (含 Properties 风格) 动态发现。
        """
        sources_cfg = self._yaml_config.get("crawler_sources", {})
        platforms = set(sources_cfg.keys()) if isinstance(sources_cfg, dict) else set()

        # 扫描环境变量中的动态平台
        for env_key in os.environ.keys():
            env_key_upper = env_key.upper()
            if "REPOS" in env_key_upper:
                # 兼容多种格式：CRAWLER_SOURCES.GITHUB.REPOS[0].PATH, GITHUB_REPOS 等
                parts = env_key_upper.replace(".", "_").replace("[", "_").split("_")
                try:
                    # 寻找 REPOS 所在的索引
                    for i, p in enumerate(parts):
                        if p == "REPOS" and i > 0:
                            prev_part = parts[i - 1]
                            if prev_part not in ["SOURCES", "CRAWLER"]:
                                platforms.add(prev_part.lower())
                except:
                    pass

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

    def get_provider_for_model(self, model_id: str) -> str:
        """
        根据具体的模型 ID 遍历 models 配置，找到并返回挂载该模型的提供商
        名称 (例如 doubao)。如果未找到，则返回 None。
        """
        models_cfg = self.get("models", {})
        if not isinstance(models_cfg, dict):
            return None

        for provider_name, provider_cfg in models_cfg.items():
            if isinstance(provider_cfg, dict):
                provider_models = provider_cfg.get("models", [])
                if isinstance(provider_models, list) and model_id in provider_models:
                    return provider_name
                elif provider_cfg.get("model") == model_id:
                    return provider_name

        return None

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

        # 2. 构造环境变量对应的名（剥离分类前缀 + 完整路径）
        normalized_path = ".".join(normalized_keys)
        env_base_key = self.path_to_env_key(normalized_path)
        attr_name_key = self.path_to_attr_name(normalized_path)
        full_env_key = normalized_path.upper()  # 不剥离前缀的完整路径

        # 3. 环境变量优先级最高：精确匹配 (不区分大小写)
        for env_key, env_val in os.environ.items():
            env_k_up = env_key.upper()
            if env_k_up in (env_base_key, attr_name_key.upper(), full_env_key):
                return self._parse_env_value(env_val)
            # 4. 如果基础值是字典/列表，或者环境中有前缀匹配项（支持动态注入整个分支）
        prefix_dot = f"{env_base_key}."
        prefix_under = f"{attr_name_key}_"
        full_prefix_dot = f"{full_env_key}."
        prefix_bracket = f"{env_base_key}["
        full_prefix_bracket = f"{full_env_key}["
        full_env_under = full_env_key.replace(".", "_")

        # 增加各种风格的前缀识别 (点号风格、下划线风格、属性名风格、索引风格)
        prefixes = [
            prefix_dot,
            full_prefix_dot,
            prefix_under,
            f"{full_env_under}_",
            prefix_bracket,
            full_prefix_bracket,
            f"{attr_name_key}[",
            f"{full_env_under}[",
        ]

        has_env_prefix = any(
            k.upper().startswith(p) for p in prefixes for k in os.environ.keys()
        )

        if isinstance(base_val, (dict, list)) or (base_val is None and has_env_prefix):
            # 记录待注入的任务
            injection_tasks = []
            final_data_type = list if isinstance(base_val, list) else dict

            # 扫描所有环境变量进行合并
            for env_key, env_val in os.environ.items():
                env_key_upper = env_key.upper()
                remaining = ""

                # 尝试匹配并提取剩余路径
                for p in sorted(prefixes, key=len, reverse=True):
                    if env_key_upper.startswith(p):
                        # 如果前缀是 [ 结尾，保留 [
                        if p.endswith("["):
                            remaining = env_key_upper[len(p) - 1 :]
                        else:
                            remaining = env_key_upper[len(p) :]

                        # 简单转换下划线风格
                        if p == prefix_under or p == f"{full_env_under}_":
                            remaining = remaining.replace("_", ".")

                        # 启发式确定数据类型 (针对从 None 开始的情况)
                        if base_val is None and remaining.startswith("["):
                            final_data_type = list
                        break

                if remaining:
                    injection_tasks.append((remaining, env_val))

            # 初始化容器
            data = (
                copy.deepcopy(base_val) if base_val is not None else final_data_type()
            )

            # 执行注入
            for rem, val in injection_tasks:
                self._inject_env_value(data, rem, val)

            final_data = data
        else:
            final_data = base_val

        # 递归清理所有配置项中的空占位符 (None, "", {}, [])，确保无实质内容的项不会被采用
        cleaned_data = self._clean_empty_values(final_data)

        # 如果清理后结果为空，则回退到提供的默认值
        return cleaned_data if cleaned_data is not None else default

    def _inject_env_value(self, data: Any, env_path: str, value: Any):
        """
        递归注入环境变量值。env_path 是大写的点号路径。
        支持 key[index] 或 [index] 格式。
        """
        parts = env_path.split(".")

        # 1. 识别并提取数组索引，例如 REPOS[0] 或 [0]
        match = re.match(r"^([^\[]+)?\[(\d+)\]$", parts[0])
        if match:
            key_name = match.group(1)
            index = int(match.group(2))

            if key_name:
                # 处理字典中的列表，如 REPOS[0]
                if not isinstance(data, dict):
                    return
                key = key_name.lower()
                if key not in data or not isinstance(data[key], list):
                    data[key] = []
                target_list = data[key]
            else:
                # 处理直接是列表的情况，如 [0]
                if not isinstance(data, list):
                    return
                target_list = data

            # 自动扩容列表
            while len(target_list) <= index:
                target_list.append({})

            if len(parts) == 1:
                target_list[index] = self._parse_env_value(value)
            else:
                self._inject_env_value(target_list[index], ".".join(parts[1:]), value)
            return

        # 2. 原有的字典处理逻辑
        if not isinstance(data, dict):
            return

        current_data_keys = {k.upper(): k for k in data.keys()}
        for i in range(len(parts), 0, -1):
            key_upper = ".".join(parts[:i])
            if key_upper in current_data_keys:
                actual_key = current_data_keys[key_upper]
                if i == len(parts):
                    data[actual_key] = self._parse_env_value(value)
                    return
                elif isinstance(data[actual_key], dict):
                    self._inject_env_value(data[actual_key], ".".join(parts[i:]), value)
                    return

        # 3. 兜底逻辑
        target = data
        for pk in parts[:-1]:
            pk_lower = pk.lower()
            if pk_lower not in target or not isinstance(target[pk_lower], dict):
                target[pk_lower] = {}
            target = target[pk_lower]
        target[parts[-1].lower()] = self._parse_env_value(value)

    def _clean_empty_values(self, data: Any) -> Any:
        """
        递归清理配置中的空值（None, "", {}, []）。
        保留有意义的 Falsy 值（如 0, 0.0, False）。
        """
        # 显式定义什么是“空”：None、空字符、空字典、空列表
        if data is None or data == "" or data == {} or data == []:
            return None

        if isinstance(data, dict):
            cleaned = {k: self._clean_empty_values(v) for k, v in data.items()}
            # 仅保留非 None 的键值对
            result = {k: v for k, v in cleaned.items() if v is not None}
            return result if result else None
        elif isinstance(data, list):
            cleaned = [self._clean_empty_values(item) for item in data]
            # 仅保留非 None 的项
            result = [i for i in cleaned if i is not None]
            return result if result else None

        return data

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
