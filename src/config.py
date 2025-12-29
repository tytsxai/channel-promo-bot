import os
import sys
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Config:
    bot_token: str
    admin_ids: list[int]
    openai_api_key: str
    min_members: int
    database_path: str
    promo_hour_utc: int
    promo_minute: int

    @classmethod
    def from_env(cls) -> "Config":
        bot_token = os.getenv("BOT_TOKEN", "")
        if not bot_token:
            sys.exit("ERROR: BOT_TOKEN is required")

        admin_ids_raw = os.getenv("ADMIN_IDS", "")
        admin_ids = []
        for x in admin_ids_raw.split(","):
            x = x.strip()
            if x:
                try:
                    admin_ids.append(int(x))
                except ValueError:
                    sys.exit(f"ERROR: Invalid ADMIN_ID: {x}")

        if not admin_ids:
            sys.exit("ERROR: At least one ADMIN_ID is required")

        promo_hour = int(os.getenv("PROMO_HOUR_UTC", "5"))
        promo_minute = int(os.getenv("PROMO_MINUTE", "0"))
        if not (0 <= promo_hour <= 23):
            sys.exit(f"ERROR: PROMO_HOUR_UTC must be 0-23, got {promo_hour}")
        if not (0 <= promo_minute <= 59):
            sys.exit(f"ERROR: PROMO_MINUTE must be 0-59, got {promo_minute}")

        return cls(
            bot_token=bot_token,
            admin_ids=admin_ids,
            openai_api_key=os.getenv("OPENAI_API_KEY", ""),
            min_members=int(os.getenv("MIN_MEMBERS", "700")),
            database_path=os.getenv("DATABASE_PATH", "data/bot.db"),
            promo_hour_utc=promo_hour,
            promo_minute=promo_minute,
        )


config = Config.from_env()
