from loguru import logger
from api import apis
from request.hooks import use_request

def fetch_comments(open_id, task_guid):
  """获取任务评论"""
  req = use_request(apis.feishu_task.get_comments)
  try:
    data = req.fetch({"resource_id": task_guid, "resource_type": "task", "open_id": open_id})
    return data.get("items", []) if data else []
  except:
    return []

def get_tasks_by_user(open_id, tasklist_guid):
  """获取指定用户的任务列表"""
  tasks_api = use_request(apis.feishu_task.get_tasks)
  try:
    res = tasks_api.fetch({"tasklist_guid": tasklist_guid, "open_id": open_id, "page_size": 50})
    return res.get("items", []) if isinstance(res, dict) else []
  except Exception as e:
    logger.warning(f"⚠️ 拉取用户 {open_id} 任务失败: {e}")
    return []
