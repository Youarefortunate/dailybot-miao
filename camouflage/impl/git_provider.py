from typing import List
from ..modules.base_camouflage import BaseCamouflage
from ..modules.models import CamouflageItem
from crawlers import CrawlerFactory
from common.config import config
from loguru import logger


class GitCamouflageProvider(BaseCamouflage):
    """
    Git 平台素材提供者实现 (GitLab 等)
    """

    SOURCE_NAME = "git"

    async def fetch_items(self, since: str, until: str) -> List[CamouflageItem]:
        """
        通过爬虫获取代码提交记录作为伪装素材
        """
        items = []
        platforms = config.get_repo_platforms()

        for platform_name in platforms:
            crawler = CrawlerFactory.get_crawler(platform_name)
            if not crawler:
                continue

            repos_config = crawler.get_repos_config()
            for repo in repos_config:
                repo_path = repo["path"]
                try:
                    # 获取该仓库指定日期范围内的原始提交
                    raw_data_list = await crawler.fetch_repo_commits(
                        repo_path,
                        repo.get("branch", "master").split(",")[0].strip(),
                        since,
                        until,
                    )

                    if not raw_data_list:
                        continue

                    for raw in raw_data_list:
                        dataset = crawler._extract_commit_data(raw)
                        # 过滤掉不合规范的提交
                        if crawler._should_skip_commit(dataset):
                            continue

                        # 使用建造者模式构建对象
                        item = (
                            CamouflageItem.builder()
                            .set_id(dataset["id"])
                            .set_source(repo.get("name") or repo_path)
                            .set_content(dataset["message"])
                            .set_platform(platform_name)
                            .set_author(dataset.get("author_name"))
                            .set_created_at(dataset.get("created_at"))
                            .build()
                        )

                        items.append(item)
                except Exception as e:
                    logger.warning(f"[GitProvider] 采集仓库 {repo_path} 失败: {e}")

        return items
