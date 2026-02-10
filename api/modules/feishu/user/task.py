def get_task_api():
    """
    飞书任务模块 API 定义 (使用 user_access_token)
    """
    return {
        "platform": "feishu",
        # 获取指定用户清单（单个）
        "get_task": "GET /open-apis/task/v2/tasks",
        # 获取清单任务列表
        "get_tasks": "GET /open-apis/task/v2/tasklists/{tasklist_guid}/tasks",
    }
