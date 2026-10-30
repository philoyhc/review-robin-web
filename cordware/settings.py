"""The platform settings Cordware owns and every application reads
through `cordware.identity` (v0.8 §3, "Environment, guard and local
testing switches").

Each keeps the name and default it had in RRW's `app/config.py`, and is
read from the one repository-root `.env`, a shell value overriding the
file. Separate from `cordware.main`'s `CordwareSettings`: applications
import this module, never the host's entry point, which builds the host
when imported.
"""

from __future__ import annotations

from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class IdentitySettings(BaseSettings):
    # The deployment's environment. Only `local` permits fake auth (the
    # host's guard, `cordware.main.create_app`).
    app_env: str = "local"

    # The baked-in localhost account (v0.8 §3, "Local fake auth"). Never
    # on outside `APP_ENV=local`: the host refuses to start.
    allow_fake_auth: bool = False
    fake_auth_principal_id: str = "local-dev"
    fake_auth_email: str = "operator@example.edu"
    fake_auth_name: str = "Local Operator"
    # The fake account's tenant, UPN and primary email; a blank UPN or mail
    # is the fake email. Set one apart to test an alias locally.
    fake_auth_tenant_id: str = "local-tenant"
    fake_auth_upn: str = ""
    fake_auth_mail: str = ""

    # The platform super-admin (v0.8 §3): a comma-separated email list,
    # set only by the deployer. `NoDecode` keeps pydantic-settings from
    # reading the raw value as JSON; the validator splits it.
    super_admin_emails: Annotated[list[str], NoDecode] = []
    # Folds the fake account into the effective list while fake auth is
    # on, so the localhost user is a super-admin with no list set.
    fake_auth_super_admin: bool = True

    @field_validator("super_admin_emails", mode="before")
    @classmethod
    def _split_email_list(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


identity_settings = IdentitySettings()
