from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://timelog:timelog@localhost:5442/timelog"
    app_tz: str = "Asia/Tehran"
    cookie_secure: bool = True          # False only for local http development / tests
    session_days: int = 30
    login_max_failures: int = 3         # per username ...
    login_window_minutes: int = 20      # ... in this window
    login_ip_max_failures: int = 10


settings = Settings()
