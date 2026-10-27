FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# 先装依赖，代码变了也不会让这一层缓存失效
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# 容器里不用 --reload；要热更新请用本地运行方式
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
