"""Constants for Bazaar."""

from datetime import timedelta
from typing import Final

DOMAIN: Final = "bazaar"
VERSION: Final = "0.1.3"

CONF_CATALOG_URL: Final = "catalog_url"
DEFAULT_CATALOG_URL: Final = "https://beolink.github.io/ha-bazaar/catalog.json"
CATALOG_SCHEMA: Final = 1
# The catalog is rebuilt once a night; a few looks a day catch it without
# asking the host more than it needs to.
UPDATE_INTERVAL: Final = timedelta(hours=6)
MAX_CATALOG_BYTES: Final = 64 * 1024 * 1024

PANEL_URL_PATH: Final = "bazaar"
PANEL_COMPONENT: Final = "bazaar-panel"
PANEL_ICON: Final = "mdi:store-search"
PANEL_TITLE: Final = "Bazaar"
STATIC_URL: Final = "/bazaar_static"
CATALOG_API_URL: Final = "/api/bazaar/catalog"
CACHE_FILENAME: Final = "bazaar.catalog.json"
