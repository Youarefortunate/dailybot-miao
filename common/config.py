import os
import yaml
import json
from typing import Any
from loguru import logger
from dotenv import load_dotenv
from utils.path_helper import get_resource_path, get_app_dir


class Config:
    """
    项目配置类，负责从环境变量和 YAML 文件中读取配置项。
    初始化逻辑在构造函数中自动执行。
    """

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
        """
        for path, yaml_value in self.iter_yaml_paths("", self._yaml_config):
            # 特殊处理 crawler_sources.gitlab.repos
            if path == "crawler_sources.gitlab.repos":
                env_raw = os.getenv("GITLAB_CRAWLER_SOURCES")
                if env_raw:
                    self.GITLAB_CRAWLER_SOURCES = self.parse_gitlab_crawler_sources(
                        env_raw
                    )
                else:
                    self.GITLAB_CRAWLER_SOURCES = yaml_value or []
                continue

            attr_name = self.path_to_env_key(path)
            env_val = os.getenv(attr_name)
            if env_val is not None:
                # 识别并解析环境变量
                final_value = env_val
                if isinstance(env_val, str):
                    env_val_strip = env_val.strip()
                    # 仅支持 JSON 解析 (必须以 { 或 [ 开头)
                    if env_val_strip.startswith(("{", "[")):
                        try:
                            final_value = json.loads(env_val_strip)
                        except Exception:
                            pass
            else:
                final_value = yaml_value
            setattr(self, attr_name, final_value)

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

    @staticmethod
    def path_to_env_key(path: str) -> str:
        """
        路径转环境变量名。
        """
        _CATEGORY_KEYS = {"platforms", "models", "crawler_sources"}
        parts = path.split(".")
        if len(parts) > 1 and parts[0] in _CATEGORY_KEYS:
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

    def get_merged_config(self, category: str, name: str) -> dict:
        """
        核心合并逻辑 (现已完全复用 get() 方法的链式取值与环境变量合并机制)。
        """
        path = f"{category}.{name}"
        res = self.get(path, default={})
        return res if isinstance(res, dict) else {}

    def get_crawler_source_platforms(self) -> list:
        """
        获取配置的所有采集源平台名称。
        """
        sources_cfg = self._yaml_config.get("crawler_sources", {})
        platforms = set(sources_cfg.keys()) if isinstance(sources_cfg, dict) else set()

        for env_key in os.environ.keys():
            if env_key.endswith("_CRAWLER_SOURCES"):
                platform_name = env_key.replace("_CRAWLER_SOURCES", "").lower()
                platforms.add(platform_name)

        return sorted(list(platforms))

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
        示例：get("redis.host") 或 get("platforms.feishu.bot_token")
        """
        # 第一步：查看是否被单项环境变量/动态属性作为基础标量完全覆盖
        env_attr = self.path_to_env_key(path)
        if hasattr(self, env_attr):
            val = getattr(self, env_attr)
            if not isinstance(val, dict):
                return val

        # 第二步：在字典树中深层查询基础配置
        keys = path.split(".")
        current = self._yaml_config

        found = True
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                found = False
                break

        # 如果没找到，尝试补全前缀逻辑 (免前缀寻址)
        if not found:
            _CATEGORY_KEYS = ["platforms", "models", "crawler_sources"]
            for cat in _CATEGORY_KEYS:
                # 尝试补全分类前缀，例如 "wecom" -> "platforms.wecom"
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
                    break

        base_val = current if found else default

        # 第三步：如果查出来的是字典，还需要进行类似 get_merged_config 的环境变量前缀覆盖探测
        if isinstance(base_val, dict):
            # 将基准字典深层拷贝防止污染原 yaml
            data = base_val.copy()
            # 环境变量前缀格式处理，如 path="models.doubao" 时对应的前缀为 "DOUBAO_"
            # 如果 path 长于 1，则以前最后一段为前缀进行探测比较贴合项目现存设定。
            last_key = keys[-1]
            prefix = f"{last_key.upper()}_"
            for env_key, env_val in os.environ.items():
                if env_key.startswith(prefix):
                    config_key = env_key[len(prefix) :].lower()
                    final_val = env_val
                    if isinstance(env_val, str) and (
                        env_val.strip().startswith("{")
                        or env_val.strip().startswith("[")
                    ):
                        try:
                            final_val = json.loads(env_val)
                        except:
                            pass
                    data[config_key] = final_val
            return data

        return base_val


# 导出全局单例配置对象，实例化时会自动触发初始化
config = Config()
