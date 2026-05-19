import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector
import logging

from .const import (
    DOMAIN, CONF_MODEL, CONF_SENSITIVITY, CONF_PROCESSING_MODE, 
    CONF_MAX_PROFILES, CONF_MUSIC_ASSISTANT, 
    DEFAULT_MODEL, DEFAULT_SENSITIVITY, DEFAULT_PROCESSING_MODE, DEFAULT_MAX_PROFILES
)

_LOGGER = logging.getLogger(__name__)

class VoiceMatchFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    async def async_step_user(self, user_input=None) -> FlowResult:
        """Handle initial configuration step."""
        if user_input is not None:
            await self.async_set_unique_id(DOMAIN)
            self._abort_if_unique_id_configured()
            
            # Start cache build in background after config is saved
            self.hass.async_create_task(
                self._build_cache(user_input.get(CONF_MUSIC_ASSISTANT))
            )
            
            return self.async_create_entry(
                title="Voice Match",
                data=user_input,
            )

        data_schema = vol.Schema({
            vol.Required(CONF_MUSIC_ASSISTANT): selector.EntitySelector(
                selector.EntitySelectorConfig(
                    domain="media_player",
                    integration="music_assistant",
                )
            ),
            vol.Required(CONF_MODEL, default=DEFAULT_MODEL): str,
            vol.Required(CONF_SENSITIVITY, default=DEFAULT_SENSITIVITY): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0.0,
                    max=1.0,
                    step=0.05,
                    unit_of_measurement="",
                )
            ),
            vol.Required(CONF_PROCESSING_MODE, default=DEFAULT_PROCESSING_MODE): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=["local", "hybrid"],
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Required(CONF_MAX_PROFILES, default=DEFAULT_MAX_PROFILES): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=1,
                    max=100,
                    unit_of_measurement="profiles",
                )
            ),
        })

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            description_placeholders={
                "music_assistant_help": "Select the Music Assistant media player",
                "model_help": "Sentence Transformer model for embeddings",
                "sensitivity_help": "Matching sensitivity (0.0-1.0, higher = stricter)",
                "mode_help": "Processing mode: local (on device) or hybrid",
                "profiles_help": "Maximum number of speaker profiles",
            }
        )

    async def _build_cache(self, music_assistant_entity):
        """Build the voice match cache from Music Assistant library."""
        try:
            from .sync import fetch_library_from_hass, build_items
            from .embedding import build_index
            
            if not music_assistant_entity:
                _LOGGER.warning("No Music Assistant selected, skipping cache build")
                return
            
            _LOGGER.info("Starting Voice Match cache build from %s", music_assistant_entity)
            
            # Fetch library from Music Assistant integration
            lib = await fetch_library_from_hass(self.hass, music_assistant_entity)
            items = build_items(lib)
            
            # Build the vector index
            await self.hass.async_add_executor_job(build_index, items)
            
            _LOGGER.info("Voice Match cache build completed. Indexed %d items", len(items))
            
        except Exception as err:
            _LOGGER.error("Failed to build Voice Match cache: %s", err)

    @staticmethod
    def async_get_options_flow(config_entry):
        """Get the options flow for the configuration entry."""
        return OptionsFlowVoiceMatch(config_entry)


class OptionsFlowVoiceMatch(config_entries.OptionsFlow):
    """Handle options updates."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        options_schema = vol.Schema({
            vol.Optional(
                CONF_SENSITIVITY,
                default=self.config_entry.options.get(CONF_SENSITIVITY, 
                    self.config_entry.data.get(CONF_SENSITIVITY, DEFAULT_SENSITIVITY))
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0.0,
                    max=1.0,
                    step=0.05,
                    unit_of_measurement="",
                )
            ),
            vol.Optional(
                CONF_PROCESSING_MODE,
                default=self.config_entry.options.get(CONF_PROCESSING_MODE,
                    self.config_entry.data.get(CONF_PROCESSING_MODE, DEFAULT_PROCESSING_MODE))
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=["local", "hybrid"],
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Optional(
                CONF_MAX_PROFILES,
                default=self.config_entry.options.get(CONF_MAX_PROFILES,
                    self.config_entry.data.get(CONF_MAX_PROFILES, DEFAULT_MAX_PROFILES))
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=1,
                    max=100,
                    unit_of_measurement="profiles",
                )
            ),
        })

        return self.async_show_form(
            step_id="init",
            data_schema=options_schema,
        )
