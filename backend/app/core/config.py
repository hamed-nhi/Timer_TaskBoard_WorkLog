from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", env_ignore_empty=True)

    database_url: str = "postgresql+psycopg://timelog:timelog@localhost:5442/timelog"
    app_tz: str = "Asia/Tehran"
    cookie_secure: bool | None = None   # Auto from request scheme; explicit True/False overrides it
    session_days: int = 90
    login_max_failures: int = 3         # per username ...
    login_window_minutes: int = 20      # ... in this window
    login_ip_max_failures: int = 10


settings = Settings()
