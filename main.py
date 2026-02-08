import json
import threading
import time
from datetime import datetime
import uvicorn
from api import apis, setup_api_requester
from config import config
from request.hooks import use_request
from request.setup import setup_request
from token_store import load_all_tokens
from feishu_oauth_fastapi import app, send_auth_nudge, get_tenant_token

def fetch_comments(open_id, task_guid):
    """获取任务评论"""
    req = use_request(apis.feishu_task.get_comments)
    try:
        data = req.fetch({"resource_id": task_guid, "resource_type": "task", "open_id": open_id})
        return data.get("items", []) if data else []
    except:
        return []

def get_user_name(open_id):
    """通过 open_id 获取姓名"""
    tenant_token = get_tenant_token()
    req = use_request(apis.feishu_contact.get_user_info)
    try:
        data = req.fetch({"user_id": open_id, "headers": {"Authorization": f"Bearer {tenant_token}"}})
        return data.get("user", {}).get("name", open_id) if data else open_id
    except:
        return open_id

def run_reporting_logic():
    """核心日报生成与推送逻辑"""
    print("🎬 开始执行日报生成流程...")

    tokens = load_all_tokens()
    open_ids = list(tokens.keys())

    all_tasks = []
    tasks_api = use_request(apis.feishu_task.get_tasks)

    for open_id in open_ids:
        try:
            # use_request 返回的是 data 字段，飞书任务列表的 data 是 {"items": [...], ...}
            res = tasks_api.fetch({"tasklist_guid": config.TASKLIST_GUID, "open_id": open_id, "page_size": 50})
            items = res.get("items", []) if isinstance(res, dict) else []
            if items:
                all_tasks.extend(items)
        except Exception as e:
            print(f"⚠️ 拉取用户 {open_id} 任务失败: {e}")

    if not all_tasks:
        print("📭 未发现任何新任务。")
        return

    # 去重与分组 (健壮性检查)
    unique_tasks = {t["guid"]: t for t in all_tasks if isinstance(t, dict) and "guid" in t}.values()
    user_day_data = {}
    for t in unique_tasks:
        # 寻找负责人抓评论
        assignees = [m.get("id") for m in t.get("members", []) if m.get("role") == "assignee"]
        target_oid = next((aid for aid in assignees if aid in open_ids), open_ids[0])

        comments = fetch_comments(target_oid, t["guid"])
        
        # 归类
        due_ts = t.get("due", {}).get("timestamp")
        date_str = datetime.fromtimestamp(int(due_ts) // 1000).strftime("%Y-%m-%d") if due_ts else "无日期"
        
        info = {
            "summary": t.get("summary"),
            "desc": t.get("description"),
            "comments": [c.get("content") for c in comments if c.get("content")],
            "completed": t.get("status") == "completed",
            "date": date_str
        }
        
        members = [m.get("id") for m in t.get("members", []) if m.get("role") in ("assignee", "follower")]
        for uid in set(members):
            user_day_data.setdefault(uid, {}).setdefault(date_str, []).append(info)

    # 生成文本
    report_text = ""
    for uid, dates in user_day_data.items():
        name = get_user_name(uid)
        report_text += f"\n【{name}】\n"
        for date, tasks in dates.items():
            for t in tasks:
                status = "✅已完成" if t["completed"] else "🕒进行中"
                report_text += f"- {t['summary']} ({status}, {t['date']})\n"
                if t['desc']: report_text += f"  描述: {t['desc']}\n"
                if t['comments']: report_text += f"  评论: {' | '.join(t['comments'])}\n"

    # AI 总结
    print("🤖 正在请求 AI 总结...")
    summary = summarize_with_doubao(report_text) 

    # 推送
    tenant_token = get_tenant_token()
    card = {
        "header": {"title": {"tag": "plain_text", "content": "📊 团队进度总结"}, "template": "blue"},
        "elements": [{"tag": "div", "text": {"tag": "lark_md", "content": summary}}]
    }
    
    msg_req = use_request(apis.feishu_im.send_message)
    msg_req.fetch({
        "receive_id": config.TARGET_CHAT_ID,
        "content": json.dumps(card),
        "msg_type": "interactive",
        "headers": {"Authorization": f"Bearer {tenant_token}"}
    })
    print("✅ 报表已推送至群聊")

def main():
    # 1. 基础初始化
    request_instance = setup_request()
    setup_api_requester(request_instance)

    # 2. 启动内嵌 WebServer (子线程)
    server_thread = threading.Thread(target=lambda: uvicorn.run(app, host="0.0.0.0", port=8001), daemon=True)
    server_thread.start()

    # 3. 授权检测循环
    start_time = time.time()
    nudge_sent = False
    timeout_seconds = 180  # 3 分钟超时

    while True:
        tokens = load_all_tokens()
        if tokens:
            print(f"✨ 发现 {len(tokens)} 个有效授权，准备开始工作...")
            break
        
        # 检查超时
        elapsed = time.time() - start_time
        if elapsed > timeout_seconds:
            print(f"⏱️ 授权超时 ({timeout_seconds}s)，程序自动退出。请稍后重试。")
            return

        if not nudge_sent:
            print("🔍 未发现有效授权，正在发送引导卡片...")
            send_auth_nudge()
            nudge_sent = True
            print(f"⏳ 等待用户授权中 (最长等待 {timeout_seconds}s)...")
        
        # 每 10 秒重检一次
        time.sleep(10)

    # 4. 执行业务逻辑
    try:
        run_reporting_logic()
    except Exception as e:
        print(f"❌ 程序运行时出错: {e}")

# 这里的辅助函数暂时从旧代码迁移过来，直到完全 API 化
def summarize_with_doubao(text):
    import requests
    url = config.DOUBAO_BASE_URL
    headers = {"Authorization": f"Bearer {config.DOUBAO_API_KEY}", "Content-Type": "application/json"}
    data = {
        "model": config.DOUBAO_MODEL,
        "messages": [
            {"role": "system", "content": "你是一个专业日报助手，请总结以下任务，使用列表形式，不要带 markdown 代码块。"},
            {"role": "user", "content": text}
        ],
    }
    resp = requests.post(url, headers=headers, json=data)
    return resp.json().get("choices", [{}])[0].get("message", {}).get("content", "总结失败")

if __name__ == "__main__":
    main()
