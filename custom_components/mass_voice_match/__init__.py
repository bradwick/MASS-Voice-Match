"""Initialize the MASS Voice Match integration."""
import logging
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

from .const import DOMAIN, CONF_MODEL
from .service import async_setup_services
from .embedding import build_index, load_index
from .storage import async_load_items, get_index_path

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up MASS Voice Match from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    # Set up services first so they are available for initial sync
    await async_setup_services(hass, entry)

    # Load items and index
    items = await async_load_items(hass)
    model_name = entry.data.get(CONF_MODEL)

    if items:
        index_path = get_index_path(hass)
        success = await hass.async_add_executor_job(
            load_index, hass, items, index_path
        )
        if not success:
            _LOGGER.info("Could not load index from disk, rebuilding...")
            await hass.async_add_executor_job(
                build_index, hass, items, model_name, index_path
            )
        _LOGGER.info("MASS Voice Match index initialized")
    else:
        _LOGGER.info("MASS Voice Match index empty, triggering initial sync")
        hass.async_create_task(hass.data[DOMAIN]["rebuild_index"]())

    # Set up conversation agent
    await hass.config_entries.async_forward_entry_setups(entry, ["conversation"])

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, ["conversation"])
    if unload_ok:
        hass.data.pop(DOMAIN, None)
    return unload_ok
