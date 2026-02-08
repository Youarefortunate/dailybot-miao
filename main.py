import requests
from config import config
import time
import datetime
import os
import json
from request.setup import setup_request
from api import setup_api_requester
from token_store import get_token, _token_dict, get_refresh_token, refresh_user_token


def _request_with_retry(open_id, url, method="GET", json_data=None, params=None):
    """
    通用请求包装器，支持 Token 过期自动刷新并重试。
    """
    def do_request(token):
        headers = {"Authorization": f"Bearer {token}"}
        if method == "POST":
            return requests.post(url, headers=headers, json=json_data, params=params)
        return requests.get(url, headers=headers, params=params)

    access_token = get_token(open_id)
    resp = do_request(access_token)
    
    # 检查是否为 Token 过期错误 (飞书错误码 99991677)
    try:
        data = resp.json()
        if data.get("code") == 99991677 or "Authentication token expired" in data.get("msg", ""):
            print(f"检测到 Token 过期，正在为 {open_id} 尝试刷新...")
            refresh_token = get_refresh_token(open_id)
            tenant_access_token = get_tenant_access_token() # 获取机器人令牌作为刷新背书
            
            new_token = refresh_user_token(open_id, refresh_token, tenant_access_token)
            if new_token:
                print(f"刷新成功，正在重试请求...")
                resp = do_request(new_token)
    except Exception:
        pass # 非 JSON 返回或解析失败，保持原样逻辑

    return resp

def fetch_comments(open_id, task_guid):
    """
    获取指定任务的评论。
    """
    url = "https://open.feishu.cn/open-apis/task/v2/comments"
    params = {"resource_id": task_guid, "resource_type": "task"}
    resp = _request_with_retry(open_id, url, params=params)
    
    if resp.status_code == 200:
        return resp.json().get("data", {}).get("items", [])
    return []

def get_tenant_access_token():
    """
    获取自建应用的 tenant_access_token。
    这是应用级别的令牌，用于访问不属于特定用户的资源或执行管理操作。
    """
    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal/"
    resp = requests.post(url, json={
        "app_id": config.FEISHU_APP_ID,
        "app_secret": config.FEISHU_APP_SECRET
    })
    return resp.json().get("tenant_access_token")

def get_user_name(tenant_access_token, open_id):
    """
    通过 open_id 获取用户的真实姓名。
    """
    url = f"https://open.feishu.cn/open-apis/contact/v3/users/{open_id}"
    headers = {"Authorization": f"Bearer {tenant_access_token}"}
    resp = requests.get(url, headers=headers)
    if resp.status_code == 200:
        return resp.json().get("data", {}).get("user", {}).get("name", open_id)
    return open_id

def timestamp_to_date(ts):
    """
    将飞书 API 返回的毫秒级时间戳转换为日期对象。
    """
    return datetime.datetime.fromtimestamp(int(ts)//1000).date()

def group_tasks_by_user_and_date(tasks, openid2token):
    """
    核心业务逻辑：按用户和截止日期对任务进行分组。
    
    参数:
        tasks: 飞书 API 返回的原始任务列表
        openid2token: 用户 open_id 到 access_token 的映射字典，用于拉取评论
    """
    user_day = {}
    for task in tasks:
        print(f"任务: {task.get('summary')}")
        print(f"  描述: {task.get('description', 'API未返回')}")
        
        # 寻找该任务的负责人，看我们是否有其授权来抓取评论
        assignees = [m.get("id") for m in task.get("members", []) if m.get("role") == "assignee"]
        target_open_id = next((aid for aid in assignees if aid in openid2token), None)
        
        comments = fetch_comments(target_open_id, task["guid"]) if target_open_id else []
        print(f"  评论: {[c.get('content', 'API未返回') for c in comments]}")
        
        # 确定任务的相关人员（负责人和关注者）
        members = [m.get("id") for m in task.get("members", []) if m.get("role") in ("assignee", "follower")]
        
        # 处理截止日期
        due_ts = task.get("due", {}).get("timestamp")
        if due_ts:
            day = timestamp_to_date(due_ts)
        else:
            day = None
            
        # 整理任务的关键信息
        task_info = {
            "summary": task.get("summary"),
            "completed": task.get("completed_at") != "0", # 判断任务是否已完成
            "due": due_ts,
            "desc": task.get("description", "API未返回"),
            "comments": [c.get("content", "API未返回") for c in comments],
            "date": str(day)
        }
        
        # 将任务归类到每个成员的名下
        for user_id in set(members):
            user_day.setdefault(user_id, {}).setdefault(str(day), []).append(task_info)
        
        # 稍微延迟一下，避免触发表叔 API 的频率限制
        time.sleep(0.2)
    return user_day

def pretty_grouped_tasks(user_day, tenant_access_token):
    """
    将分组后的任务字典转换成美化的字符串文本，准备发送给 AI 总结或直接推送。
    """
    text = ""
    for user, days in user_day.items():
        # 获取用户的真实姓名
        name = get_user_name(tenant_access_token, user)
        text += f"\n【{name}】\n"
        all_tasks = []
        # 合并该用户下所有日期的任务
        for day, tasks in days.items():
            all_tasks.extend(tasks)
            
        if all_tasks:
            text += "所有任务：\n"
            for t in all_tasks:
                status = "✅已完成" if t["completed"] else "❌未完成"
                # 拼接任务摘要、状态、日期和描述
                text += f"- {t['summary']}（{status}，日期:{t['date']}）\n  描述：{t['desc'] or '无'}\n"
                # 如果有评论，也拼接到后面
                if t["comments"]:
                    text += "  评论：" + " | ".join(t["comments"]) + "\n"
        else:
            text += "无任务\n"
    return text

def summarize_with_doubao(text):
    """
    使用豆包 AI 总结。优化提示词以适配飞书卡片。
    """
    url = config.DOUBAO_BASE_URL
    headers = {
        "Authorization": f"Bearer {config.DOUBAO_API_KEY}",
        "Content-Type": "application/json"
    }
    system_prompt = (
        "你是一个专业、亲和的飞书日报助手。请根据提供的任务数据，为每个人生成美观、结构清晰的进度总结。\n"
        "排版要求：\n"
        "1. 使用 **加粗** 突出人名、任务标题和关键状态。\n"
        "2. 使用列表（- 或 1.）进行排版，增加层次感。\n"
        "3. 重要：严禁使用 Markdown 标准表格格式（飞书卡片不支持表格渲染），请用列表形式替代表格内容。\n"
        "4. 重要：严禁在输出的内容前后包裹 ```markdown 或 ``` 等代码块标签，直接输出纯文本内容。\n"
        "5. 适当添加一些表情符号（如 ✅, 🕒, 💡）增加可读性。"
    )
    data = {
        "model": config.DOUBAO_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text}
        ]
    }
    resp = requests.post(url, headers=headers, json=data)
    if resp.status_code == 200:
        content = resp.json().get("choices", [{}])[0].get("message", {}).get("content", "总结失败")
        # 清理逻辑：去掉 AI 偶尔强行加的 markdown 代码块包裹
        if content.startswith("```"):
            lines = content.split("\n")
            if lines[0].startswith("```"): lines = lines[1:]
            if lines and lines[-1].startswith("```"): lines = lines[:-1]
            content = "\n".join(lines).strip()
        return content
    return f"总结失败: {resp.text}"


