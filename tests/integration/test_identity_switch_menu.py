"""Segment AD2X: Review Robin's top bar offers *Switch to …* on a local run
with fake auth and a second fake account, and never otherwise."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from cordware.settings import identity_settings


def test_the_top_bar_offers_the_switch_on_a_local_run(
    mounted_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(identity_settings, "app_env", "local")
    monkeypatch.setattr(identity_settings, "allow_fake_auth", True)
    monkeypatch.setattr(identity_settings, "fake_auth_alt_email", "divya.petrova@example.edu")
    monkeypatch.setattr(identity_settings, "fake_auth_alt_name", "Divya Petrova")
    page = mounted_client.get("/reviewrobin/operator/sessions").text
    assert "data-switch-identity>Switch to Divya Petrova</a>" in page


def test_no_switch_without_fake_auth(
    mounted_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(identity_settings, "allow_fake_auth", False)
    page = mounted_client.get("/reviewrobin/operator/sessions").text
    assert "data-switch-identity" not in page
