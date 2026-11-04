FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# 先装依赖，代码变了也不会让这一层缓存失效
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# 非 root 运行：应用被打穿时拿到的也不是宿主机 root 上下文。
# 用数字 UID 而不是 useradd，省掉对系统包的依赖（slim 镜像不一定带 passwd）。
# uploads 要提前 chown，否则 named volume 首次挂载后写不进去。
RUN mkdir -p /app/uploads && chown -R 10001:10001 /app
USER 10001:10001

EXPOSE 8000

# 探针打 /health：MySQL 挂了才 503，Redis 挂了只标 degraded、仍 200。
# 用 python 自带的 urllib，slim 镜像里没有 curl。
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import sys, urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4).status == 200 else 1)"

# --proxy-headers：让 request.client.host 取 X-Forwarded-For 里的真实 IP。
# 不加的话 nginx 后面所有用户共用同一个限流桶（见 utils/rate_limit.py 的说明）。
# ⚠️ --forwarded-allow-ips=* 信任所有来源，前提是后端不直接暴露公网；
# compose 里映射 18000 只用于调试，正式部署应去掉该端口映射。
# 容器里不用 --reload；要热更新请用本地运行方式。
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips=*"]
