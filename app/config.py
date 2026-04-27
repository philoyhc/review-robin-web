from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "local"
    app_name: str = "Review Robin Web"
    debug: bool = True

    allow_fake_auth: bool = False
    fake_auth_principal_id: str = "local-dev"
    fake_auth_email: str = "operator@example.edu"
    fake_auth_name: str = "Local Operator"

    database_url: str = "sqlite:///./review_robin_web.db"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
