import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env", override=False)

# OpenAI 兼容的 chat/completions 地址
AI_CHAT_URL = os.getenv("AI_CHAT_URL", "")
AI_API_KEY = os.getenv("AI_API_KEY", "")
AI_MODEL = os.getenv("AI_MODEL", "qwen3.7-flash")
AI_TIMEOUT = float(os.getenv("AI_TIMEOUT", "120"))
# 允许客户端通过请求体切换的模型，逗号分隔；留空表示只能用 AI_MODEL
AI_ALLOWED_MODELS = [m.strip() for m in os.getenv("AI_ALLOWED_MODELS", "").split(",") if m.strip()]


def is_configured() -> bool:
    """API Key 与地址都配好了才允许调用，否则直接返回 503 而不是发出一个注定失败的请求。"""
    return bool(AI_CHAT_URL and AI_API_KEY)


def allowed_models() -> set[str]:
    """客户端可以指定的模型集合。

    默认只允许配置里那一个：否则任何人拿到登录态就能把请求转成更贵的模型，
    账单由你来付。
    """
    return set(AI_ALLOWED_MODELS) | {AI_MODEL}
