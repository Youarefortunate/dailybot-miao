from fastapi import FastAPI
from fastapi.responses import RedirectResponse, HTMLResponse
import requests
from config import config
from token_store import save_token, get_token, load_all_tokens

FEISHU_APP_ID = config.FEISHU_APP_ID
FEISHU_APP_SECRET = config.FEISHU_APP_SECRET
OAUTH_REDIRECT_URI = config.OAUTH_REDIRECT_URI
TASKLIST_GUID = config.TASKLIST_GUID

app = FastAPI()


@app.get("/")
@app.get("/auth")
def auth():
    return RedirectResponse(
        f"https://open.feishu.cn/open-apis/authen/v1/index?app_id={FEISHU_APP_ID}&redirect_uri={OAUTH_REDIRECT_URI}&state=state-test"
    )


@app.get("/favicon.ico")
@app.get("/.well-known/{_path:path}")
def silence():
    return {}


@app.get("/callback")
def callback(code: str):
    """
    飞书授权后的回调接口。
    飞书会带上一个 'code' 参数跳转回这个地址。
    我们使用这个 'code' 去换取用户的 access_token。
    """
    url = "https://open.feishu.cn/open-apis/authen/v1/access_token"
    resp = requests.post(
        url,
        json={
            "grant_type": "authorization_code",
            "code": code,
            "app_id": FEISHU_APP_ID,
            "app_secret": FEISHU_APP_SECRET,
        },
    )
    data = resp.json()
    if "data" in data:
        open_id = data["data"]["open_id"]
        access_token = data["data"]["access_token"]
        refresh_token = data["data"]["refresh_token"]
        save_token(open_id, access_token, refresh_token)
        return HTMLResponse(f"<h2>授权成功！open_id: {open_id}</h2>")
    return HTMLResponse(f"<h2>授权失败！{data}</h2>")


@app.get("/tasks")
def get_tasks(open_id: str = None):
    """
    获取任务列表。如果未提供 open_id，则自动尝试使用最近一次授权的用户。
    """
    # 自动获取第一个可用的 open_id
    if not open_id:
        tokens = load_all_tokens()
        open_id = next(iter(tokens), None)

    if not open_id or not get_token(open_id):
        return {"msg": "请先完成授权，或通过 ?open_id= 传参"}

    # 优先使用配置中的 GUID，并确保去除了多余空格
    target_guid = (TASKLIST_GUID or config.TASKLIST_GUID).strip()

    print(f"target_guid: {target_guid}")

    if not target_guid:
        return {"msg": "未配置 TASKLIST_GUID"}

    url = f"https://open.feishu.cn/open-apis/task/v2/tasklists/{target_guid}/tasks"
    headers = {"Authorization": f"Bearer {get_token(open_id)}"}
    resp = requests.get(url, headers=headers, params={"page_size": 50, "user_id_type": "open_id"})
    return resp.json()
