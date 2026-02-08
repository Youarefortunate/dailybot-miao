# Request 模块使用指南

本目录包含了一个受声明式 API 风格启发的 Python 请求库，专门为多平台（如飞书）集成设计，支持 **自动鉴权**、**无感刷新** 以及 **点符号访问**。

## 目录结构

- `core/`: 核心逻辑，包括请求容器、API 注册器和工具函数。
- `hooks/`: 提供类似 React/Vue 的 `use_request` 钩子，方便状态管理。
- `platforms/`: 平台适配层，负责不同平台的 URL 解析、鉴权注入和过期处理。
- `setup/`: 快速初始化入口。

## 核心特性

### 1. 声明式 API 定义

您可以像这样定义 API，支持字符串占位符自动解析：

```python
def get_feishu_task_api():
    return {
        "platform": "feishu",
        "get_tasks": "GET /open-apis/task/v2/tasklists/{tasklist_guid}/tasks",
        "get_task": "GET /open-apis/task/v2/tasks/{task_guid}"
    }
```

### 2. 点符号访问 (Dot Notation)

不再需要使用 `apis['module']['method']`，现在支持更自然的 Python 风格：

```python
from api import apis
resp = apis.feishu_task.get_tasks({"open_id": "xxx", "tasklist_guid": "yyy"})
```

### 3. 自动化鉴权与无感刷新

底层平台类（如 `FeishuPlatform`）会自动处理 Token：

- **自动查找**：根据 `open_id` 自动从 `token_store` 获取 Token。
- **检测过期**：捕获飞书返回的权限类错误。
- **静默刷新**：后台自动刷新令牌并重试原始请求，业务层无感知。

### 4. 使用 useRequest 钩子

如果您需要管理加载状态或错误：

```python
from request.hooks.use_request import use_request
from api import apis

# 包装 API
req = use_request(apis.feishu_task.get_tasks)

# 调用
data = req['fetch']({"open_id": "xxx", ...})

# 获取状态
print(req['state'].loading)
print(req['state'].data)
```

## 快速开始

1. **初始化**：

   ```python
   from request.setup import setup_request
   from api import setup_api_requester

   # 配置请求实例（不传 token，由平台自动管理）
   request_instance = setup_request({"platform": "feishu"})
   setup_api_requester(request_instance)
   ```

2. **调用业务 API**：
   ```python
   from api import apis
   resp = apis.feishu_task.get_tasks({"open_id": "your_open_id", "tasklist_guid": "guid"})
   ```

---

此库旨在解决跨平台请求中的鉴权碎片化问题，将复杂的流转逻辑收拢在平台适配层。
