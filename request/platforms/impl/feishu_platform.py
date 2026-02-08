from api import apis
from ..modules.base_platform import BasePlatform
from token_store import get_refresh_token, refresh_user_token, save_token, get_token as get_local_token
from ...hooks.use_request import use_request

class FeishuPlatform(BasePlatform):
    """
    飞书平台接口实现
    """
    PLATFORM_NAME = "feishu"
    URL_PATTERN = r"feishu\.cn"

    def __init__(self, config=None):
        if config is None:
            config = {}
        config.setdefault('name', 'feishu')
        config.setdefault('baseURL', 'https://open.feishu.cn')
        super().__init__(config)
        # 飞书特有的响应结构: code, data, msg
        self.response_template = {
            "code": "code",
            "data": "data",
            "message": "msg"
        }

    def get_token(self, params=None):
        """
        从 token_store 自动获取用户 Token
        """
        if self.token:
            return self.token
        
        if isinstance(params, dict) and 'open_id' in params:
            return get_local_token(params['open_id'])
        return None

    def _is_token_expired(self, response):
        """
        判断飞书 Token 是否过期或无效
        """
        # 1. 检查 HTTP 状态码
        if response.status_code == 401:
            return True
        
        # 2. 检查业务错误码
        try:
            data = response.json()
            code = data.get("code")
            msg = data.get("msg", "").lower()
            
            # 99991677: Token 过期
            # 99991661: Token 无效或未提供
            if code in [99991677, 99991661]:
                return True
            
            # 关键词匹配
            if "token expired" in msg or "invalid access token" in msg:
                return True
        except:
            pass
        return False

    def refresh_token(self, params=None):
        """
        执行无感刷新：完全自闭环，使用 use_request
        """
        if not isinstance(params, dict) or 'open_id' not in params:
            return None
        
        open_id = params['open_id']
        print(f"[Feishu] 正在为 {open_id} 进行自闭环无感刷新 (use_request)...")
        
        refresh_tk = get_refresh_token(open_id)
        if not refresh_tk:
            print(f"[Feishu] 刷新失败：未找到有效 refresh_token")
            return None
            
        try:
            # 1. 获取飞书自定义机器人token
            tenant_token_req = use_request(apis.feishu_auth.get_tenant_token)
            tenant_data = tenant_token_req.fetch()
            tenant_tk = tenant_data.get("tenant_access_token") if tenant_data else None
            
            if not tenant_tk:
                print(f"[Feishu] 刷新失败：无法获取 tenant_access_token")
                return None
                
            # 2. 刷新用户令牌 
            refresh_req = use_request(apis.feishu_auth.refresh_user_token)
            fetch_refresh = refresh_req.fetch
            
            refresh_data = fetch_refresh({
                "grant_type": "refresh_token",
                "refresh_token": refresh_tk,
                "headers": {"Authorization": f"Bearer {tenant_tk}"}
            })
            
            # 注意：use_request 会根据 feishu 的模板自动解包 data 字段
            new_token = refresh_data.get("access_token") if refresh_data else None
            
            if new_token:
                # 3. 同步到本地存储
                save_token(open_id, new_token, refresh_data.get("refresh_token"))
                print(f"[Feishu] 自闭环刷新成功 (use_request)")
                return new_token
                
        except Exception as e:
            print(f"[Feishu] 刷新过程中出现异常: {e}")
            
        return None

    def get_auth_header(self, token):
        return f"Bearer {token}"

    def get_request_headers(self):
        headers = super().get_request_headers()
        headers.update({
            "Content-Type": "application/json; charset=utf-8"
        })
        return headers
