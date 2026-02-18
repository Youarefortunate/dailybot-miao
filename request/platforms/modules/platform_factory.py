from loguru import logger
from common.config import config
from .base_platform import BasePlatform


class PlatformFactory:
    """
    平台工厂：从配置中动态生成通用平台实例。
    当 PlatformManager 找不到已注册的专用平台类时，
    由本工厂尝试从 config.yaml 的 models 配置节点中读取信息并构建标准平台实例。
    """

    # OpenAI 兼容的响应模板
    RESPONSE_TEMPLATE = {"code": None, "data": None, "message": "message"}

    @staticmethod
    def create(platform_name, config_override=None):
        """
        工厂入口：尝试从配置中动态创建平台实例。
        :param platform_name: 平台名称（对应 config.yaml 中 models 下的 key）
        :param config_override: 外部传入的覆盖配置
        :return: BasePlatform 实例 或 None
        """
        model_cfg = config.get_model(platform_name)
        if not model_cfg:
            return None

        base_url = model_cfg.get("base_url")
        api_key = model_cfg.get("api_key")

        if not base_url:
            logger.debug(
                f"[PlatformFactory] 跳过 '{platform_name}'：缺少 base_url 配置"
            )
            return None

        # 构建初始化配置
        init_config = {
            "name": platform_name,
            "baseURL": base_url,
        }

        # 注入 API Key 作为 token
        if api_key:
            init_config["token"] = api_key

        # 合并外部覆盖配置（保留调用方传入的 baseURL / token 等优先级）
        if config_override and isinstance(config_override, dict):
            for key, value in config_override.items():
                init_config.setdefault(key, value)

        # 创建 BasePlatform 实例并设置 OpenAI 兼容的响应模板
        instance = BasePlatform(init_config)
        instance.PLATFORM_NAME = platform_name
        instance.response_template = PlatformFactory.RESPONSE_TEMPLATE.copy()

        logger.info(
            f"[PlatformFactory] 已动态生成平台实例: {platform_name} (baseURL={base_url})"
        )

        return instance
