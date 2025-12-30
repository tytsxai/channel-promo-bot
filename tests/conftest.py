import os

os.environ["BOT_TOKEN"] = "test_token"
os.environ["ADMIN_IDS"] = "123456"
os.environ["DATABASE_PATH"] = ":memory:"
os.environ["LOG_LEVEL"] = "INFO"
os.environ["LOG_FORMAT"] = "text"
os.environ["HEALTHCHECK_PORT"] = "0"
