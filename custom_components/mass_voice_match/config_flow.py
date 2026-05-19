import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector
import logging

from .const import (
    DOMAIN, CONF_MODEL, CONF_MUSIC_ASSISTANT_ENTRY, CONF_DEFAULT_MEDIA_PLAYER,
    CONF_THRESHOLD, CONF_FALLBACK_AGENT, DEFAULT_MODEL, DEFAULT_THRESHOLD
)

_LOGGER = logging.getLogger(__name__)

class MASSVoiceMatchFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None) -> FlowResult:
        """Handle initial configuration step."""
        if user_input is not None:
            await self.async_set_unique_id(DOMAIN)
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title="MASS Voice Match",
                data=user_input,
            )

        # Detect Music Assistant
        ma_entries = []
        for domain in ["mass", "music_assistant"]:
            ma_entries.extend(self.hass.config_entries.async_entries(domain))

        if not ma_entries:
            return self.async_abort(reason="no_ma")

        ma_options = [
            selector.SelectOptionDict(value=entry.entry_id, label=entry.title)
            for entry in ma_entries
        ]

        data_schema = vol.Schema({
            vol.Required(CONF_MUSIC_ASSISTANT_ENTRY): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=ma_options,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Required(CONF_DEFAULT_MEDIA_PLAYER): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="media_player")
            ),
            vol.Optional(CONF_FALLBACK_AGENT): selector.ConversationAgentSelector(),
            vol.Required(CONF_MODEL, default=DEFAULT_MODEL): str,
            vol.Required(CONF_THRESHOLD, default=DEFAULT_THRESHOLD): selector.NumberSelector(
                selector.NumberSelectorConfig(min=0.0, max=1.0, step=0.01)
            ),
        })

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for the configuration entry."""
        return OptionsFlowMASSVoiceMatch(config_entry)


class OptionsFlowMASSVoiceMatch(config_entries.OptionsFlow):
    """Handle options updates."""

    async def async_step_init(self, user_input=None) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        options_schema = vol.Schema({
            vol.Required(
                CONF_DEFAULT_MEDIA_PLAYER,
                default=self.config_entry.data.get(CONF_DEFAULT_MEDIA_PLAYER)
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="media_player")
            ),
            vol.Optional(
                CONF_FALLBACK_AGENT,
                default=self.config_entry.data.get(CONF_FALLBACK_AGENT)
            ): selector.ConversationAgentSelector(),
            vol.Required(
                CONF_THRESHOLD,
                default=self.config_entry.data.get(CONF_THRESHOLD, DEFAULT_THRESHOLD)
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(min=0.0, max=1.0, step=0.01)
            ),
            vol.Required(
                CONF_MODEL,
                default=self.config_entry.data.get(CONF_MODEL, DEFAULT_MODEL)
            ): str,
        })

        return self.async_show_form(
            step_id="init",
            data_schema=options_schema,
        )
