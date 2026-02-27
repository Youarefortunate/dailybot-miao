# 使用 Playwright 官方 Python 镜像，境内外环境均有较好支持
# 包含 Python 环境及 Chromium/Firefox/Webkit 浏览器核心
FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

# 设置工作目录
WORKDIR /app

# 不生成 .pyc 文件
ENV PYTHONDONTWRITEBYTECODE 1
# Python 输出不缓存
ENV PYTHONUNBUFFERED 1
# 设置时区
ENV TZ=Asia/Shanghai

# 安装系统依赖 (如果需要)
RUN apt-get update && apt-get install -y --no-install-recommends \
    tzdata \
    && ln -fs /usr/share/zoneinfo/$TZ /etc/localtime \
    && dpkg-reconfigure -f noninteractive tzdata \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .

# 安装 Python 依赖
# 注意：在 Linux 下跳过 Windows 特有库的安装
RUN pip install --no-cache-dir --upgrade pip && \
    grep -vE "winshell|pywin32|pypiwin32" requirements.txt > req_linux.txt && \
    pip install --no-cache-dir -r req_linux.txt

# 复制项目源代码
COPY . .

# 暴露 OAuth 回调端口
EXPOSE 8001

# TODO：目前push_scheduler是windows环境
CMD ["python", "push_scheduler.py"]
