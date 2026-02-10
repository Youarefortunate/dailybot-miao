def get_task_api():
    """
    飞书任务模块 API 定义 (使用 tenant_access_token)
    """
    return {
        "platform": "feishu",
        # 获取任务列表
        "get_tasks": {
            "method": "GET",
            "auth_type": "app",
            "url": "/open-apis/task/v2/tasklists/{tasklist_guid}/tasks",
        },
        # 获取单条任务详情
        "get_task": {
            "method": "GET",
            "auth_type": "app",
            "url": "/open-apis/task/v2/tasks/{task_guid}",
        },
        # 获取任务评论列表
        "get_comments": {
            "method": "GET",
            "auth_type": "app",
            "url": "/open-apis/task/v2/comments",
        },
    }
