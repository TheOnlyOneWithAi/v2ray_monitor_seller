from pathlib import Path

from cryptography.fernet import Fernet
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

APP_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = APP_DIR / ".env"
DATA_DIR = APP_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)


class Settings(BaseSettings):
    """Seller configuration for the integrated Monitor installation."""

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    seller_bot_token: str = Field(default="", validation_alias="SELLER_BOT_TOKEN")
    bot_token: str = Field(default="", validation_alias="BOT_TOKEN")
    admin_ids: str = ""
    web_port: int = 8090
    webapp_url: str = "http://127.0.0.1:8090"
    database_url: str = f"sqlite+aiosqlite:///{DATA_DIR / 'seller.db'}"
    encryption_key: str = ""
    monitor_bot_token: str = ""
    monitor_bot_url: str = ""
    monitor_api_url: str = "http://127.0.0.1:8091"
    # Compatibility value only. It is never requested from the user and is
    # not written to .env. Monitor ignores the legacy header.
    monitor_api_token: str = "local-internal"
    monitor_webapp_url: str = ""
    force_join_enabled: bool = False
    force_join_channel: str = ""
    force_join_channel_url: str = ""
    card_number: str = ""
    card_holder: str = ""
    payment_instructions: str = ""
    support_username: str = ""
    currency_label: str = "تومان"

    @field_validator("web_port")
    @classmethod
    def valid_port(cls, value: int) -> int:
        if not 1 <= value <= 65535:
            raise ValueError("WEB_PORT must be between 1 and 65535")
        return value

    @property
    def token(self) -> str:
        return self.seller_bot_token.strip() or self.bot_token.strip()

    @property
    def admins(self) -> set[int]:
        out: set[int] = set()
        for value in self.admin_ids.split(","):
            value = value.strip()
            if value.isdigit():
                out.add(int(value))
        return out

    @property
    def key(self) -> bytes:
        return self.encryption_key.encode() if self.encryption_key else Fernet.generate_key()

    def validate_runtime(self) -> None:
        if not self.token:
            raise RuntimeError("SELLER_BOT_TOKEN is not configured")
        if not self.admins:
            raise RuntimeError("ADMIN_IDS is not configured")


settings = Settings()
