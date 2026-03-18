import os
import urllib.parse
from datetime import datetime, timezone, timedelta
from loguru import logger
from api import apis
from request.hooks.use_request import use_request
from common.config import config
from crawlers.modules.base_crawler import BaseCrawler
from utils.path_helper import (
    resolve_path,
    ensure_dir,
    read_file,
    write_file,
    append_file,
    file_exists,
    cleanup_old_files,
)

_TZ = timezone(timedelta(hours=8))


class GitlabCrawler(BaseCrawler):
    """
    GitLab 提交记录爬虫
    """

    CRAWLER_NAME = "gitlab"

    def __init__(self):
        super().__init__()
        self.gitlab_api = use_request(apis.repo_gitlab.get_commits)
        self._extra_report = {"enabled": False}
        self._load_extra_report_config()

    def _load_extra_report_config(self):
        """加载额外报告配置"""
        extra_cfg = self.get_extra_report_config()
        if not extra_cfg.get("enabled", False):
            return

        self._extra_report = {
            "enabled": True,
            "file_path": resolve_path(extra_cfg.get("file_path", "extra_report.md")),
            "log_path": resolve_path(
                extra_cfg.get("log", {}).get("path", "logs/extra_report")
            ),
            "retention_days": extra_cfg.get("log", {}).get("retention", 30),
            "auto_cleanup": extra_cfg.get("auto_cleanup", {}).get("enabled", True),
        }

        logger.info(
            f"📝 [额外报告] GitLab 已启用，文件: {self._extra_report['file_path']}，"
            f"自动清理: {self._extra_report['auto_cleanup']}"
        )

    def get_platform_name(self) -> str:
        return "GitLab"

    def get_sources_config(self) -> list:
        """
        获取 GitLab 的实体（项目仓库）配置列表
        """
        return getattr(config, "GITLAB_REPOS", [])

    async def fetch_activities(self, entity_config: dict, query_params: dict) -> list:
        """
        GitLab 版：支持多分支、API 层过滤及自动分页。

        预期 query_params 包含:
        - since/until (str): ISO 时间范围
        - target_user (str, optional): 目标作者过滤
        """
        repo_path = entity_config.get("path")
        if not repo_path:
            return []

        since = query_params.get("since")
        until = query_params.get("until")
        target_user = query_params.get("target_user")

        # GitLab API 要求项目路径必须经过 URL 编码
        encoded_path = urllib.parse.quote_plus(repo_path)

        # 处理多分支逻辑
        branch_raw = entity_config.get("branch", "master")
        branches = [b.strip() for b in branch_raw.split(",") if b.strip()]

        all_raw_commits = []
        for branch in branches:
            try:
                page = 1
                while True:
                    logger.debug(
                        f"🔍 GitLab [{repo_path}] 分支 {branch} 正在请求第 {page} 页数据..."
                    )
                    # 使用 GitLab API 获取提交记录，带上作者过滤
                    params = {
                        "project_id": encoded_path,
                        "ref_name": branch,
                        "since": since,
                        "until": until,
                        "per_page": 100,
                        "page": page,
                    }
                    if target_user:
                        params["author"] = target_user

                    # 调用获取数据
                    data = await self.gitlab_api.fetch(params)

                    if not data or not isinstance(data, list):
                        break

                    # 补充分支信息
                    for commit in data:
                        commit["_branch_name"] = branch
                    all_raw_commits.extend(data)

                    # 检查分页：如果返回数据不满 per_page，说明到头了
                    if len(data) < 100:
                        break

                    page += 1

            except Exception as e:
                logger.error(f"GitLab [{repo_path}] 分支 {branch} 数据拉取失败: {e}")

        return all_raw_commits

    def extract_activity_data(self, raw_data: dict) -> dict:
        """
        提取 GitLab 活动数据，并将分支名存于 metadata
        """
        return {
            "id": raw_data.get("id"),
            "author_name": raw_data.get("author_name", ""),
            "author_email": raw_data.get("author_email", ""),
            "content": raw_data.get("title", ""),
            "created_at": raw_data.get("created_at", ""),
            "metadata": {"branch": raw_data.get("_branch_name", "master")},
        }

    def format_activity(self, activity_data: dict) -> str:
        """
        定制 GitLab 风格展示：[时间](分支) 内容
        """
        time_display = activity_data.get("time_display", "")
        branch = activity_data.get("metadata", {}).get("branch", "master")
        content = activity_data.get("content", "")

        time_str = f"[{time_display}]" if time_display else ""
        branch_str = f"({branch})"

        return f"{time_str}{branch_str} {content}".strip()

    async def fetch_extra_report(self) -> dict:
        """获取额外报告补充内容"""
        if not self._extra_report["enabled"]:
            return {}

        file_path = self._extra_report["file_path"]
        if not file_exists(file_path):
            return {}

        content = read_file(file_path).strip()
        if not content:
            return {}

        today = datetime.now(_TZ).strftime("%Y-%m-%d")
        logger.info("📝 [额外报告] GitLab 采集到额外补充内容")

        return {today: [content]}

    def archive_extra_report(self):
        """归档并清理额外报告文件"""
        if not self._extra_report["enabled"]:
            return {}

        file_path = self._extra_report["file_path"]
        if not file_exists(file_path):
            return {}

        content = read_file(file_path).strip()
        if not content:
            return {}

        log_path = self._extra_report["log_path"]
        ensure_dir(log_path)

        today = datetime.now(_TZ).strftime("%Y-%m-%d")
        log_file = os.path.join(log_path, f"{today}.md")
        timestamp = datetime.now(_TZ).strftime("%Y-%m-%d %H:%M:%S")

        append_file(log_file, f"\n## 📝 额外信息补充 - {timestamp}\n\n{content}\n\n")

        write_file(file_path, "")

        logger.info(f"📝 [额外报告] GitLab 内容已归档到: {log_file}")

        self._cleanup_old_logs()

    def _cleanup_old_logs(self):
        log_path = self._extra_report["log_path"]
        retention_days = self._extra_report["retention_days"]
        if cleanup_old_files(log_path, ".md", retention_days) > 0:
            logger.info("📝 [额外报告] GitLab 已清理过期日志")

    def get_today_commits(self, target_user=None):
        """
        保持向前兼容的接口
        """
        user_to_filter = target_user or getattr(config, "GITLAB_TARGET_USER", None)
        return self.crawl(target_user=user_to_filter)
