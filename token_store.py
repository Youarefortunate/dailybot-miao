import json
import os
from api import apis
from request.hooks import use_request

# 存储 Token 的本地 JSON 文件名
TOKEN_FILE = "token.json"
# 内存中的 Token 字典，用于快速访问
_token_dict = {}


def save_token(open_id, access_token, refresh_token):
    """
    保存用户的 access_token 和 refresh_token。
    同时更新内存字典和本地 JSON 文件。
    """
    _token_dict[open_id] = {"access_token": access_token, "refresh_token": refresh_token}
    with open(TOKEN_FILE, "w", encoding="utf-8") as f:
        json.dump(_token_dict, f, ensure_ascii=False)
    print(f"保存token: open_id={open_id}, access_token={access_token}, refresh_token={refresh_token}")


def _ensure_loaded(force=False):
    """确保本地文件中的 Token 已加载到内存"""
    if force or not _token_dict:
        if os.path.exists(TOKEN_FILE):
            try:
                with open(TOKEN_FILE, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                    if content:
                        data = json.loads(content)
                        _token_dict.clear()
                        _token_dict.update(data)
                        if "" in _token_dict:
                            del _token_dict[""]  # 清理无效空键
            except Exception as e:
                print(f"Load token error: {e}")


def load_all_tokens():
    """返回所有已保存的用户信息 (强制从磁盘同步)"""
    _ensure_loaded(force=True)
    return _token_dict


def get_token(open_id):
    _ensure_loaded()
    info = _token_dict.get(open_id)
    return info["access_token"] if info else None


def get_refresh_token(open_id):
    _ensure_loaded()
    info = _token_dict.get(open_id)
    return info["refresh_token"] if info else None


def refresh_user_token(open_id, refresh_token, tenant_access_token):
    """
    使用 refresh_token 去飞书服务器换取新的 access_token
    """
    try:
        refresh_req = use_request(apis.feishu_auth.refresh_user_token)
        data = refresh_req.fetch(
            {
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "headers": {"Authorization": f"Bearer {tenant_access_token}"},
            }
        )
        # use_request 对飞书平台会自动解包 data 字段，这里拿到的就是接口返回的 data
        if data and "access_token" in data:
            save_token(open_id, data["access_token"], data.get("refresh_token", refresh_token))
            print(f"open_id {open_id} access_token 已刷新")
            return data["access_token"]
        print(f"open_id {open_id} access_token 刷新失败: {data}")
    except Exception as e:
        print(f"open_id {open_id} access_token 刷新异常: {e}")
    return None
