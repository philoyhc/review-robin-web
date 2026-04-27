from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "local"
    app_name: str = "Review Robin Web"
    debug: bool = True

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
