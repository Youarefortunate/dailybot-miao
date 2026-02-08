# from fastapi import FastAPI
# from fastapi.responses import RedirectResponse, HTMLResponse
# from config import config
# from token_store import save_token, get_token, load_all_tokens
# from api import apis
# from request.hooks import use_request

# FEISHU_APP_ID = config.FEISHU_APP_ID
# FEISHU_APP_SECRET = config.FEISHU_APP_SECRET
# OAUTH_REDIRECT_URI = config.OAUTH_REDIRECT_URI
# TASKLIST_GUID = config.TASKLIST_GUID

# app = FastAPI()


# @app.get("/")
# @app.get("/auth")
# def auth():
#     return RedirectResponse(
#         f"https://open.feishu.cn/open-apis/authen/v1/index?app_id={FEISHU_APP_ID}&redirect_uri={OAUTH_REDIRECT_URI}&state=state-test"
#     )


# @app.get("/favicon.ico")
# @app.get("/.well-known/{_path:path}")
# def silence():
#     return {}


# @app.get("/callback")
# def callback(code: str):
#     """
#     飞书授权后的回调接口。
#     飞书会带上一个 'code' 参数跳转回这个地址。
#     我们使用这个 'code' 去换取用户的 access_token。
#     """
#     token_api = use_request(apis.feishu_auth.get_access_token)
#     data = token_api.fetch({"code": code})

#     if data and "open_id" in data:
#         open_id = data["open_id"]
#         access_token = data["access_token"]
#         refresh_token = data["refresh_token"]
#         save_token(open_id, access_token, refresh_token)
#         return HTMLResponse(f"<h2>授权成功！open_id: {open_id}</h2>")
#     return HTMLResponse(f"<h2>授权失败！{data}</h2>")


# @app.get("/tasks")
# def get_tasks(open_id: str = None):
#     """
#     获取任务列表。如果未提供 open_id，则自动尝试使用最近一次授权的用户。
#     """
#     # 自动获取第一个可用的 open_id
#     if not open_id:
#         tokens = load_all_tokens()
#         open_id = next(iter(tokens), None)

#     if not open_id or not get_token(open_id):
#         return {"msg": "请先完成授权，或通过 ?open_id= 传参"}

#     # 优先使用配置中的 GUID，并确保去除了多余空格
#     target_guid = (TASKLIST_GUID or config.TASKLIST_GUID).strip()

#     if not target_guid:
#         return {"msg": "未配置 TASKLIST_GUID"}

#     tasks_api = use_request(apis.feishu_task.get_tasks)
#     try:
#         data = tasks_api.fetch(
#             {
#                 "tasklist_guid": target_guid,
#                 "page_size": 50,
#                 "user_id_type": "open_id",
#                 "open_id": open_id,  # 供平台实例自动获取 token
#             }
#         )
#         return data
#     except Exception as e:
#         return {"error": str(e)}
