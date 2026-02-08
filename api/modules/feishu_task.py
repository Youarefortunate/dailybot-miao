def get_feishu_task_api():
    """
    飞书任务模块 API 定义
    """
    return {
        "platform": "feishu",
        
        # 获取任务列表
        "get_tasks": "GET /open-apis/task/v2/tasklists/{tasklist_guid}/tasks",
        
        # 获取单条任务详情
        "get_task": "GET /open-apis/task/v2/tasks/{task_guid}",
        
        # 获取任务评论列表
        "get_comments": "GET /open-apis/task/v2/comments"
    }
