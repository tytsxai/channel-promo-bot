from dataclasses import replace

import pytest

import src.services.ai_classifier as ai_classifier
from src.config import config as base_config
from src.services.ai_classifier import CATEGORIES


class TestAIClassifier:
    def test_categories_defined(self):
        assert len(CATEGORIES) > 0
        assert "其他" in CATEGORIES

    def test_categories_list(self):
        expected = ["科技数码", "影视娱乐", "游戏电竞", "学习教育",
                    "资源分享", "新闻资讯", "生活服务", "金融理财", "其他"]
        assert CATEGORIES == expected


@pytest.mark.asyncio
async def test_classify_channel_without_key(monkeypatch):
    cfg = replace(base_config, openai_api_key="")
    monkeypatch.setattr(ai_classifier, "config", cfg)
    result = await ai_classifier.classify_channel("Test", "Desc")
    assert result == "其他"


def test_get_client_cached(monkeypatch):
    created = {"count": 0}

    class DummyClient:
        def __init__(self, api_key: str, timeout):
            created["count"] += 1
            self.api_key = api_key

    cfg = replace(base_config, openai_api_key="key123")
    monkeypatch.setattr(ai_classifier, "config", cfg)
    monkeypatch.setattr(ai_classifier, "AsyncOpenAI", DummyClient)
    monkeypatch.setattr(ai_classifier, "_client", None)

    c1 = ai_classifier._get_client()
    c2 = ai_classifier._get_client()
    assert c1 is c2
    assert c1.api_key == "key123"
    assert created["count"] == 1


@pytest.mark.asyncio
async def test_classify_channel_valid_category(monkeypatch):
    class DummyMessage:
        def __init__(self, content: str):
            self.content = content

    class DummyChoice:
        def __init__(self, content: str):
            self.message = DummyMessage(content)

    class DummyResponse:
        def __init__(self, content: str):
            self.choices = [DummyChoice(content)]

    class DummyCompletions:
        async def create(self, **kwargs):
            return DummyResponse("科技数码")

    class DummyChat:
        def __init__(self):
            self.completions = DummyCompletions()

    class DummyClient:
        def __init__(self):
            self.chat = DummyChat()

    cfg = replace(base_config, openai_api_key="key123")
    monkeypatch.setattr(ai_classifier, "config", cfg)
    monkeypatch.setattr(ai_classifier, "_get_client", lambda: DummyClient())

    result = await ai_classifier.classify_channel("Test", "Desc")
    assert result == "科技数码"


@pytest.mark.asyncio
async def test_classify_channel_invalid_category(monkeypatch):
    class DummyMessage:
        def __init__(self, content: str):
            self.content = content

    class DummyChoice:
        def __init__(self, content: str):
            self.message = DummyMessage(content)

    class DummyResponse:
        def __init__(self, content: str):
            self.choices = [DummyChoice(content)]

    class DummyCompletions:
        async def create(self, **kwargs):
            return DummyResponse("未知分类")

    class DummyChat:
        def __init__(self):
            self.completions = DummyCompletions()

    class DummyClient:
        def __init__(self):
            self.chat = DummyChat()

    cfg = replace(base_config, openai_api_key="key123")
    monkeypatch.setattr(ai_classifier, "config", cfg)
    monkeypatch.setattr(ai_classifier, "_get_client", lambda: DummyClient())

    result = await ai_classifier.classify_channel("Test", "Desc")
    assert result == "其他"


@pytest.mark.asyncio
async def test_classify_channel_exception(monkeypatch):
    class DummyCompletions:
        async def create(self, **kwargs):
            raise RuntimeError("boom")

    class DummyChat:
        def __init__(self):
            self.completions = DummyCompletions()

    class DummyClient:
        def __init__(self):
            self.chat = DummyChat()

    cfg = replace(base_config, openai_api_key="key123")
    monkeypatch.setattr(ai_classifier, "config", cfg)
    monkeypatch.setattr(ai_classifier, "_get_client", lambda: DummyClient())

    result = await ai_classifier.classify_channel("Test", "Desc")
    assert result == "其他"


@pytest.mark.asyncio
async def test_classify_channel_empty_content(monkeypatch):
    class DummyMessage:
        def __init__(self, content: str):
            self.content = content

    class DummyChoice:
        def __init__(self, content: str):
            self.message = DummyMessage(content)

    class DummyResponse:
        def __init__(self, content: str):
            self.choices = [DummyChoice(content)]

    class DummyCompletions:
        async def create(self, **kwargs):
            return DummyResponse("")

    class DummyChat:
        def __init__(self):
            self.completions = DummyCompletions()

    class DummyClient:
        def __init__(self):
            self.chat = DummyChat()

    cfg = replace(base_config, openai_api_key="key123")
    monkeypatch.setattr(ai_classifier, "config", cfg)
    monkeypatch.setattr(ai_classifier, "_get_client", lambda: DummyClient())

    result = await ai_classifier.classify_channel("Test", "Desc")
    assert result == "其他"
