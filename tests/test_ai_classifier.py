import pytest
from src.services.ai_classifier import CATEGORIES


class TestAIClassifier:
    def test_categories_defined(self):
        assert len(CATEGORIES) > 0
        assert "其他" in CATEGORIES

    def test_categories_list(self):
        expected = ["科技数码", "影视娱乐", "游戏电竞", "学习教育",
                    "资源分享", "新闻资讯", "生活服务", "金融理财", "其他"]
        assert CATEGORIES == expected
