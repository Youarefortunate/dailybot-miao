import urllib.parse
from datetime import datetime, timezone, timedelta
from loguru import logger
from api import apis
from request.hooks.use_request import use_request
from config import config


class GitlabCrawler:
    """
    GitLab 提交记录爬虫
    """

    def __init__(self):
        self.gitlab_api = use_request(apis.repo_gitlab.get_commits)

    def get_today_commits(self, target_user=None):
        """
        爬取所有配置仓库中指定用户当天的提交记录
        :param target_user: 指定用户（邮箱或用户名关键词），若不传则使用全局配置
        """
        all_commits = {}

        # 获取今天的开始时间 (假设是东八区北京时间)
        # GitLab API since 参数接受 ISO 8601 格式
        now = datetime.now(timezone(timedelta(hours=8)))
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()

        user_to_filter = target_user or config.TARGET_GIT_USER

        for repo in config.GITLAB_REPOS:
            repo_path = repo["path"]
            branch = repo.get("branch", "master")
            repo_name = repo_path.split("/")[-1]

            logger.info(f"正在爬取仓库: {repo_path} (分支: {branch})")

            # GitLab API 要求项目路径必须经过 URL 编码
            encoded_path = urllib.parse.quote_plus(repo_path)

            try:
                # 调用 GitLab API 获取提交记录
                # 传入 project_id 作为路径参数，其余作为 query params (GET 请求下)
                res_data = self.gitlab_api.fetch(
                    {
                        "project_id": encoded_path,
                        "ref_name": branch,
                        "since": today_start,
                    }
                )

                if not res_data or not isinstance(res_data, list):
                    logger.info(f"仓库 {repo_name} 今日无提交或返回异常")
                    continue

                # 过滤并提取提交记录
                filtered_messages = []
                for commit in res_data:
                    author_name = commit.get("author_name", "")
                    author_email = commit.get("author_email", "")
                    message = commit.get("title", "")  # 获取提交的第一行信息

                    # 如果指定了过滤用户
                    if user_to_filter:
                        u_f = user_to_filter.lower()
                        if (
                            u_f not in author_name.lower()
                            and u_f not in author_email.lower()
                        ):
                            continue

                    filtered_messages.append(message)

                if filtered_messages:
                    all_commits[repo_name] = filtered_messages
                    logger.info(
                        f"仓库 {repo_name} 找到 {len(filtered_messages)} 条符合条件的提交"
                    )

            except Exception as e:
                logger.error(f"爬取仓库 {repo_path} 失败: {e}")

        return all_commits
