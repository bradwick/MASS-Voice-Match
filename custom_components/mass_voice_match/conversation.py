"""Conversation agent for MASS Voice Match."""
import logging
import random
import re
from typing import Literal
from rapidfuzz import fuzz

from homeassistant.components import conversation
from homeassistant.core import HomeAssistant
from homeassistant.helpers import intent
from homeassistant.config_entries import ConfigEntry

from .const import (
    DOMAIN, CONF_MUSIC_ASSISTANT_ENTRY, CONF_DEFAULT_MEDIA_PLAYER,
    CONF_THRESHOLD, CONF_FALLBACK_AGENT, CONF_MODEL, CONF_SUGGESTION_COUNT
)
from .embedding import search_top_n
from .sync import get_ma_domain

_LOGGER = logging.getLogger(__name__)


def get_display_name(item: dict) -> str:
    """Get a user-friendly display name for a media item."""
    name = item.get("name", "")
    artist = item.get("artist", "")
    item_type = item.get("type", "")

    if artist:
        return f"{name} by {artist}"
    elif item_type in ["playlist", "radio"]:
        return f"the {item_type} {name}"
    return name


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
        self._sessions = {}

    @property
    def supported_languages(self) -> list[str] | Literal["*"]:
        """Return a list of supported languages."""
        return "*"

    def _match_suggestion(self, text: str, suggestions: list) -> dict | None:
        """Match user input to suggestions using ordinals or fuzzy matching."""
        text_lower = text.lower().strip()

        # Remove common filler words
        clean_text = re.sub(
            r"\b(?:the|play|listen|to|start|put|on|yes|please|want|choose|select|number)\b",
            "",
            text_lower
        ).strip()

        # 1. Match ordinal numbers (specific/ordinal words first, then fallback cardinal numbers like 'one')
        ordinals = [
            ("first", 0), ("1st", 0), ("1", 0),
            ("second", 1), ("2nd", 1), ("2", 1),
            ("third", 2), ("3rd", 2), ("3", 2),
            ("fourth", 3), ("4th", 3), ("4", 3),
            ("fifth", 4), ("5th", 4), ("5", 4),
            ("sixth", 5), ("6th", 5), ("6", 5),
            ("seventh", 6), ("7th", 6), ("7", 6),
            ("eighth", 7), ("8th", 7), ("8", 7),
            ("ninth", 8), ("9th", 8), ("9", 8),
            ("tenth", 9), ("10th", 9), ("10", 9),
            ("one", 0), ("two", 1), ("three", 2), ("four", 3),
            ("five", 4), ("six", 5), ("seven", 6), ("eight", 7),
            ("nine", 8), ("ten", 9)
        ]

        # Check direct words in clean_text
        for word, idx in ordinals:
            if re.search(r"\b" + re.escape(word) + r"\b", clean_text):
                if idx < len(suggestions):
                    return suggestions[idx]

        # 2. Fuzzy match against suggestions
        best_score = 0.0
        best_item = None
        for item in suggestions:
            name = item.get("name", "").lower().strip()
            text_val = item.get("text", "").lower().strip()

            # Check fuzz ratios
            score_name = fuzz.token_set_ratio(text_lower, name) / 100.0
            score_text = fuzz.token_set_ratio(text_lower, text_val) / 100.0
            max_score = max(score_name, score_text)

            if max_score > best_score:
                best_score = max_score
                best_item = item

        if best_score > 0.75:
            return best_item

        return None

    async def _play_item(
        self, user_input: conversation.ConversationInput, item: dict
    ) -> conversation.ConversationResult:
        """Call play_media and return the success conversation result with random speech."""
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

        display_name = get_display_name(item)
        success_phrases = [
            f"Playing {display_name}",
            f"Sure, starting {display_name}",
            f"Got it, playing {display_name}",
            f"Starting {display_name} now",
            f"Here is {display_name}",
            f"Enjoy {display_name}"
        ]
        speech = random.choice(success_phrases)

        intent_response = intent.IntentResponse(language=user_input.language)
        intent_response.async_set_speech(speech)
        return conversation.ConversationResult(
            response=intent_response,
            conversation_id=user_input.conversation_id,
        )

    async def async_process(
        self, user_input: conversation.ConversationInput
    ) -> conversation.ConversationResult:
        """Process a sentence."""
        text = user_input.text
        _LOGGER.debug("Processing text: %s", text)
        conversation_id = user_input.conversation_id or "default_session"

        # Check active session first
        session = self._sessions.get(conversation_id)
        if session:
            suggestions = session.get("suggestions", [])
            matched_item = self._match_suggestion(text, suggestions)
            # Remove session to avoid loops on subsequent tries
            self._sessions.pop(conversation_id, None)

            if matched_item:
                return await self._play_item(user_input, matched_item)
            else:
                _LOGGER.debug("No suggestion matched for input: %s", text)
                fallback_agent_id = self.entry.options.get(CONF_FALLBACK_AGENT,
                                                         self.entry.data.get(CONF_FALLBACK_AGENT))
                if fallback_agent_id:
                    return await self._async_fallback(user_input)

                intent_response = intent.IntentResponse(language=user_input.language)
                intent_response.async_set_speech("Sorry, I didn't catch that selection.")
                return conversation.ConversationResult(
                    response=intent_response,
                    conversation_id=conversation_id,
                )

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
            suggestion_count = self.entry.options.get(CONF_SUGGESTION_COUNT,
                                                    self.entry.data.get(CONF_SUGGESTION_COUNT, 3))

            results = await self.hass.async_add_executor_job(
                search_top_n, self.hass, query, suggestion_count, model_name
            )

            if not results:
                _LOGGER.debug("No search results found.")
                return await self._async_fallback(user_input)

            best_item, score = results[0]
            actual_threshold = threshold if matched_prefix else max(threshold, 0.7)

            if score >= actual_threshold:
                _LOGGER.info("Matched '%s' to '%s' (score: %s)", query, best_item["name"], score)
                return await self._play_item(user_input, best_item)

            _LOGGER.debug("Match score %s below threshold %s.", score, actual_threshold)

            fallback_agent_id = self.entry.options.get(CONF_FALLBACK_AGENT,
                                                     self.entry.data.get(CONF_FALLBACK_AGENT))

            # If not matched_prefix and a fallback agent is configured, bypass suggestions
            if not matched_prefix and fallback_agent_id:
                _LOGGER.debug("Query did not match play prefix and fallback agent is available. Forwarding.")
                return await self._async_fallback(user_input)

            suggestions = [item for item, s in results]

            if not suggestions:
                return await self._async_fallback(user_input)

            # Formulate speech
            intro = random.choice([
                "I couldn't find an exact match, but did you mean",
                "I'm not sure which one you wanted. Did you mean",
                "I couldn't find that exact song. Would you like to play",
                "I didn't find a perfect match. Did you mean"
            ])

            names = [get_display_name(item) for item in suggestions]
            if len(names) == 1:
                speech = f"{intro} {names[0]}?"
            elif len(names) == 2:
                speech = f"{intro} {names[0]} or {names[1]}?"
            else:
                formatted_names = ", ".join(names[:-1]) + f", or {names[-1]}"
                speech = f"{intro} {formatted_names}?"

            # Save suggestions in session
            self._sessions[conversation_id] = {
                "suggestions": suggestions,
                "timestamp": self.hass.loop.time() if (self.hass and self.hass.loop) else 0
            }

            intent_response = intent.IntentResponse(language=user_input.language)
            intent_response.async_set_speech(speech)
            return conversation.ConversationResult(
                response=intent_response,
                conversation_id=conversation_id,
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
