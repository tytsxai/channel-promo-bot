import pytest
from src.handlers.admin_handlers import is_admin, PENDING_PER_PAGE
from src.config import config


class TestAdminHandlers:
    def test_is_admin_true(self):
        admin_id = config.admin_ids[0]
        assert is_admin(admin_id) is True

    def test_is_admin_false(self):
        assert is_admin(999999999) is False

    def test_pending_per_page_constant(self):
        assert PENDING_PER_PAGE == 5

    def test_pagination_calculation(self):
        """测试分页计算逻辑"""
        per_page = PENDING_PER_PAGE

        # 12条记录应该有3页
        total = 12
        total_pages = (total + per_page - 1) // per_page
        assert total_pages == 3

        # 5条记录应该有1页
        total = 5
        total_pages = (total + per_page - 1) // per_page
        assert total_pages == 1

        # 0条记录应该有0页
        total = 0
        total_pages = (total + per_page - 1) // per_page
        assert total_pages == 0
