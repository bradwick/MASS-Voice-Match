"""Conversation agent for MASS Voice Match."""
import logging
from typing import Literal
import re

from homeassistant.components import conversation
from homeassistant.core import HomeAssistant
from homeassistant.helpers import intent
from homeassistant.config_entries import ConfigEntry

from .const import (
    DOMAIN, CONF_MUSIC_ASSISTANT_ENTRY, CONF_DEFAULT_MEDIA_PLAYER,
    CONF_THRESHOLD, CONF_FALLBACK_AGENT, CONF_MODEL
)
from .embedding import search
from .sync import get_ma_domain

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> bool:
    """Set up conversation agent from a config entry."""
    agent = MASSVoiceMatchConversationAgent(hass, entry)
    conversation.async_set_agent(hass, entry, agent)
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload conversation agent."""
    conversation.async_unset_agent(hass, entry)
    return True

class MASSVoiceMatchConversationAgent(conversation.AbstractConversationAgent):
    """MASS Voice Match conversation agent."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the agent."""
        self.hass = hass
        self.entry = entry

    @property
    def supported_languages(self) -> list[str] | Literal["*"]:
        """Return a list of supported languages."""
        return "*"

    async def async_process(
        self, user_input: conversation.ConversationInput
    ) -> conversation.ConversationResult:
        """Process a sentence."""
        text = user_input.text
        _LOGGER.debug("Processing text: %s", text)

        # Patterns to strip
        patterns = [
            r"^(?:could you |can you |please |i want to )?(?:play|listen to|start|put on) (.+)$",
            r"^(.+)$"
        ]

        query = text
        matched_prefix = False
        for pattern in patterns:
            match = re.match(pattern, text, re.IGNORECASE)
            if match:
                if pattern != patterns[-1]:
                    matched_prefix = True
                query = match.group(1).strip()
                break

        try:
            # Use current options if available, otherwise data
            threshold = self.entry.options.get(CONF_THRESHOLD,
                                             self.entry.data.get(CONF_THRESHOLD, 0.5))
            model_name = self.entry.options.get(CONF_MODEL,
                                              self.entry.data.get(CONF_MODEL))

            item, score = await self.hass.async_add_executor_job(
                search, self.hass, query, model_name
            )

            actual_threshold = threshold if matched_prefix else max(threshold, 0.7)

            if score < actual_threshold:
                 _LOGGER.debug("Match score %s below threshold %s. Falling back.", score, actual_threshold)
                 return await self._async_fallback(user_input)

            _LOGGER.info("Matched '%s' to '%s' (score: %s)", query, item["name"], score)

            ma_domain = get_ma_domain(self.hass)
            ma_entry_id = self.entry.data.get(CONF_MUSIC_ASSISTANT_ENTRY)
            player_id = self.entry.options.get(CONF_DEFAULT_MEDIA_PLAYER,
                                             self.entry.data.get(CONF_DEFAULT_MEDIA_PLAYER))

            await self.hass.services.async_call(
                "media_player",
                "play_media",
                {
                    "entity_id": player_id,
                    "media_content_id": item["uri"],
                    "media_content_type": item["type"],
                },
                blocking=True,
            )

            intent_response = intent.IntentResponse(language=user_input.language)
            intent_response.async_set_speech(f"Playing {item['name']}")
            return conversation.ConversationResult(
                response=intent_response,
                conversation_id=user_input.conversation_id,
            )

        except Exception as err:
            _LOGGER.error("Error in conversation agent: %s", err, exc_info=True)
            return await self._async_fallback(user_input)

    async def _async_fallback(
        self, user_input: conversation.ConversationInput
    ) -> conversation.ConversationResult:
        """Pass the input to the fallback conversation agent."""
        fallback_agent_id = self.entry.options.get(CONF_FALLBACK_AGENT,
                                                 self.entry.data.get(CONF_FALLBACK_AGENT))

        if not fallback_agent_id:
             _LOGGER.debug("No fallback agent configured.")
             return conversation.ConversationResult(
                response=intent.IntentResponse(language=user_input.language),
                conversation_id=user_input.conversation_id,
            )

        _LOGGER.debug("Forwarding to fallback agent: %s", fallback_agent_id)
        return await conversation.async_converse(
            hass=self.hass,
            text=user_input.text,
            conversation_id=user_input.conversation_id,
            context=user_input.context,
            language=user_input.language,
            agent_id=fallback_agent_id,
        )
