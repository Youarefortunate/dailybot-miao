import os
from loguru import logger
from dotenv import load_dotenv

# 加载 .env 文件中的环境变量
load_dotenv()


class Config:
    """
    项目配置类，负责从环境变量中读取配置项
    """

    # 飞书应用的 App ID
    FEISHU_APP_ID = os.getenv("FEISHU_APP_ID", "")
    # 飞书应用的 App Secret
    FEISHU_APP_SECRET = os.getenv("FEISHU_APP_SECRET", "")
    FEISHU_BOT_TOKEN = os.getenv("FEISHU_BOT_TOKEN", "")
    # 豆包大模型配置
    DOUBAO_API_KEY = os.getenv("DOUBAO_API_KEY", "")
    DOUBAO_BASE_URL = os.getenv("DOUBAO_BASE_URL", "")
    DOUBAO_MODEL = os.getenv("DOUBAO_MODEL", "")
    # 目标群聊ID
    TARGET_CHAT_ID = os.getenv("TARGET_CHAT_ID", "")
    # 每日站会的推送时间 (格式为 HH:mm)
    STANDUP_TIME = os.getenv("STANDUP_TIME", "09:00")
    # 时区
    TIMEZONE = os.getenv("TIMEZONE", "Asia/Shanghai")
    # 日志级别
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    # 任务清单
    TASKLIST_GUID = os.getenv("TASKLIST_GUID", "")
    # 授权重定向URI
    OAUTH_REDIRECT_URI = os.getenv(
        "OAUTH_REDIRECT_URI", "http://127.0.0.1:8001/callback"
    )
    # 应用租户token（通常由代码动态获取）
    APP_TENANT_TOKEN = os.getenv("APP_TENANT_TOKEN", "")

    # 企业微信配置
    WECOM_CORP_ID = os.getenv("WECOM_CORP_ID", "")
    WECOM_CORP_SECRET = os.getenv("WECOM_CORP_SECRET", "")

    # GitLab 配置
    GITLAB_TOKEN = os.getenv("GITLAB_TOKEN", "")
    GITLAB_BASE_URL = os.getenv("GITLAB_BASE_URL", "")

    @staticmethod
    def _parse_gitlab_repos(repos_str):
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

    # 需要爬取的仓库列表 (从 .env 中 GITLAB_REPOS 解析)
    GITLAB_REPOS = _parse_gitlab_repos.__func__(os.getenv("GITLAB_REPOS", ""))
    # 指定爬取的 Git 用户邮箱或用户名 (优先使用邮箱)
    TARGET_GIT_USER = os.getenv("TARGET_GIT_USER", "")

    # 请求库默认配置
    DEFAULT_PLATFORM = os.getenv("DEFAULT_PLATFORM", "feishu")
    DEFAULT_BASE_URL = os.getenv("DEFAULT_BASE_URL", "https://open.feishu.cn")

    @classmethod
    def validate(cls):
        """
        验证必要的配置项是否存在
        """
        required_fields = [
            "FEISHU_APP_ID",
            "FEISHU_APP_SECRET",
            "DOUBAO_API_KEY",
            "TARGET_CHAT_ID",
            "GITLAB_TOKEN",
        ]
        missing = [f for f in required_fields if not getattr(cls, f)]
        if missing:
            logger.warning(f"缺少必要的配置项: {', '.join(missing)}")
            return False
        return True


config = Config()
