import os
import yaml
from loguru import logger
from dotenv import load_dotenv


def _load_yaml_config():
    """
    从 config/config.yaml 读取配置；如果不存在或解析失败，则返回空字典。
    """
    if yaml is None:
        return {}

    base_dir = os.path.dirname(os.path.abspath(__file__))
    yaml_path = os.path.join(base_dir, "config", "config.yaml")

    if not os.path.exists(yaml_path):
        return {}

    try:
        with open(yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
            if not isinstance(data, dict):
                return {}
            return data
    except Exception as e:
        logger.warning(f"读取 config/config.yaml 失败，将回退到环境变量配置: {e}")
        return {}


_YAML_CONFIG = _load_yaml_config()


def _from_yaml(path, default=None):
    """
    从嵌套的 YAML 配置中安全取值，例如 path='gitlab.token'
    """
    if not _YAML_CONFIG:
        return default

    parts = path.split(".")
    cur = _YAML_CONFIG
    for p in parts:
        if not isinstance(cur, dict) or p not in cur:
            return default
        cur = cur[p]
    return cur


def _iter_yaml_paths(prefix, data):
    """
    将嵌套的 YAML 配置拍平成 (path, value) 列表。
    例如: {"gitlab": {"token": "xxx"}} -> [("gitlab.token", "xxx")]
    """
    if isinstance(data, dict):
        for k, v in data.items():
            new_prefix = f"{prefix}.{k}" if prefix else k
            # 继续向下遍历
            yield from _iter_yaml_paths(new_prefix, v)
    else:
        if prefix:
            yield prefix, data


def _path_to_env_key(path: str) -> str:
    """
    将 YAML 路径转换为环境变量风格的大写常量名。
    对于分类键（platforms/models/repos）下的路径，跳过顶层前缀。
    例如: 'platforms.feishu.base_url' -> 'FEISHU_BASE_URL'
         'log.level' -> 'LOG_LEVEL'
    """
    # 需要跳过的顶层分类前缀
    _CATEGORY_KEYS = {"platforms", "models", "repos"}

    parts = path.split(".")
    if len(parts) > 1 and parts[0] in _CATEGORY_KEYS:
        parts = parts[1:]  # 跳过第一层分类前缀

    return "_".join(parts).upper()


def _parse_gitlab_repos(repos_str: str):
    """
    解析 GITLAB_REPOS 环境变量字符串 (格式: path:branch,path:branch,...)
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


# 加载 .env 文件中的环境变量（作为 YAML 之外的兜底）
load_dotenv()


class Config:
    """
    项目配置类，负责从环境变量中读取配置项
    """

    # 应用租户token（通常由代码动态获取）
    APP_TENANT_TOKEN = os.getenv("APP_TENANT_TOKEN", "")

    @classmethod
    def get_repo_platforms(cls):
        """
        获取 config.yaml 中配置的所有仓库平台名称
        """
        repos_cfg = _YAML_CONFIG.get("repos", {})
        if not isinstance(repos_cfg, dict):
            return []
        return list(repos_cfg.keys())

    @classmethod
    def get_platform(cls, platform_name: str) -> dict:
        """
        根据平台名称获取其在 platforms 分类下的所有配置
        """
        platforms_cfg = _YAML_CONFIG.get("platforms", {})
        platform_data = platforms_cfg.get(platform_name)
        if isinstance(platform_data, dict):
            return platform_data
        return {}

    @classmethod
    def validate(cls):
        """
        验证必要的配置项是否存在
        """
        required_fields = [
            "FEISHU_APP_ID",
            "FEISHU_APP_SECRET",
            "DOUBAO_API_KEY",
            "FEISHU_TARGET_CHAT_ID",
            "FEISHU_OAUTH_REDIRECT_URI",
            "FEISHU_TASKLIST_GUID",
            "FEISHU_BASE_URL",
            "GITLAB_TOKEN",
            "GITLAB_BASE_URL",
        ]
        missing = [f for f in required_fields if not getattr(cls, f, None)]
        if missing:
            logger.warning(f"缺少必要的配置项: {', '.join(missing)}")
            return False
        return True


config = Config()

# === 基于 YAML 自动生成全大写常量名 ===
# 分类键（platforms/models/repos）会被跳过
# 例如: platforms.feishu.base_url -> FEISHU_BASE_URL
for _path, _yaml_value in _iter_yaml_paths("", _YAML_CONFIG):
    # gitlab.repos 特殊处理（现在路径变为 repos.gitlab.repos）
    if _path == "repos.gitlab.repos":
        _env_raw = os.getenv("GITLAB_REPOS")
        if _env_raw:
            Config.GITLAB_REPOS = _parse_gitlab_repos(_env_raw)
        else:
            Config.GITLAB_REPOS = _yaml_value or []
        continue

    # 通用规则：路径转常量名（自动跳过分类前缀）
    _attr_name = _path_to_env_key(_path)
    _env_val = os.getenv(_attr_name)

    # 环境变量优先生效，其次 YAML
    _final_value = _env_val if _env_val is not None else _yaml_value

    setattr(Config, _attr_name, _final_value)
