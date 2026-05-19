"""Services for the MASS Voice Match integration."""
import logging
import voluptuous as vol
from homeassistant.core import ServiceCall, HomeAssistant

from .const import (
    DOMAIN, SERVICE_REBUILD_INDEX, CONF_MUSIC_ASSISTANT_ENTRY, CONF_MODEL
)
from .embedding import build_index
from .sync import fetch_library_from_hass, build_items
from .storage import async_save_items, get_index_path

_LOGGER = logging.getLogger(__name__)

async def async_setup_services(hass: HomeAssistant, entry) -> None:
    """Set up services for the MASS Voice Match integration."""

    async def handle_rebuild_index(call: ServiceCall = None) -> None:
        """Rebuild the vector index from Music Assistant library."""
        ma_entry_id = entry.data.get(CONF_MUSIC_ASSISTANT_ENTRY)
        model_name = entry.data.get(CONF_MODEL)

        if not ma_entry_id:
            _LOGGER.error("No Music Assistant entry configured")
            return

        try:
            _LOGGER.info("Rebuilding MASS Voice Match index")

            # Fetch the library
            lib = await fetch_library_from_hass(hass, ma_entry_id)
            items = build_items(lib)

            if not items:
                _LOGGER.warning("No items found in Music Assistant library")
                return

            # Build and save index
            index_path = get_index_path(hass)
            await hass.async_add_executor_job(
                build_index, hass, items, model_name, index_path
            )

            # Save items to persistent storage
            await async_save_items(hass, items)

            _LOGGER.info("MASS Voice Match index rebuilt successfully with %d items", len(items))

        except Exception as err:
            _LOGGER.error("Error rebuilding MASS Voice Match index: %s", err)

    # Register rebuild service
    hass.services.async_register(
        DOMAIN,
        SERVICE_REBUILD_INDEX,
        handle_rebuild_index,
    )

    # Expose for internal use
    entry.async_on_unload(lambda: None) # Placeholder
    hass.data[DOMAIN]["rebuild_index"] = handle_rebuild_index
