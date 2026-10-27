"""Keeps a copy of the catalog: fetched every few hours, cached on disk for the next start."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
import json
import logging
from pathlib import Path
from typing import Any

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    CACHE_FILENAME,
    CATALOG_SCHEMA,
    CONF_CATALOG_URL,
    DEFAULT_CATALOG_URL,
    DOMAIN,
    MAX_CATALOG_BYTES,
    UPDATE_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


class InvalidCatalog(ValueError):
    """The answer was not a catalog this version can read."""


@dataclass(frozen=True, slots=True)
class Catalog:
    """The catalog as fetched, kept as bytes so the panel gets it without a re-encode."""

    raw: bytes
    generated: str | None
    counts: dict[str, int]
    fetched: datetime
    source: str
    etag: str | None = None


def parse_catalog(raw: bytes) -> dict[str, Any]:
    """The decoded catalog, or InvalidCatalog when it is not one."""
    try:
        data = json.loads(raw)
    except ValueError as err:
        raise InvalidCatalog("not JSON") from err
    if not isinstance(data, dict) or not isinstance(data.get("repositories"), list):
        raise InvalidCatalog("no repositories list")
    if data.get("schema") != CATALOG_SCHEMA:
        raise InvalidCatalog(f"schema {data.get('schema')!r}, expected {CATALOG_SCHEMA}")
    return data


async def fetch_catalog(
    hass: HomeAssistant, url: str, etag: str | None = None
) -> tuple[bytes, str | None] | None:
    """The catalog's bytes and ETag, or None when the server says it has not changed."""
    session = async_get_clientsession(hass)
    headers = {"If-None-Match": etag} if etag else {}
    async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=120)) as response:
        if response.status == 304:
            return None
        response.raise_for_status()
        # content.read(n) returns what has arrived so far, not n bytes, so the
        # body is gathered chunk by chunk with the limit checked on the way.
        chunks: list[bytes] = []
        size = 0
        async for chunk in response.content.iter_chunked(1 << 16):
            size += len(chunk)
            if size > MAX_CATALOG_BYTES:
                raise InvalidCatalog("larger than the limit")
            chunks.append(chunk)
        return b"".join(chunks), response.headers.get("ETag")


def catalog_url(entry: ConfigEntry) -> str:
    """The address in use. Saved options decide once they exist; an empty one means the default."""
    if CONF_CATALOG_URL in entry.options:
        return entry.options[CONF_CATALOG_URL] or DEFAULT_CATALOG_URL
    return entry.data.get(CONF_CATALOG_URL) or DEFAULT_CATALOG_URL


class CatalogCoordinator(DataUpdateCoordinator[Catalog]):
    """The catalog, refreshed from its URL and remembered across restarts."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )
        self._cache = Path(hass.config.path(".storage", CACHE_FILENAME))
        self._meta = self._cache.with_name(f"{CACHE_FILENAME}.meta")
        # A refresh by hand can overlap the one at start; their saves take turns.
        self._save_lock = asyncio.Lock()

    @property
    def url(self) -> str:
        entry = self.config_entry
        return catalog_url(entry)

    def _build(self, raw: bytes, etag: str | None, fetched: datetime) -> Catalog:
        data = parse_catalog(raw)
        # Only numbers and a date travel on to the panel from the catalog's header.
        counts = data.get("counts") if isinstance(data.get("counts"), dict) else {}
        counts = {k: v for k, v in counts.items() if isinstance(k, str) and type(v) is int}
        generated = data.get("generated")
        if not isinstance(generated, str) or dt_util.parse_datetime(generated) is None:
            generated = None
        return Catalog(raw, generated, counts, fetched, self.url, etag)

    async def async_load_cache(self) -> Catalog | None:
        """Last run's catalog, if one was saved and came from the same URL."""

        def load() -> Catalog | None:
            try:
                meta = json.loads(self._meta.read_text())
                if meta.get("source") != self.url:
                    return None
                fetched = dt_util.parse_datetime(meta["fetched"]) or dt_util.utcnow()
                return self._build(self._cache.read_bytes(), meta.get("etag"), fetched)
            except FileNotFoundError:
                return None
            except (OSError, ValueError, KeyError, TypeError) as err:
                _LOGGER.debug("No usable catalog cache: %s", err)
                return None

        return await self.hass.async_add_executor_job(load)

    async def _async_save_cache(self, catalog: Catalog) -> None:
        def save() -> None:
            meta = {"source": catalog.source, "fetched": catalog.fetched.isoformat(), "etag": catalog.etag}
            self._cache.parent.mkdir(parents=True, exist_ok=True)
            for path, content in ((self._cache, catalog.raw), (self._meta, json.dumps(meta).encode())):
                tmp = path.with_suffix(".tmp")
                tmp.write_bytes(content)
                tmp.replace(path)

        try:
            async with self._save_lock:
                await self.hass.async_add_executor_job(save)
        except OSError as err:
            _LOGGER.warning("Could not save the catalog for the next start: %s", err)

    async def async_remove_cache(self) -> None:
        def remove() -> None:
            self._cache.unlink(missing_ok=True)
            self._meta.unlink(missing_ok=True)

        await self.hass.async_add_executor_job(remove)

    async def _async_update_data(self) -> Catalog:
        current = self.data if self.data and self.data.source == self.url else None
        try:
            result = await fetch_catalog(self.hass, self.url, current.etag if current else None)
        except (aiohttp.ClientError, TimeoutError) as err:
            raise UpdateFailed(f"Could not fetch the catalog from {self.url}: {err}") from err
        except InvalidCatalog as err:
            raise UpdateFailed(f"The catalog at {self.url} is not usable: {err}") from err
        now = dt_util.utcnow()
        if result is None and current:
            catalog = Catalog(current.raw, current.generated, current.counts, now, current.source, current.etag)
        else:
            if result is None:
                raise UpdateFailed("The server answered Not Modified without a catalog to keep")
            raw, etag = result
            try:
                catalog = await self.hass.async_add_executor_job(self._build, raw, etag, now)
            except InvalidCatalog as err:
                raise UpdateFailed(f"The catalog at {self.url} is not usable: {err}") from err
        await self._async_save_cache(catalog)
        return catalog
