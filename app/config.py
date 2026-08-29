from __future__ import annotations
import json
import sys
from pathlib import Path
from typing import Any
from cryptography.fernet import Fernet

APP_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = APP_DIR / "data"
CONFIG_FILE = DATA_DIR / "config.json"
DATA_DIR.mkdir(parents=True, exist_ok=True)

class Settings:
    """Local runtime configuration. No .env or user-supplied environment variables."""
    DEFAULTS: dict[str, Any] = {
        "seller_bot_token": "", "admin_ids": [], "web_port": 8090,
        "webapp_url": "http://127.0.0.1:8090", "database_url": "",
        "encryption_key": "", "monitor_api_url": "http://127.0.0.1:8091",
        "monitor_api_token": "local-internal", "monitor_webapp_url": "",
        "force_join_enabled": False, "force_join_channel": "", "force_join_channel_url": "",
        "card_number": "", "card_holder": "", "payment_instructions": "",
        "support_username": "", "currency_label": "تومان",
    }
    def __init__(self) -> None:
        self._values = dict(self.DEFAULTS)
        self._load()
    def _load(self) -> None:
        if CONFIG_FILE.exists():
            try:
                data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
                if not isinstance(data, dict): raise ValueError("config root must be an object")
                self._values.update(data)
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                raise RuntimeError(f"Invalid configuration file: {CONFIG_FILE}: {exc}") from exc
        self._refresh()
    def _refresh(self) -> None:
        for key, default in self.DEFAULTS.items():
            setattr(self, key, self._values.get(key, default))
        self.seller_bot_token = str(self.seller_bot_token).strip()
        self.admin_ids = [int(x) for x in self.admin_ids if str(x).isdigit()]
        self.web_port = int(self.web_port)
        self.database_url = str(self.database_url or f"sqlite+aiosqlite:///{DATA_DIR / 'seller.db'}")
        self.encryption_key = str(self.encryption_key)
        self.monitor_api_token = str(self.monitor_api_token or "local-internal")
        self.validate_values()
    def validate_values(self) -> None:
        if not 1 <= self.web_port <= 65535: raise RuntimeError("Web port must be between 1 and 65535")
    @property
    def token(self) -> str: return self.seller_bot_token
    @property
    def admins(self) -> set[int]: return set(self.admin_ids)
    @property
    def key(self) -> bytes: return self.encryption_key.encode() if self.encryption_key else Fernet.generate_key()
    def save(self, **updates: Any) -> None:
        self._values.update(updates)
        if not self._values.get("encryption_key"): self._values["encryption_key"] = Fernet.generate_key().decode()
        CONFIG_FILE.write_text(json.dumps(self._values, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        CONFIG_FILE.chmod(0o600)
        self._refresh()
    def validate_runtime(self) -> None:
        if not self.token or not self.admins: raise RuntimeError("Bot setup is incomplete. Run first-run setup interactively.")
    def setup_interactive(self) -> None:
        if not sys.stdin.isatty(): raise RuntimeError("No configuration found. Start the bot once from an interactive terminal for setup.")
        print("\n=== V2Ray Monitor Seller — First Run Setup ===\nNo .env is used; settings are saved to data/config.json.\n")
        token = input("Seller Telegram Bot Token: ").strip()
        while not token: token = input("Seller Telegram Bot Token (required): ").strip()
        raw = input("Admin Telegram ID(s), comma-separated: ").strip()
        while not any(p.strip().isdigit() for p in raw.split(",")): raw = input("Admin Telegram ID(s) (required): ").strip()
        admins = [int(p.strip()) for p in raw.split(",") if p.strip().isdigit()]
        port = input("Web port [8090]: ").strip() or "8090"
        while not port.isdigit() or not 1 <= int(port) <= 65535: port = input("Web port (1-65535): ").strip()
        monitor_api = input("Monitor API URL [http://127.0.0.1:8091]: ").strip() or "http://127.0.0.1:8091"
        monitor_web = input("Monitor WebApp URL (optional): ").strip()
        card = input("Card number (optional): ").strip()
        holder = input("Card holder (optional): ").strip()
        join_channel = input("Force-join channel (optional, e.g. @channel): ").strip()
        join_url = input("Force-join URL (optional): ").strip()
        currency = input("Currency label [تومان]: ").strip() or "تومان"
        self.save(seller_bot_token=token, admin_ids=admins, web_port=int(port), webapp_url=f"http://127.0.0.1:{port}", monitor_api_url=monitor_api, monitor_webapp_url=monitor_web, card_number=card, card_holder=holder, force_join_channel=join_channel, force_join_channel_url=join_url, force_join_enabled=bool(join_channel), currency_label=currency)
        print(f"\nConfiguration saved securely to {CONFIG_FILE}")

settings = Settings()
