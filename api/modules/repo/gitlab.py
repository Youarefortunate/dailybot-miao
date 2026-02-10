def get_gitlab_api():
    """
    GitLab 核心 API 定义
    """
    return {
        "platform": "gitlab",
        # 获取项目的提交记录
        "get_commits": "GET /projects/{project_id}/repository/commits",
        # 获取项目详细信息
        "get_project": "GET /projects/{project_id}",
    }


