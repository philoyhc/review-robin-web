"""Unit coverage for the fail-fast configuration guard.

Segment 14A PR 6a. ``validate_critical_settings`` runs from
``create_app`` before the app accepts traffic. In a deployed
(non-local) environment it refuses to boot when both operator and
sys-admin allowlists are empty — a state in which no one could
sign in. Local development is exempt.
"""
from __future__ import annotations

import pytest

from app.config import ConfigurationError, Settings, validate_critical_settings


def _settings(**overrides: object) -> Settings:
    base: dict[str, object] = {
        "app_env": "production",
        "operator_emails": [],
        "sys_admin_emails": [],
    }
    base.update(overrides)
    return Settings(**base)  # type: ignore[arg-type]


def test_local_env_skips_the_check() -> None:
    # Empty allowlists are fine locally — fake auth covers dev.
    validate_critical_settings(_settings(app_env="local"))


def test_deployed_env_with_empty_allowlists_fails() -> None:
    with pytest.raises(ConfigurationError) as excinfo:
        validate_critical_settings(_settings())
    assert "operator_emails" in str(excinfo.value)
    assert "production" in str(excinfo.value)


def test_deployed_env_passes_with_operator_allowlist() -> None:
    validate_critical_settings(
        _settings(operator_emails=["op@example.edu"])
    )


def test_deployed_env_passes_with_sys_admin_allowlist() -> None:
    validate_critical_settings(
        _settings(sys_admin_emails=["admin@example.edu"])
    )
