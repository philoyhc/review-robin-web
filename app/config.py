from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


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
    #
    # ``NoDecode`` suppresses pydantic-settings's default
    # JSON-decode pass for complex-typed env vars — without it,
    # ``OPERATOR_EMAILS=alice@example.edu`` would fail because
    # the raw value isn't JSON. The ``_split_email_list``
    # validator below handles comma-separated parsing instead.
    operator_emails: Annotated[list[str], NoDecode] = []
    sys_admin_emails: Annotated[list[str], NoDecode] = []

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

    # Root log level for the structured-logging setup configured by
    # ``app.logging_config.configure_logging`` (called from
    # ``create_app``). Any standard ``logging`` level name; an
    # unrecognised value falls back to ``INFO``.
    log_level: str = "INFO"

    # Symmetric Fernet key (Base64-urlsafe-encoded 32 bytes) used to
    # encrypt operator SMTP passwords at rest. ``None`` is fail-loud at
    # encrypt / decrypt time rather than at startup so local dev / tests
    # that don't touch the operator Settings page don't need the key
    # set. Generate with ``cryptography.fernet.Fernet.generate_key()``.
    smtp_encryption_key: str | None = None

    # Segment 18G Part 1 — minimum lead time (hours) the operator must
    # leave between "now" and the ``scheduled_activate_at`` they set at
    # save. Covers operational fan-out headroom for the
    # 1,200-reviewer pilot case + operator coordination. Per-deployment
    # tunable so a workshop-style flow can lower it. Per
    # ``spec/lifecycle.md`` §8.2.1 + the Part 1 plan section.
    scheduled_operational_lead_hours: int = 1

    # Segment 18G Part 2 — minimum gap (hours) between an auto-send
    # invitation's resolved fire moment and ``scheduled_activate_at``
    # (Start). Enforced per-entry at save: every ``invite_offsets``
    # entry must satisfy ``|offset| ≥ this floor`` so reviewers get
    # at least this much notice between the invite landing and the
    # session opening. Per ``spec/lifecycle.md`` §8.2.1 + the Part 2
    # plan section.
    reviewer_notice_min_hours: int = 1

    # When True, ``audit.write_event`` raises on a detail-shape violation;
    # when False (production default), it logs a warning and writes the
    # row anyway. Auditing is observability — dropping events because of
    # a shape bug would hide the very mutations we're auditing. Tests flip
    # this on via ``tests/conftest.py`` so drift surfaces in CI before
    # deploy. See ``spec/architecture.md`` "Audit-event detail schema".
    audit_strict_mode: bool = False

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


class ConfigurationError(RuntimeError):
    """A critical setting is missing or unsafe for a deployed
    (non-local) environment. Raised at startup so a misconfigured
    deploy fails fast rather than surfacing as a confusing runtime
    symptom later."""


def validate_critical_settings(s: "Settings") -> None:
    """Fail-fast guard, run from ``create_app`` before the app
    accepts traffic. A no-op when ``app_env == "local"`` — the
    checks below only matter for a deployed environment.

    Segment 14A PR 6a. The check set is deliberately minimal; see
    ``docs/security_posture.md`` for the settings that are guarded
    elsewhere (e.g. ``allow_fake_auth`` via the auth layer).
    """
    if s.app_env == "local":
        return
    problems: list[str] = []
    if not s.operator_emails and not s.sys_admin_emails:
        problems.append(
            "operator_emails and sys_admin_emails are both empty — "
            "no one could sign in to this environment"
        )
    if problems:
        raise ConfigurationError(
            f"Critical configuration problem(s) for app_env={s.app_env!r}: "
            + "; ".join(problems)
        )


settings = Settings()
