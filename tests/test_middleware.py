import pytest
import time
from src.middleware import RateLimitMiddleware


class TestRateLimitMiddleware:
    def test_init_defaults(self):
        middleware = RateLimitMiddleware()
        assert middleware.limit == 5
        assert middleware.window == 60
        assert middleware.cleanup_interval == 300

    def test_init_custom(self):
        middleware = RateLimitMiddleware(limit=10, window=30, cleanup_interval=100)
        assert middleware.limit == 10
        assert middleware.window == 30
        assert middleware.cleanup_interval == 100

    def test_requests_tracking(self):
        middleware = RateLimitMiddleware(limit=3, window=60)
        user_id = 12345
        now = time.time()

        middleware.requests[user_id] = [now - 10, now - 5]
        assert len(middleware.requests[user_id]) == 2

    def test_cleanup_stale_entries_skips_when_interval_not_reached(self):
        middleware = RateLimitMiddleware(limit=3, window=60, cleanup_interval=300)
        now = time.time()
        middleware._last_cleanup = now - 100  # 100秒前清理过
        middleware.requests[111] = [now - 1000]  # 过期记录

        middleware._cleanup_stale_entries(now)
        # 未到清理间隔，不应清理
        assert 111 in middleware.requests

    def test_cleanup_stale_entries_removes_expired(self):
        middleware = RateLimitMiddleware(limit=3, window=60, cleanup_interval=300)
        now = time.time()
        middleware._last_cleanup = now - 400  # 超过清理间隔

        middleware.requests[111] = [now - 1000]  # 过期
        middleware.requests[222] = [now - 10]    # 未过期
        middleware.requests[333] = []            # 空列表

        middleware._cleanup_stale_entries(now)

        assert 111 not in middleware.requests
        assert 222 in middleware.requests
        assert 333 not in middleware.requests
