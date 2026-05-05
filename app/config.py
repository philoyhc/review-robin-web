from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "local"
    app_name: str = "Review Robin Web"
    app_version: str = "dev"
    debug: bool = True

    allow_fake_auth: bool = False
    fake_auth_principal_id: str = "local-dev"
    fake_auth_email: str = "operator@example.edu"
    fake_auth_name: str = "Local Operator"

    database_url: str = "sqlite:///./review_robin_web.db"

    # Symmetric Fernet key (Base64-urlsafe-encoded 32 bytes) used to
    # encrypt operator SMTP passwords at rest. ``None`` is fail-loud at
    # encrypt / decrypt time rather than at startup so local dev / tests
    # that don't touch the operator Settings page don't need the key
    # set. Generate with ``cryptography.fernet.Fernet.generate_key()``.
    smtp_encryption_key: str | None = None

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
