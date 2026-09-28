import os
from pathlib import Path

# Load .env from the same project folder.
_env_path = Path(__file__).resolve().parent / ".env"
if _env_path.exists():
    for _line in _env_path.read_text(encoding="utf-8").splitlines():
        _line = _line.strip()
        if not _line or _line.startswith("#") or "=" not in _line:
            continue
        _key, _value = _line.split("=", 1)
        _value = _value.strip().strip('"').strip("'")
        os.environ.setdefault(_key.strip(), _value)

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()

# Админы — через .env (через запятую можно несколько ID)
_admin_raw = os.getenv("ADMIN_IDS", os.getenv("ADMIN_ID", "")).strip()
ADMIN_IDS = tuple(int(x.strip()) for x in _admin_raw.split(",") if x.strip().isdigit())
ADMIN_ID = ADMIN_IDS[0] if ADMIN_IDS else 0

DB_NAME = os.getenv("DB_NAME", "shop.db").strip()
SHOP_NAME = os.getenv("SHOP_NAME", "MyShop").strip()
CRYPTO_PAY_TOKEN = os.getenv("CRYPTO_PAY_TOKEN", "").strip()

# Канал обязательной подписки и саппорт (можно менять в .env)
REQUIRED_CHANNEL = os.getenv("REQUIRED_CHANNEL", "").strip()          # например @my_channel
REQUIRED_CHANNEL_URL = os.getenv("REQUIRED_CHANNEL_URL", "").strip()  # https://t.me/my_channel
SUPPORT_USERNAME = os.getenv("SUPPORT_USERNAME", "support").strip()   # без @
RUB_OWNER_USERNAME = os.getenv("RUB_OWNER_USERNAME", SUPPORT_USERNAME).strip()
