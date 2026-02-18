import json
import os
import inspect
from loguru import logger
from request.hooks import use_request
from functools import wraps


# 存储 Token 的本地 JSON 文件名
TOKEN_FILE = "token.json"
# 内存中的 Token 字典，用于快速访问
_token_dict = {}

# 临时存储自建应用 Token，用于授权流程中的中转
_temp_app_token = None


def _auto_ensure_loaded(func):
    """
    装饰器：在调用被装饰函数前自动执行 `_ensure_loaded()`。
    如果函数的 `open_id` 参数为 `None`，则自动使用 `get_current_open_id()`。
    """

    @wraps(func)
    def wrapper(*args, **kwargs):
        _ensure_loaded()
        # 获取函数签名
        sig = inspect.signature(func)
        params = list(sig.parameters.keys())

        # 检查 open_id 参数
        if "open_id" in params:
            # 确定 open_id 在参数列表中的位置
            open_id_index = params.index("open_id")

            # 如果 open_id 在位置参数中且为 None
            if open_id_index < len(args) and args[open_id_index] is None:
                # 替换为当前用户的 open_id
                args = list(args)
                args[open_id_index] = get_current_open_id()
                args = tuple(args)
            # 如果 open_id 在关键字参数中且为 None
            elif "open_id" in kwargs and kwargs["open_id"] is None:
                kwargs["open_id"] = get_current_open_id()

        return func(*args, **kwargs)

    return wrapper


def _save_to_file():
    """
    将内存中的 _token_dict 持久化到本地 JSON 文件。
    """
    try:
        with open(TOKEN_FILE, "w", encoding="utf-8") as f:
            json.dump(_token_dict, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"持久化 token 文件失败: {e}")


def save_token(open_id, access_token, refresh_token, app_token=None):
    """
    保存用户的 access_token、refresh_token 以及自建应用 token (app_token)。
    同时更新内存字典和本地 JSON 文件。
    """
    _token_dict[open_id] = {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "app_token": app_token,
    }
    _save_to_file()
    logger.debug(
        f"保存token: open_id={open_id}, access_token={access_token[:10]}..., "
        f"refresh_token={refresh_token[:10]}..., app_token={app_token[:10] if app_token else None}..."
    )


def fetch_tenant_access_token():
    """
    从飞书服务端请求最新的自建应用 token (tenant_access_token)。
    成功返回 token 字符串，失败时抛出异常让调用方处理。
    """
    try:
        from api import apis

        req = use_request(apis.feishu_app_auth.get_tenant_token)
        data = req.fetch()
        token = data.get("tenant_access_token") if data else None
        if token:
            logger.info(f"✅ 成功获取最新的自建应用 Token: {token[:10]}...")
            return token
        raise Exception("获取自建应用 Token 失败：响应数据为空或缺失字段")
    except Exception as e:
        logger.error(f"❌ 获取自建应用 Token 异常: {e}")
        raise


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
                logger.error(f"加载 token 文件异常: {e}")


def load_all_tokens():
    """返回所有已保存的用户信息 (强制从磁盘同步)"""
    _ensure_loaded(force=True)
    return _token_dict


@_auto_ensure_loaded
def get_current_open_id():
    """
    获取当前用户的 open_id。
    当前实现：如果本地只保存了一个或多个用户，则返回第一个用户的 open_id。
    如需更复杂的“当前用户”判定逻辑，可在此处扩展。
    """
    if not _token_dict:
        return None
    # 简单返回字典中的第一个 open_id
    return next(iter(_token_dict.keys()))


@_auto_ensure_loaded
def get_token(open_id=None):
    info = _token_dict.get(open_id)
    return info.get("access_token") if info else None


@_auto_ensure_loaded
def get_app_token(open_id=None, force_refresh=False):
    """
    获取保存的自建应用 token。
    优化逻辑：内存 -> 临时变量 -> fetch_tenant_access_token
    :param force_refresh: 是否强制在线刷新（跳过缓存）
    """
    global _temp_app_token

    if not force_refresh:
        if open_id is None:
            open_id = get_current_open_id()

        # 1. 优先尝试从内存获取（已持久化的用户信息中）
        info = _token_dict.get(open_id)
        if info and info.get("app_token"):
            logger.debug(
                f"🎯 从内存获取到 open_id {open_id} 的 app_token: {info['app_token'][:10]}..."
            )
            return info["app_token"]

        # 2. 尝试从临时变量获取（授权过程中的中转）
        if _temp_app_token:
            logger.debug(f"⚡ 从临时变量获取到 app_token: {_temp_app_token[:10]}...")
            return _temp_app_token

    # 3. 在线换取并暂存
    logger.info("🌐 准备在线获取最新的 app_token...")
    new_token = fetch_tenant_access_token()
    if new_token:
        # a. 更新临时变量
        _temp_app_token = new_token

        # b. 重要：将新换取的 app_token 同步更新到内存中已存的所有用户条目中
        # 这样可以确保只要有一个用户触发了刷新，所有用户在内存和文件中的 app_token 都会被同步更新
        updated = False
        for oid in _token_dict:
            if isinstance(_token_dict[oid], dict):
                _token_dict[oid]["app_token"] = new_token
                updated = True

        # c. 立即触发持久化落盘，确保状态一致
        if updated:
            _save_to_file()
            logger.debug("💾 app_token 已同步更新至本地文件")

        return new_token

    return None


def clear_temp_app_token():
    """
    清空临时存储的 app_token。
    通常在用户授权成功并持久化信息后调用。
    """
    global _temp_app_token
    _temp_app_token = None
    logger.debug("🧹 临时 app_token 已清空")


@_auto_ensure_loaded
def get_refresh_token(open_id=None):
    info = _token_dict.get(open_id)
    return info["refresh_token"] if info else None


def refresh_user_token(open_id, refresh_token, tenant_access_token=None):
    """
    使用 refresh_token 去飞书服务器换取新的 access_token。
    如果未提供 tenant_access_token，则会自动请求一个新的。
    """
    try:
        # 如果没传，或者传的是空，则主动获取一个
        if not tenant_access_token:
            tenant_access_token = fetch_tenant_access_token()

        if not tenant_access_token:
            logger.warning(f"open_id {open_id} 刷新由于缺少应用 Token 而中止")
            return None

        from api import apis

        refresh_req = use_request(apis.feishu_user_auth.refresh_user_token)
        data = refresh_req.fetch(
            {
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "headers": {"Authorization": f"Bearer {tenant_access_token}"},
            }
        )

        if data and "access_token" in data:
            save_token(
                open_id,
                data["access_token"],
                data.get("refresh_token", refresh_token),
                app_token=tenant_access_token,
            )
            logger.info(f"open_id {open_id} access_token 已刷新")
            return data["access_token"]
        logger.error(f"open_id {open_id} access_token 刷新失败: {data}")
    except Exception as e:
        logger.error(f"open_id {open_id} access_token 刷新异常: {e}")
    return None
