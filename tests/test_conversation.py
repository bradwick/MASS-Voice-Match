import pytest
from unittest.mock import MagicMock, AsyncMock
from custom_components.mass_voice_match.embedding import _detect_requested_media_type, search_top_n
from custom_components.mass_voice_match.conversation import (
    get_display_name,
    MASSVoiceMatchConversationAgent,
)
from custom_components.mass_voice_match.const import DOMAIN, CONF_THRESHOLD, CONF_SUGGESTION_COUNT
from homeassistant.components import conversation

def test_detect_requested_media_type():
    # prefixes
    assert _detect_requested_media_type("album thriller") == ("thriller", "album")
    assert _detect_requested_media_type("artist Michael Jackson") == ("michael jackson", "artist")
    assert _detect_requested_media_type("playlist Chill Vibes") == ("chill vibes", "playlist")
    assert _detect_requested_media_type("song Yesterday") == ("yesterday", "track")

    # suffixes
    assert _detect_requested_media_type("thriller album") == ("thriller", "album")
    assert _detect_requested_media_type("Chill Vibes playlist") == ("chill vibes", "playlist")
    assert _detect_requested_media_type("BBC Radio 1 radio station") == ("bbc radio 1", "radio")

    # default
    assert _detect_requested_media_type("play Yesterday") == ("play yesterday", None)


def test_get_display_name():
    assert get_display_name({"name": "Thriller", "artist": "Michael Jackson", "type": "track"}) == "Thriller by Michael Jackson"
    assert get_display_name({"name": "Chill Vibes", "type": "playlist"}) == "the playlist Chill Vibes"
    assert get_display_name({"name": "Smooth Jazz", "type": "radio"}) == "the radio Smooth Jazz"


@pytest.mark.asyncio
async def test_search_top_n_fuzzy_fallback():
    # Setup mock hass
    hass = MagicMock()
    items = [
        {"text": "Yesterday by The Beatles", "name": "Yesterday", "artist": "The Beatles", "uri": "spotify:track:123", "type": "track"},
        {"text": "Hey Jude by The Beatles", "name": "Hey Jude", "artist": "The Beatles", "uri": "spotify:track:456", "type": "track"},
        {"text": "Thriller by Michael Jackson", "name": "Thriller", "artist": "Michael Jackson", "uri": "spotify:track:789", "type": "track"},
        {"text": "Chill Vibes playlist", "name": "Chill Vibes", "uri": "spotify:playlist:abc", "type": "playlist"},
        {"text": "BBC Radio 1 radio station", "name": "BBC Radio 1", "uri": "radio:bbc1", "type": "radio"},
    ]
    hass.data = {
        DOMAIN: {
            "items": items,
            "index": None,
            "model": None,
        }
    }

    # Search for "Yesterday"
    results = search_top_n(hass, "Yesterday", limit=2)
    assert len(results) > 0
    # First one should be Yesterday
    assert results[0][0]["name"] == "Yesterday"

    # Search with a media type preference
    results = search_top_n(hass, "the song Thriller", limit=2)
    assert len(results) > 0
    assert results[0][0]["name"] == "Thriller"

    # Search playlist with suffix
    results_playlist = search_top_n(hass, "Chill Vibes playlist", limit=1)
    assert len(results_playlist) > 0
    assert results_playlist[0][0]["name"] == "Chill Vibes"
    assert results_playlist[0][0]["type"] == "playlist"

    # Search radio station with suffix
    results_radio = search_top_n(hass, "BBC Radio 1 radio station", limit=1)
    assert len(results_radio) > 0
    assert results_radio[0][0]["name"] == "BBC Radio 1"
    assert results_radio[0][0]["type"] == "radio"


