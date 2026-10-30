from typing import Annotated

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

from cordware.identity import app_env


class Settings(BaseSettings):
    # `APP_ENV`, `ALLOW_FAKE_AUTH` and the fake identity's
    # `FAKE_AUTH_*` fields (principal id, email, name, tenant, UPN, mail)
    # are Cordware's
    # (`cordware/settings.py`, segment 21C), read through
    # `cordware.identity`; the role switches below stay RRW's.
    app_version: str = "dev"

    # Sandbox-only flags so the agent's local dev exercises the
    # 16A operator / sys-admin gates without coordinating env vars.
    # Honoured only for an identity with ``is_fake=True``, which
    # Cordware supplies only with fake auth on, and refuses fake auth
    # outside ``APP_ENV=local``, so they're inert in any deployed
    # environment. Default-True keeps the agent's
    # local dev loop seamless under the 16A PR 1 operator gate.
    fake_auth_operator: bool = True
    fake_auth_sys_admin: bool = True
    # `SUPER_ADMIN_EMAILS` and `FAKE_AUTH_SUPER_ADMIN` are Cordware's
    # too: super-admin is the platform role (segment 21C C3,
    # ``app/auth/roles.py``).

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

    # Optional contact address on ``/about``'s "getting access" note,
    # the signed-in-but-no-access landing since 18R Item 6 retired
    # ``/request-access``. When set, the note renders a ``mailto:``
    # link; when unset, it falls back to generic copy.
    operator_contact_email: str | None = None

    @field_validator("operator_emails", "sys_admin_emails", mode="before")
    @classmethod
    def _split_email_list(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    # `RRW_DATABASE_URL`, app-prefixed like Residential's
    # `RES_OPS_DATABASE_URL` / `RES_SUPPORT_DATABASE_URL`, so one shared
    # process reads unambiguous names. Within one source it wins over the
    # older `DATABASE_URL`, which still works for local `.env` files and
    # CI; the environment is read before `.env`, as for every setting.
    database_url: str = Field(
        default="sqlite:///./review_robin_web.db",
        validation_alias=AliasChoices("RRW_DATABASE_URL", "DATABASE_URL"),
    )

    # Symmetric Fernet key (Base64-urlsafe-encoded 32 bytes) used to
    # encrypt operator SMTP passwords at rest. ``None`` is fail-loud at
    # encrypt / decrypt time rather than at startup so local dev / tests
    # that don't touch the operator Settings page don't need the key
    # set. Generate with ``cryptography.fernet.Fernet.generate_key()``.
    smtp_encryption_key: str | None = None

    # Minimum lead time (hours) the operator must leave between "now"
    # and the ``scheduled_activate_at`` they set at save, and between
    # "now" and each resolved auto-send invite / reminder fire moment.
    # Covers operational fan-out headroom for a large reviewer roster
    # + operator coordination. Per-deployment tunable so a
    # workshop-style flow can lower it. Per ``spec/settings_inventory.md``
    # §8 (the rule itself is in §2).
    scheduled_operational_lead_hours: int = 1

    # Minimum ``|offset|`` (hours) of each auto-send entry. Enforced
    # per-entry at save while the entry's anchor is set (Start for
    # ``invite_offsets``, End for ``reminder_offsets``; an unanchored
    # entry is inert): ``|offset| ≥ this floor``, so an invite lands
    # at least this long before Start and a reminder at least this
    # long before End. Per ``spec/settings_inventory.md`` §8 (the rule
    # itself is in §2).
    reviewer_notice_min_hours: int = 1

    # Segment 19N — Rehydrate is gated off by default. The pipeline
    # works for unproblematic cases, but not every detail is settled:
    # a responses row the regenerated rules cannot place is currently
    # dropped with a warning nobody surfaces (`SC-40`), against a spec
    # that promises no response is lost. Nobody has run it on real
    # data, so the surface closes until 19N lands the
    # dropped-responses export. The machinery stays wired and tested —
    # the test suite sets ``REHYDRATE_ENABLED=true`` — so re-opening
    # it is this one flag.
    rehydrate_enabled: bool = False

    # When True, ``audit.write_event`` raises on a detail-shape violation;
    # when False (production default), it issues a ``warnings.warn`` and
    # writes the row anyway. Auditing is observability — dropping events because of
    # a shape bug would hide the very mutations we're auditing. Tests flip
    # this on via ``tests/conftest.py`` so drift surfaces in CI before
    # deploy. See ``spec/architecture.md`` "Audit-event detail schema".
    audit_strict_mode: bool = False

    model_config = SettingsConfigDict(
        env_file=".env", extra="ignore", populate_by_name=True
    )


class ConfigurationError(RuntimeError):
    """A critical setting is missing or unsafe for a deployed
    (non-local) environment. Raised at startup so a misconfigured
    deploy fails fast rather than surfacing as a confusing runtime
    symptom later."""


def validate_critical_settings(s: "Settings", env: str | None = None) -> None:
    """Fail-fast guard, run from ``create_app`` before the app
    accepts traffic. A no-op when the environment is ``local`` — the
    checks below only matter for a deployed environment.

    ``env`` is `APP_ENV`, Cordware's (``cordware.identity.app_env``,
    segment 21C); a test passes it in.

    Segment 14A PR 6a. The check set is deliberately minimal; see
    ``docs/security_posture.md`` for the settings that are guarded
    elsewhere (fake auth by the host's guard).
    """
    env = app_env() if env is None else env
    if env == "local":
        return
    problems: list[str] = []
    if not s.operator_emails and not s.sys_admin_emails:
        problems.append(
            "operator_emails and sys_admin_emails are both empty — "
            "no one could sign in to this environment"
        )
    if problems:
        raise ConfigurationError(
            f"Critical configuration problem(s) for app_env={env!r}: "
            + "; ".join(problems)
        )


settings = Settings()
