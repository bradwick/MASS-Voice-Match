"""Storage handling for MASS Voice Match."""
import logging
import os
from homeassistant.helpers.storage import Store
from .const import DOMAIN, STORAGE_VERSION, STORAGE_KEY_ITEMS, INDEX_FILENAME

_LOGGER = logging.getLogger(__name__)

async def async_save_items(hass, items):
    """Save items to Home Assistant storage."""
    store = Store(hass, STORAGE_VERSION, STORAGE_KEY_ITEMS)
    await store.async_save(items)

async def async_load_items(hass):
    """Load items from Home Assistant storage."""
    store = Store(hass, STORAGE_VERSION, STORAGE_KEY_ITEMS)
    return await store.async_load()

def get_index_path(hass):
    """Get the path to the FAISS index file."""
    return hass.config.path("storage", INDEX_FILENAME)
