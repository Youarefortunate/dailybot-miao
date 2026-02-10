def get_task_api():
    """
    飞书任务模块 API 定义 (使用 user_access_token)
    """
    return {
        "platform": "feishu",
        # 获取指定用户任务列表
        "get_tasks": "GET /open-apis/task/v2/tasks",
    }
