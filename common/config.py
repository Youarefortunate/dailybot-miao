import os
import yaml
import json
from loguru import logger
from dotenv import load_dotenv


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
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        env_path = os.path.join(base_dir, ".env")
        if os.path.exists(env_path):
            load_dotenv(env_path, override=True)

    @staticmethod
    def load_yaml_config():
        """
        从 config/config.yaml 读取配置。
        """
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        yaml_path = os.path.join(base_dir, "config", "config.yaml")

        if not os.path.exists(yaml_path):
            return {}

        try:
            with open(yaml_path, "r", encoding="utf-8") as f:
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
            # 特殊处理 gitlab.repos
            if path == "repos.gitlab.repos":
                env_raw = os.getenv("GITLAB_REPOS")
                if env_raw:
                    self.GITLAB_REPOS = self.parse_gitlab_repos(env_raw)
                else:
                    self.GITLAB_REPOS = yaml_value or []
                continue

            attr_name = self.path_to_env_key(path)
            env_val = os.getenv(attr_name)
            final_value = env_val if env_val is not None else yaml_value
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
        _CATEGORY_KEYS = {"platforms", "models", "repos"}
        parts = path.split(".")
        if len(parts) > 1 and parts[0] in _CATEGORY_KEYS:
            parts = parts[1:]
        return "_".join(parts).upper()

    @staticmethod
    def parse_gitlab_repos(repos_str: str):
        """
        解析 GITLAB_REPOS 字符串。
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
        核心合并逻辑。
        """
        base_cfg = self._yaml_config.get(category, {}).get(name, {})
        if not isinstance(base_cfg, dict):
            base_cfg = {}

        data = base_cfg.copy()
        prefix = f"{name.upper()}_"
        for env_key, env_val in os.environ.items():
            if env_key.startswith(prefix):
                config_key = env_key[len(prefix) :].lower()
                final_val = env_val
                if isinstance(env_val, str) and (
                    env_val.strip().startswith("{") or env_val.strip().startswith("[")
                ):
                    try:
                        final_val = json.loads(env_val)
                    except:
                        pass
                data[config_key] = final_val
        return data

    def get_repo_platforms(self) -> list:
        """
        获取配置的所有仓库平台名称。
        """
        repos_cfg = self._yaml_config.get("repos", {})
        platforms = set(repos_cfg.keys()) if isinstance(repos_cfg, dict) else set()

        for env_key in os.environ.keys():
            if env_key.endswith("_REPOS"):
                platform_name = env_key.replace("_REPOS", "").lower()
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


# 导出全局单例配置对象，实例化时会自动触发初始化
config = Config()
