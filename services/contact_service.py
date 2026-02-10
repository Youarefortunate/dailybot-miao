from api import apis
from request.hooks import use_request
from feishu_oauth_fastapi import get_tenant_token


def get_user_name(open_id):
    """通过 open_id 获取姓名"""
    tenant_token = get_tenant_token()
    req = use_request(apis.feishu_app_contact.get_user_info)
    try:
        data = req.fetch(
            {"user_id": open_id, "headers": {"Authorization": f"Bearer {tenant_token}"}}
        )
        return data.get("user", {}).get("name", open_id) if data else open_id
    except:
        return open_id
