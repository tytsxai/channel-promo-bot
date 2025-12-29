import pytest
import os


class TestConfig:
    def test_promo_hour_default(self):
        from src.config import config
        assert 0 <= config.promo_hour_utc <= 23

    def test_promo_minute_default(self):
        from src.config import config
        assert 0 <= config.promo_minute <= 59

    def test_min_members_default(self):
        from src.config import config
        assert config.min_members == 700

    def test_admin_ids_loaded(self):
        from src.config import config
        assert len(config.admin_ids) > 0
