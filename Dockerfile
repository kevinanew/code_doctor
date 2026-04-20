# 使用 Python 官方精简镜像作为基础镜像
FROM python:3.12-slim

# 设置工作目录
WORKDIR /workspace

# 安装必要的系统工具：git
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*

# 从官方 uv 镜像中拷贝二进制文件
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uv/bin/uv
ENV PATH="/uv/bin:${PATH}"

# 将 Code Doctor 脚本拷贝到固定位置
RUN mkdir -p /usr/local/bin/code-doctor
COPY . /usr/local/bin/code-doctor/

# 为常用的 check.py 创建软链接，方便全局调用
RUN ln -s /usr/local/bin/code-doctor/check.py /usr/local/bin/check-code

# 设置环境变量，确保 Python 输出不会被缓冲
ENV PYTHONUNBUFFERED=1
