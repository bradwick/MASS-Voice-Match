import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
import logging

from .const import DOMAIN, CONF_MODEL, CONF_SENSITIVITY, CONF_PROCESSING_MODE, CONF_MAX_PROFILES

_LOGGER = logging.getLogger(__name__)

class VoiceMatchFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    async def async_step_user(self, user_input=None) -> FlowResult:
        """Handle initial configuration step."""
        if user_input is not None:
            await self.async_set_unique_id(DOMAIN)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title="Voice Match",
                data=user_input,
            )

        data_schema = vol.Schema({
            vol.Required(CONF_MODEL, default="sentence-transformers/all-MiniLM-L6-v2"): str,
            vol.Required(CONF_SENSITIVITY, default=0.7): vol.Range(min=0.0, max=1.0),
            vol.Required(CONF_PROCESSING_MODE, default="local"): vol.In(["local", "hybrid"]),
            vol.Required(CONF_MAX_PROFILES, default=10): vol.Range(min=1, max=100),
        })

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            description_placeholders={
                "model_help": "Sentence Transformer model for embeddings",
                "sensitivity_help": "Matching sensitivity (0.0-1.0, higher = stricter)",
                "mode_help": "Processing mode: local (on device) or hybrid",
                "profiles_help": "Maximum number of speaker profiles",
            }
        )

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
                    self.config_entry.data.get(CONF_SENSITIVITY, 0.7))
            ): vol.Range(min=0.0, max=1.0),
            vol.Optional(
                CONF_PROCESSING_MODE,
                default=self.config_entry.options.get(CONF_PROCESSING_MODE,
                    self.config_entry.data.get(CONF_PROCESSING_MODE, "local"))
            ): vol.In(["local", "hybrid"]),
            vol.Optional(
                CONF_MAX_PROFILES,
                default=self.config_entry.options.get(CONF_MAX_PROFILES,
                    self.config_entry.data.get(CONF_MAX_PROFILES, 10))
            ): vol.Range(min=1, max=100),
        })

        return self.async_show_form(
            step_id="init",
            data_schema=options_schema,
        )