def send_to_group(access_token, target_id, summary):
    """
    将生成的总结内容推送到飞书（支持 Markdown 消息卡片）。
    """
    url = "https://open.feishu.cn/open-apis/im/v1/messages"
    
    # 自动识别 ID 类型
    receive_id_type = "open_id" if target_id.startswith("ou_") else "chat_id"
    
    params = {"receive_id_type": receive_id_type}
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json; charset=utf-8"
    }
    
    # 构造飞书消息卡片 (JSON 格式)
    card_content = {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {
                "tag": "plain_text",
                "content": "📊 飞书任务助手 · 每日进度总结"
            },
            "template": "blue"
        },
        "elements": [
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": summary
                }
            }
        ]
    }

    payload = {
        "receive_id": target_id,
        "msg_type": "interactive",
        "content": json.dumps(card_content)
    }
    
    resp = requests.post(url, headers=headers, params=params, json=payload)
    print(f"推送返回 ({target_id}): {resp.text}")
    return resp.json()


def fetch_tasks(open_id):
    """
    拉取指定用户的可见任务。
    """
    tasklist_guid = config.TASKLIST_GUID
    url = "https://open.feishu.cn/open-apis/task/v2/tasks"
    params = {"tasklist_guid": tasklist_guid, "page_size": 50, "user_id_type": "open_id"}
    
    resp = _request_with_retry(open_id, url, params=params)
    
    if resp.status_code != 200:
        print(f"获取任务失败 ({open_id}): {resp.text}")
        return []
    
    return resp.json().get("data", {}).get("items", [])

def bootstrap():
    """
    初始化项目：串联请求库与 API 注册器。
    """
    # 1. 初始化请求实例（会自动根据平台加载配置）
    request_instance = setup_request({"platform": "feishu"})
    
    # 2. 将请求实例关联到 API 注册器
    setup_api_requester(request_instance)
    print("✅ 请求与 API 模块串联成功")

def main():
    """
    程序主入口：
    1. 初始化模块关联
    2. 加载授权用户
    3. 拉取所有任务
    4. 任务去重与分组
    5. AI 总结
    6. 推送至群聊
    """
    bootstrap()
    
    # 自动加载 token.json 中已授权的用户
    if not _token_dict and os.path.exists("token.json"):
        with open("token.json", "r", encoding="utf-8") as f:
            data = json.load(f)
            _token_dict.update(data)
    
    open_ids = list(_token_dict.keys())
    if not open_ids:
        print("未找到任何已授权的用户，请先通过 FastAPI 授权！")
        return
    
    print(f"自动获取到 {len(open_ids)} 个已授权用户：{open_ids}")
    all_tasks = []
    # 预先构建 open_id 到 token 的映射，方便后面查评论
    openid2token = {oid: get_token(oid) for oid in open_ids if get_token(oid)}
    
    # 遍历每个用户，拉取他们可见的任务
    for open_id in open_ids:
        tasks = fetch_tasks(open_id)
        print(f"{open_id} 拉取到任务数: {len(tasks)}")
        all_tasks.extend(tasks)
    
    if not all_tasks:
        print("未获取到任何任务，请检查任务清单配置和用户权限")
        return
    
    # 任务去重（因为多个用户可能会看到同一个任务）
    guid_set = set()
    unique_tasks = []
    for t in all_tasks:
        if t["guid"] not in guid_set:
            unique_tasks.append(t)
            guid_set.add(t["guid"])
    
    # 获取应用级 token，用于查用户名
    tenant_access_token = get_tenant_access_token()
    # 执行分组逻辑
    user_day = group_tasks_by_user_and_date(unique_tasks, openid2token)
    # 生成美化文本
    pretty_text = pretty_grouped_tasks(user_day, tenant_access_token)
    print("\n美化输出：\n", pretty_text)
    # AI 总结
    summary = summarize_with_doubao(pretty_text)
    print("\n豆包总结：\n", summary)
    # 推送
    send_to_group(tenant_access_token, config.TARGET_CHAT_ID, summary)

if __name__ == "__main__":
    main()
