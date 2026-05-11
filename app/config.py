from pydantic import field_validator
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
    # Sandbox-only flags so the agent's local dev exercises the
    # 16A operator / sys-admin gates without coordinating env vars.
    # Honoured only when ``allow_fake_auth`` is also true AND the
    # resolved identity is ``is_fake=True``, so they're inert in
    # any deployed environment (where ``allow_fake_auth`` must
    # remain false per CLAUDE.md). Default-True keeps the agent's
    # local dev loop seamless under the 16A PR 1 operator gate.
    fake_auth_operator: bool = True
    fake_auth_sys_admin: bool = True

    # Strict-allowlist (Option C) bootstrap sources read once by
    # ``get_or_create_user`` on first sign-in. Email match is
    # case-insensitive. After first sign-in, the persisted
    # ``users.is_operator`` / ``users.is_sys_admin`` columns are
    # authoritative — removing an email here does NOT auto-revoke.
    # Revocation goes through the 16A PR 6 workspace UI.
    operator_emails: list[str] = []
    sys_admin_emails: list[str] = []

    # Optional contact line surfaced on the Request-access landing
    # page (16A PR 1). When set, the page renders a ``mailto:`` link;
    # when unset, falls back to generic copy.
    operator_contact_email: str | None = None

    @field_validator("operator_emails", "sys_admin_emails", mode="before")
    @classmethod
    def _split_email_list(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    database_url: str = "sqlite:///./review_robin_web.db"

    # Symmetric Fernet key (Base64-urlsafe-encoded 32 bytes) used to
    # encrypt operator SMTP passwords at rest. ``None`` is fail-loud at
    # encrypt / decrypt time rather than at startup so local dev / tests
    # that don't touch the operator Settings page don't need the key
    # set. Generate with ``cryptography.fernet.Fernet.generate_key()``.
    smtp_encryption_key: str | None = None

    # When True, ``audit.write_event`` raises on a detail-shape violation;
    # when False (production default), it logs a warning and writes the
    # row anyway. Auditing is observability — dropping events because of
    # a shape bug would hide the very mutations we're auditing. Tests flip
    # this on via ``tests/conftest.py`` so drift surfaces in CI before
    # deploy. See ``spec/architecture.md`` "Audit-event detail schema".
    audit_strict_mode: bool = False

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
