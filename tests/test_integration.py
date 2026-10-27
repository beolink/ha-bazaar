"""Bazaar in a real Home Assistant: setup, panel, the catalog API, websocket and cache."""

from __future__ import annotations

from http import HTTPStatus
import json

import aiohttp
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.bazaar.const import (
    CACHE_FILENAME,
    CONF_CATALOG_URL,
    DEFAULT_CATALOG_URL,
    DOMAIN,
    PANEL_URL_PATH,
)
from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

URL = DEFAULT_CATALOG_URL


async def _setup(hass: HomeAssistant, url: str = URL) -> MockConfigEntry:
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_CATALOG_URL: url}, title="Bazaar")
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_config_flow_creates_entry(hass, aioclient_mock: AiohttpClientMocker, catalog_bytes):
    aioclient_mock.get(URL, content=catalog_bytes)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_CATALOG_URL: URL})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    # The default is not stored, so a later release can move it.
    assert result["data"] == {}


async def test_config_flow_errors(hass, aioclient_mock: AiohttpClientMocker):
    aioclient_mock.get("https://down.example/catalog.json", exc=aiohttp.ClientError())
    aioclient_mock.get("https://wrong.example/catalog.json", content=b'{"schema": 99, "repositories": []}')
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_CATALOG_URL: "https://down.example/catalog.json"}
    )
    assert result["errors"] == {"base": "cannot_connect"}
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_CATALOG_URL: "https://wrong.example/catalog.json"}
    )
    assert result["errors"] == {"base": "invalid_catalog"}


async def test_single_instance(hass, aioclient_mock: AiohttpClientMocker, catalog_bytes):
    aioclient_mock.get(URL, content=catalog_bytes)
    await _setup(hass)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


async def test_panel_and_catalog_api(
    hass, aioclient_mock: AiohttpClientMocker, catalog_bytes, hass_client, hass_read_only_access_token
):
    aioclient_mock.get(URL, content=catalog_bytes)
    entry = await _setup(hass)
    assert entry.state is ConfigEntryState.LOADED

    panel = hass.data["frontend_panels"][PANEL_URL_PATH]
    assert panel.require_admin is True
    assert panel.config["_panel_custom"]["name"] == "bazaar-panel"
    assert panel.config["_panel_custom"]["module_url"].startswith("/bazaar_static/bazaar-panel.js?v=")

    client = await hass_client()
    response = await client.get("/api/bazaar/catalog")
    assert response.status == HTTPStatus.OK
    assert json.loads(await response.read()) == json.loads(catalog_bytes)

    for path in ("/bazaar_static/bazaar-panel.js", "/bazaar_static/bazaar-catalog.js"):
        response = await client.get(path)
        assert response.status == HTTPStatus.OK, path

    reader = await hass_client(hass_read_only_access_token)
    response = await reader.get("/api/bazaar/catalog")
    assert response.status == HTTPStatus.FORBIDDEN

    assert await hass.config_entries.async_unload(entry.entry_id)
    assert PANEL_URL_PATH not in hass.data["frontend_panels"]


async def test_websocket_info_and_refresh(
    hass, aioclient_mock: AiohttpClientMocker, catalog_bytes, hass_ws_client
):
    aioclient_mock.get(URL, content=catalog_bytes)
    await _setup(hass)
    ws = await hass_ws_client(hass)
    await ws.send_json({"id": 1, "type": "bazaar/info"})
    msg = await ws.receive_json()
    assert msg["success"]
    assert msg["result"]["generated"] == "2026-10-27T03:00:00Z"
    assert msg["result"]["counts"]["total"] == 2
    assert msg["result"]["last_update_success"] is True
    assert msg["result"]["hacs"] is False

    aioclient_mock.clear_requests()
    aioclient_mock.get(URL, exc=aiohttp.ClientError())
    await ws.send_json({"id": 2, "type": "bazaar/refresh"})
    msg = await ws.receive_json()
    assert msg["success"]
    # A failed fetch keeps the last catalog and says why.
    assert msg["result"]["last_update_success"] is False
    assert msg["result"]["error"]
    assert msg["result"]["counts"]["total"] == 2


async def test_websocket_needs_admin(hass, aioclient_mock, catalog_bytes, hass_ws_client, hass_read_only_access_token):
    aioclient_mock.get(URL, content=catalog_bytes)
    await _setup(hass)
    ws = await hass_ws_client(hass, hass_read_only_access_token)
    await ws.send_json({"id": 1, "type": "bazaar/info"})
    msg = await ws.receive_json()
    assert not msg["success"]
    assert msg["error"]["code"] == "unauthorized"


