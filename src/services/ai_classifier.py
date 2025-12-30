import logging

import httpx
from openai import AsyncOpenAI

from src.config import config

logger = logging.getLogger(__name__)

# OpenAI 客户端单例，带超时配置
_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        client_kwargs: dict[str, object] = {
            "api_key": config.openai_api_key,
            "timeout": httpx.Timeout(30.0, connect=10.0),
        }
        if config.openai_base_url:
            client_kwargs["base_url"] = config.openai_base_url
        _client = AsyncOpenAI(**client_kwargs)
    return _client

CATEGORIES = [
    "科技数码",
    "影视娱乐",
    "游戏电竞",
    "学习教育",
    "资源分享",
    "新闻资讯",
    "生活服务",
    "金融理财",
    "其他",
]


async def classify_channel(title: str, description: str = "") -> str:
    if not config.openai_api_key:
        return "其他"

    client = _get_client()

    prompt = f"""根据以下频道信息，从这些分类中选择最合适的一个：
{", ".join(CATEGORIES)}

频道名称：{title}
频道描述：{description}

只返回分类名称，不要其他内容。"""

    try:
        response = await client.chat.completions.create(
            model=config.openai_model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=20,
            temperature=0,
        )
        content = response.choices[0].message.content
        if not content:
            return "其他"
        result = content.strip()
        return result if result in CATEGORIES else "其他"
    except Exception as e:
        logger.exception(f"AI classification failed for '{title}': {e}")
        return "其他"
