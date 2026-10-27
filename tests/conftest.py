"""Shared fixtures. The integration tests run against a real Home Assistant."""

from __future__ import annotations

import json

import pytest

pytest_plugins = ["pytest_homeassistant_custom_component"]

CATALOG = {
    "schema": 1,
    "generated": "2026-10-27T03:00:00Z",
    "counts": {"total": 2, "pending": 1, "integration": 1, "plugin": 1},
    "repositories": [
        {
            "repo": "someone/ha-thing",
            "category": "integration",
            "name": "Thing",
            "description": "A thing for Home Assistant",
            "stars": 12,
            "updated": "2026-10-20T10:00:00Z",
            "created": "2025-01-01T10:00:00Z",
            "releases": 3,
            "release": {"tag": "v1.2.0", "date": "2026-10-19T10:00:00Z"},
            "domain": "thing",
            "pending": {"pr": 12345, "since": "2026-09-01T10:00:00Z", "checks": "success"},
            "scan": {"ref": "abc", "files": 4, "lines": 300, "flags": []},
            "score": 80,
        },
        {
            "repo": "else/thing-card",
            "category": "plugin",
            "name": "Thing card",
            "stars": 0,
            "updated": "2024-01-01T10:00:00Z",
            "releases": 0,
            "release": None,
            "failed": ["topics"],
            "score": 10,
        },
    ],
}


@pytest.fixture
def catalog_bytes() -> bytes:
    return json.dumps(CATALOG).encode()


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(request, tmp_path):
    """Custom integrations and a config folder of the test's own for the Home Assistant tests.

    The catalog tests need no hass. Without the folder, the cache would be written
    into the test package's shared testing_config.
    """
    if "hass" in request.fixturenames:
        request.getfixturevalue("enable_custom_integrations")
        request.getfixturevalue("hass").config.config_dir = str(tmp_path)
    yield
