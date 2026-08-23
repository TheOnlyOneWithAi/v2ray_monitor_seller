from pathlib import Path

from cryptography.fernet import Fernet
from pydantic_settings import BaseSettings, SettingsConfigDict

APP_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = APP_DIR / ".env"


class Settings(BaseSettings):
    # Use an absolute path. systemd can start us from any working directory,
    # and the service account must be able to read the file itself.
    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    bot_token: str = ""
    admin_ids: str = ""
    web_port: int = 8090
    webapp_url: str = "http://127.0.0.1:8090"
    database_url: str = "sqlite+aiosqlite:///./data/seller.db"
    encryption_key: str = ""
    monitor_bot_token: str = ""
    monitor_bot_url: str = ""
    monitor_api_url: str = ""
    monitor_api_token: str = ""
    monitor_webapp_url: str = ""
    force_join_enabled: bool = True
    force_join_channel: str = ""
    force_join_channel_url: str = ""
    card_number: str = ""
    card_holder: str = ""
    payment_instructions: str = ""
    support_username: str = ""
    currency_label: str = "تومان"

    @property
    def admins(self):
        return {
            int(x.strip())
            for x in self.admin_ids.split(",")
            if x.strip().isdigit()
        }

    @property
    def key(self):
        return self.encryption_key.encode() if self.encryption_key else Fernet.generate_key()


settings = Settings()