@pytest.mark.asyncio
async def test_conversation_agent_matching_suggestions():
    # Setup agent
    hass = MagicMock()
    entry = MagicMock()
    entry.options = {CONF_THRESHOLD: 0.5, CONF_SUGGESTION_COUNT: 3}
    entry.data = {}

    agent = MASSVoiceMatchConversationAgent(hass, entry)

    suggestions = [
        {"name": "Yesterday", "text": "Yesterday by The Beatles", "uri": "spotify:track:123", "type": "track"},
        {"name": "Hey Jude", "text": "Hey Jude by The Beatles", "uri": "spotify:track:456", "type": "track"},
        {"name": "Thriller", "text": "Thriller by Michael Jackson", "uri": "spotify:track:789", "type": "track"},
    ]

    # Match ordinal
    match1 = agent._match_suggestion("the second one please", suggestions)
    assert match1 is not None
    assert match1["name"] == "Hey Jude"

    match2 = agent._match_suggestion("first option", suggestions)
    assert match2 is not None
    assert match2["name"] == "Yesterday"

    # Fuzzy match name
    match3 = agent._match_suggestion("Thriller", suggestions)
    assert match3 is not None
    assert match3["name"] == "Thriller"


@pytest.mark.asyncio
async def test_conversation_agent_process_flow():
    # Setup mock hass and service call
    hass = MagicMock()
    hass.services.async_call = AsyncMock()

    async def async_add_executor_job(func, *args, **kwargs):
        return func(*args, **kwargs)

    hass.async_add_executor_job = async_add_executor_job

    entry = MagicMock()
    entry.options = {CONF_THRESHOLD: 0.5, CONF_SUGGESTION_COUNT: 3}
    entry.data = {}

    agent = MASSVoiceMatchConversationAgent(hass, entry)

    items = [
        {"text": "Yesterday by The Beatles", "name": "Yesterday", "artist": "The Beatles", "uri": "spotify:track:123", "type": "track"},
        {"text": "Hey Jude by The Beatles", "name": "Hey Jude", "artist": "The Beatles", "uri": "spotify:track:456", "type": "track"},
    ]
    hass.data = {
        DOMAIN: {
            "items": items,
            "index": None,
            "model": None,
        }
    }

    # 1. Process a close match
    user_input = conversation.ConversationInput(
        text="play Yesterday",
        context=None,
        conversation_id="test_conv_id",
        language="en",
        agent_id="mass_voice_match",
        device_id=None,
    )

    res = await agent.async_process(user_input)
    assert res is not None
    assert any(p in res.response.speech["plain"]["speech"] for p in ["Yesterday", "Yesterday by The Beatles"])

    # Verify play service was called
    hass.services.async_call.assert_called_with(
        "media_player",
        "play_media",
        {
            "entity_id": entry.options.get("default_media_player"),
            "media_content_id": "spotify:track:123",
            "media_content_type": "track",
        },
        blocking=True,
    )

    # 2. Process with below threshold (forcing suggestions)
    # Let's mock options with very high threshold
    entry.options[CONF_THRESHOLD] = 0.99
    user_input_low = conversation.ConversationInput(
        text="play Yes",
        context=None,
        conversation_id="test_conv_id_2",
        language="en",
        agent_id="mass_voice_match",
        device_id=None,
    )

    res_low = await agent.async_process(user_input_low)
    assert res_low is not None
    assert "mean" in res_low.response.speech["plain"]["speech"]
    assert "Yesterday" in res_low.response.speech["plain"]["speech"]

    # Check that a session was registered
    assert "test_conv_id_2" in agent._sessions
    assert len(agent._sessions["test_conv_id_2"]["suggestions"]) > 0

    # 3. Follow up with ordinal choice
    user_input_follow = conversation.ConversationInput(
        text="the first one",
        context=None,
        conversation_id="test_conv_id_2",
        language="en",
        agent_id="mass_voice_match",
        device_id=None,
    )

    res_follow = await agent.async_process(user_input_follow)
    assert any(p in res_follow.response.speech["plain"]["speech"] for p in ["Yesterday", "Yesterday by The Beatles"])
    # Session should be cleaned up
    assert "test_conv_id_2" not in agent._sessions
