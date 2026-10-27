"""Each Residential application built alone from its factory, unmounted
(`residentialapps/spec/applications.md`)."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from residentialapps.residentialops.main import create_app as ops_app
from residentialapps.supportlogs.main import create_app as supportlogs_app

APPS = [("residentialops", ops_app), ("supportlogs", supportlogs_app)]


def route_names(routes: list[object]) -> list[str]:
    """Every route name under ``routes``. FastAPI nests an included router
    behind its include context, as RRW's crawl reads it."""
    names: list[str] = []
    for route in routes:
        context = getattr(route, "include_context", None)
        if context is not None:
            names += route_names(context.included_router.routes)
        else:
            names.append(route.name)
    return names


@pytest.mark.parametrize(("name", "factory"), APPS)
def test_health_answers_without_sign_in(name: str, factory) -> None:
    response = TestClient(factory()).get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.parametrize(("name", "factory"), APPS)
def test_every_route_name_carries_the_application_prefix(name: str, factory) -> None:
    """Inside a mount `url_for` resolves through the host's router, where a
    name shared with another application finds the first mount."""
    app: FastAPI = factory()
    names = route_names(app.routes)
    assert f"{name}_health" in names
    assert all(n.startswith(f"{name}_") for n in names), names


@pytest.mark.parametrize(("name", "factory"), APPS)
@pytest.mark.parametrize("path", ["/docs", "/redoc", "/openapi.json"])
def test_no_schema_pages(name: str, factory, path: str) -> None:
    assert TestClient(factory()).get(path).status_code == 404


@pytest.mark.parametrize(("name", "factory"), APPS)
def test_each_build_is_a_new_application(name: str, factory) -> None:
    assert factory() is not factory()
