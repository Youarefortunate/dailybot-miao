import json
from loguru import logger
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from api import apis
from config import config
from request.hooks import use_request
from token_store import save_token, fetch_tenant_access_token

app = FastAPI()


@app.get("/callback")
def callback(code: str):
    """授权回调接口"""
    logger.info(f"📡 接收到授权回调，Code: {code[:10]}...")
    token_api = use_request(apis.feishu_user_auth.get_access_token)
    try:
        data = token_api.fetch({"code": code})
        if data and "access_token" in data:
            open_id = data["open_id"]
            access_token = data["access_token"]
            refresh_token = data["refresh_token"]

            # 获取自建应用 token (tenant_access_token)
            logger.info(f"🔄 正在为用户 {open_id} 获取自建应用 Token...")
            app_token = fetch_tenant_access_token()

            # 一起存入 token_store
            save_token(open_id, access_token, refresh_token, app_token=app_token)
            # 授权成功后发送精美通知卡片
            logger.info(f"✅ 授权成功，准备为用户 {open_id} 发送成功提示...")
            send_success_card(open_id)
            return HTMLResponse("<h2>授权成功！请返回终端查看进度。</h2>")
    except Exception as e:
        logger.error(f"❌ 授权回调处理失败: {e}")
        return HTMLResponse(f"<h2>授权失败: {e}</h2>")
    return HTMLResponse("<h2>授权失败：未获取到有效数据</h2>")


def get_tenant_token():
    """兼容性保留，内部调用封装后的逻辑"""
    return fetch_tenant_access_token()


def send_success_card(open_id):
    """发送授权成功卡片"""
    tenant_token = get_tenant_token()
    if not tenant_token:
        return

    card = {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {"tag": "plain_text", "content": "🎊 授权成功"},
            "template": "green",
        },
        "elements": [
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": "感谢您的授权！机器人现在可以代表您读取任务清单了。\n\n**后续流程：**\n- 机器人将自动检测到授权并开始生成日报。\n- 如果由于长时间不使用导致失效，您可以在群聊中再次点击授权按钮（无感刷新机制会尽量避免此情况）。",
                },
            },
            {"tag": "hr"},
            {
                "tag": "note",
                "elements": [
                    {"tag": "plain_text", "content": "您可以关闭此页面返回飞书。"}
                ],
            },
        ],
    }

    req = use_request(apis.feishu_app_im.send_message)
    try:
        req.fetch(
            {
                "params": {"receive_id_type": "open_id"},
                "receive_id": open_id,  # 直接推送到用户
                "content": json.dumps(card),
                "msg_type": "interactive",
                "headers": {"Authorization": f"Bearer {tenant_token}"},
            }
        )
        logger.info(f"✨ 已向用户 {open_id} 推送授权成功反馈卡片")
    except Exception as e:
        logger.warning(f"⚠️ 推送授权成功反馈失败: {e}")


def send_auth_nudge():
    """
    主动推送授权引导卡片。
    返回 (success, error_reason)：
    - success=True 表示发送成功
    - success=False 时 error_reason 包含具体失败原因
    """
    try:
        tenant_token = get_tenant_token()
    except Exception as e:
        reason = str(e)
        logger.error(f"❌ {reason}")
        return False, reason

    if not tenant_token:
        reason = "无法获取机器人 Token，可能是网络异常或应用凭证失效"
        logger.error(f"❌ {reason}")
        return False, reason

    auth_url = (
        f"https://open.feishu.cn/open-apis/authen/v1/index?app_id={config.FEISHU_APP_ID}"
        f"&redirect_uri={config.FEISHU_OAUTH_REDIRECT_URI}&state=init"
    )

    card = {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {"tag": "plain_text", "content": "🔐 机器人需要您的授权"},
            "template": "orange",
        },
        "elements": [
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": "检测到目前没有有效的用户授权，机器人无法读取任务详情。\n请点击下方按钮完成授权后，机器人将自动继续工作。",
                },
            },
            {
                "tag": "action",
                "actions": [
                    {
                        "tag": "button",
                        "text": {"tag": "plain_text", "content": "立即授权"},
                        "type": "primary",
                        "url": auth_url,
                    }
                ],
            },
        ],
    }

    req = use_request(apis.feishu_app_im.send_message)
    try:
        req.fetch(
            {
                "receive_id": config.FEISHU_TARGET_CHAT_ID,
                "content": json.dumps(card),
                "msg_type": "interactive",
                "headers": {"Authorization": f"Bearer {tenant_token}"},
            }
        )
        logger.info("🚀 已向群聊发送授权引导卡片")
        return True, None
    except Exception as e:
        reason = str(e)
        logger.error(f"❌ 发送引导卡片失败: {reason}")
        return False, reason
