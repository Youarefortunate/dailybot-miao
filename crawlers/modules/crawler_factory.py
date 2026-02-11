from .crawler_manager import crawler_manager


class CrawlerFactory:
    """
    爬虫工厂类，负责根据平台名称创建对应的爬虫实例。
    """

    @classmethod
    def get_crawler(cls, platform_name: str):
        """
        根据平台名称获取爬虫实例
        """
        crawler_cls = crawler_manager.get_crawler_class(platform_name)
        if not crawler_cls:
            return None
        return crawler_cls()

    @classmethod
    def get_all_supported_platforms(cls):
        """
        获取所有已注册并实现的平台
        """
        return crawler_manager.get_registered_platforms()