async def test_cache_carries_over_a_restart_without_network(
    hass, aioclient_mock: AiohttpClientMocker, catalog_bytes, hass_client
):
    aioclient_mock.get(URL, content=catalog_bytes, headers={"ETag": '"v1"'})
    entry = await _setup(hass)
    cache = hass.config.path(".storage", CACHE_FILENAME)
    with open(cache, "rb") as handle:
        assert json.loads(handle.read()) == json.loads(catalog_bytes)
    assert await hass.config_entries.async_unload(entry.entry_id)

    aioclient_mock.clear_requests()
    aioclient_mock.get(URL, exc=aiohttp.ClientError())
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
    client = await hass_client()
    response = await client.get("/api/bazaar/catalog")
    assert response.status == HTTPStatus.OK
    assert json.loads(await response.read())["counts"]["total"] == 2


async def test_not_modified_keeps_the_catalog(hass, aioclient_mock: AiohttpClientMocker, catalog_bytes):
    aioclient_mock.get(URL, content=catalog_bytes, headers={"ETag": '"v1"'})
    entry = await _setup(hass)
    coordinator = entry.runtime_data
    first = coordinator.data
    aioclient_mock.clear_requests()
    aioclient_mock.get(URL, status=304)
    await coordinator.async_refresh()
    assert coordinator.last_update_success
    assert coordinator.data.raw == first.raw
    assert aioclient_mock.mock_calls[-1][3] == {"If-None-Match": '"v1"'}


async def test_no_network_and_no_cache_retries(hass, aioclient_mock: AiohttpClientMocker):
    aioclient_mock.get(URL, exc=aiohttp.ClientError())
    entry = await _setup(hass)
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_removing_the_entry_removes_the_cache(hass, aioclient_mock, catalog_bytes):
    aioclient_mock.get(URL, content=catalog_bytes)
    entry = await _setup(hass)
    cache = hass.config.path(".storage", CACHE_FILENAME)
    assert await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()
    import os

    assert not os.path.exists(cache)


async def test_large_catalog_streamed_in_chunks(hass, aiohttp_server, hass_client):
    """The whole body is read, however the server splits it."""
    from aiohttp import web

    big = {
        "schema": 1, "generated": "2026-10-27T03:00:00Z", "counts": {"total": 5000, "pending": 0},
        "repositories": [{"repo": f"owner/repo{i}", "category": "integration", "description": "x" * 400}
                         for i in range(5000)],
    }
    body = json.dumps(big).encode()

    async def handler(request):
        response = web.StreamResponse()
        await response.prepare(request)
        for i in range(0, len(body), 7000):
            await response.write(body[i:i + 7000])
        await response.write_eof()
        return response

    app = web.Application()
    app.router.add_get("/catalog.json", handler)
    server = await aiohttp_server(app)
    url = str(server.make_url("/catalog.json"))
    entry = await _setup(hass, url)
    assert entry.state is ConfigEntryState.LOADED
    assert len(entry.runtime_data.data.raw) == len(body)


async def test_refresh_is_scheduled(hass, aioclient_mock: AiohttpClientMocker, catalog_bytes, freezer):
    from datetime import timedelta

    from pytest_homeassistant_custom_component.common import async_fire_time_changed

    aioclient_mock.get(URL, content=catalog_bytes)
    await _setup(hass)
    assert aioclient_mock.call_count == 1
    freezer.tick(timedelta(hours=6, minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert aioclient_mock.call_count == 2


async def test_header_fields_are_sanitized(hass, aioclient_mock: AiohttpClientMocker, hass_ws_client):
    hostile = {
        "schema": 1, "generated": "<img src=x>", "counts": {"total": "<img src=x>", "pending": 3},
        "repositories": [],
    }
    aioclient_mock.get(URL, content=json.dumps(hostile).encode())
    await _setup(hass)
    ws = await hass_ws_client(hass)
    await ws.send_json({"id": 1, "type": "bazaar/info"})
    result = (await ws.receive_json())["result"]
    assert result["generated"] is None
    assert result["counts"] == {"pending": 3}


async def test_options_switch_address_and_back(hass, aioclient_mock: AiohttpClientMocker, catalog_bytes):
    other = "https://mirror.example/catalog.json"
    aioclient_mock.get(URL, content=catalog_bytes)
    aioclient_mock.get(other, content=catalog_bytes)
    entry = await _setup(hass, other)
    assert entry.runtime_data.url == other

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["data_schema"]({})[CONF_CATALOG_URL] == other
    result = await hass.config_entries.options.async_configure(result["flow_id"], {CONF_CATALOG_URL: URL})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert entry.options == {CONF_CATALOG_URL: ""}
    assert entry.runtime_data.url == URL
