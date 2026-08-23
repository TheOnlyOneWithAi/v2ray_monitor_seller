from pydantic_settings import BaseSettings, SettingsConfigDict
from cryptography.fernet import Fernet

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    bot_token: str = ""
    admin_ids: str = ""
    web_port: int = 8090
    webapp_url: str = "http://127.0.0.1:8090"
    database_url: str = "sqlite+aiosqlite:///./data/seller.db"
    encryption_key: str = ""
    monitor_bot_token: str = ""
    monitor_bot_url: str = ""
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
        return {int(x.strip()) for x in self.admin_ids.split(',') if x.strip().isdigit()}

    @property
    def key(self):
        if self.encryption_key:
            return self.encryption_key.encode()
        return Fernet.generate_key()

settings = Settings()
