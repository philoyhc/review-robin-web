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

from pydantic_settings import BaseSettings, SettingsConfigDict


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

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


identity_settings = IdentitySettings()
