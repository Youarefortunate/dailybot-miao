from config import config


def get_wecom_auth_api():
    """
    企业微信鉴权模块 API 定义
    主要用于获取应用级 access_token。
    """
    return {
        "platform": "wecom",
        # 获取企业微信应用 access_token
        # 文档：https://developer.work.weixin.qq.com/document/path/91039
        "get_token": {
            "method": "GET",
            "url": "/cgi-bin/gettoken",
            "params": {
                "corpid": config.WECOM_CORP_ID,
                "corpsecret": config.WECOM_CORP_SECRET,
            },
        },
    }
