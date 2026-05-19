"""Conversation agent for MASS Voice Match."""
import logging
from typing import Literal
import re

from homeassistant.components import conversation
from homeassistant.core import HomeAssistant
from homeassistant.helpers import intent
from homeassistant.config_entries import ConfigEntry

from .const import (
    DOMAIN, CONF_MUSIC_ASSISTANT_ENTRY, CONF_DEFAULT_MEDIA_PLAYER, CONF_THRESHOLD
)
from .embedding import search

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
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

        # Improved prefix stripping
        # Handles "Play...", "Can you play...", "I want to listen to...", etc.
        patterns = [
            r"^(?:could you |can you |please |i want to )?(?:play|listen to|start|put on) (.+)$",
            r"^(.+)$" # Fallback to whole string
        ]

        query = text
        for pattern in patterns:
            match = re.match(pattern, text, re.IGNORECASE)
            if match:
                query = match.group(1).strip()
                break

        try:
            threshold = self.entry.data.get(CONF_THRESHOLD, 0.5)
            item, score = await self.hass.async_add_executor_job(
                search, self.hass, query
            )

            if score < threshold:
                 _LOGGER.debug("Best match '%s' score %s below threshold %s",
                              item["name"], score, threshold)
                 return conversation.ConversationResult(
                    response=intent.IntentResponse(language=user_input.language),
                    conversation_id=user_input.conversation_id,
                )

            _LOGGER.info("Matched '%s' to '%s' (score: %s)", query, item["name"], score)

            # Play the matched item
            ma_entry_id = self.entry.data.get(CONF_MUSIC_ASSISTANT_ENTRY)
            player_id = self.entry.data.get(CONF_DEFAULT_MEDIA_PLAYER)

            await self.hass.services.async_call(
                "music_assistant",
                "play_media",
                {
                    "config_entry_id": ma_entry_id,
                    "media_id": item["uri"],
                    "media_type": item["type"],
                },
                target={"entity_id": player_id},
                blocking=True,
            )

            intent_response = intent.IntentResponse(language=user_input.language)
            intent_response.async_set_speech(f"Playing {item['name']}")
            return conversation.ConversationResult(
                response=intent_response,
                conversation_id=user_input.conversation_id,
            )

        except Exception as err:
            _LOGGER.error("Error in conversation agent: %s", err)
            return conversation.ConversationResult(
                response=intent.IntentResponse(language=user_input.language),
                conversation_id=user_input.conversation_id,
            )
