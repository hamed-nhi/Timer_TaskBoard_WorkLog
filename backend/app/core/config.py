from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", env_ignore_empty=True)

    database_url: str = "postgresql+psycopg://timelog:timelog@localhost:5442/timelog"
    app_tz: str = "Asia/Tehran"
    cookie_secure: bool | None = None   # Auto from request scheme; explicit True/False overrides it
    session_days: int = 90
    google_sheets_service_email: str = ""
    login_max_failures: int = 3         # per username ...
    login_window_minutes: int = 20      # ... in this window
    login_ip_max_failures: int = 10
    login_ip_burst: int = Field(default=30, ge=1, le=10000)
    login_ip_hourly: int = Field(default=120, ge=1, le=100000)
    login_global_per_minute: int = Field(default=300, ge=1, le=100000)
    captcha_provider: Literal["none", "arcaptcha"] = "none"
    arcaptcha_site_key: str = ""
    arcaptcha_secret_key: str = ""

    @model_validator(mode="after")
    def captcha_credentials(self):
        if self.captcha_provider == "arcaptcha" and not (self.arcaptcha_site_key.strip() and self.arcaptcha_secret_key.strip()):
            raise ValueError("Arcaptcha requires both site and secret keys")
        return self


settings = Settings()
