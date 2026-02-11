import urllib.parse
from loguru import logger
from api import apis
from request.hooks.use_request import use_request
from config import config
from crawlers.modules.base_crawler import BaseCrawler


class GitlabCrawler(BaseCrawler):
    """
    GitLab 提交记录爬虫
    """

    PLATFORM_NAME = "gitlab"

    def __init__(self):
        super().__init__()
        self.gitlab_api = use_request(apis.repo_gitlab.get_commits)

    def get_platform_name(self) -> str:
        return "GitLab"

    def get_repos_config(self) -> list:
        return getattr(config, "GITLAB_REPOS", [])

    def fetch_repo_commits(
        self, repo_path: str, branch: str, since: str, until: str
    ) -> list:
        # GitLab API 要求项目路径必须经过 URL 编码
        encoded_path = urllib.parse.quote_plus(repo_path)

        res_data = self.gitlab_api.fetch(
            {
                "project_id": encoded_path,
                "ref_name": branch,
                "since": since,
                "until": until,
            }
        )
        return res_data

    def _extract_commit_data(self, commit: dict) -> dict:
        return {
            "id": commit.get("id"),
            "author_name": commit.get("author_name", ""),
            "author_email": commit.get("author_email", ""),
            "message": commit.get("title", ""),
            "created_at": commit.get("created_at", ""),
        }

    def get_today_commits(self, target_user=None):
        """
        保持向前兼容的接口
        """
        user_to_filter = target_user or getattr(config, "GITLAB_TARGET_USER", None)
        return self.crawl(target_user=user_to_filter)
