import os
import pytest
import tempfile

os.environ["BOT_TOKEN"] = "test_token"
os.environ["ADMIN_IDS"] = "123456"
os.environ["DATABASE_PATH"] = ":memory:"
