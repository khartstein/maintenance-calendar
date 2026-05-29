from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    database_url: str = "postgresql+psycopg://localhost/maintenance"
    session_secret: str = "dev-secret-do-not-use-in-prod"
    magic_link_base_url: str = "http://localhost:8000"

    anthropic_api_key: str = ""
    youtube_api_key: str = ""

    email_backend: str = "console"
    resend_api_key: str = ""
    email_from: str = "no-reply@localhost"

    app_env: str = "dev"


settings = Settings()
