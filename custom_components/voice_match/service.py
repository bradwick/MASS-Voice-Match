"""Services for the Voice Match integration."""
import logging
import voluptuous as vol
from homeassistant.core import ServiceCall, HomeAssistant
from homeassistant.helpers import selector

from .const import (
    DOMAIN, SERVICE_MATCH_VOICE, SERVICE_PLAY_MATCH, SERVICE_REBUILD_INDEX,
    CONF_MUSIC_ASSISTANT
)
from .embedding import build_index, search, load_index
from .sync import fetch_library_from_hass, build_items

_LOGGER = logging.getLogger(__name__)

# Service schemas
MATCH_VOICE_SCHEMA = vol.Schema({
    vol.Required("query"): str,
})

PLAY_MATCH_SCHEMA = vol.Schema({
    vol.Required("query"): str,
    vol.Optional("media_player"): str,
})

REBUILD_INDEX_SCHEMA = vol.Schema({
    vol.Optional("music_assistant"): str,
})


async def async_setup_services(hass: HomeAssistant, entry) -> None:
    """Set up services for the Voice Match integration."""
    
    async def handle_match_voice(call: ServiceCall) -> dict:
        """Match voice query against the vector index and return the best match."""
        query = call.data.get("query")
        
        if not query:
            _LOGGER.error("No query provided to match_voice service")
            return {"success": False, "error": "No query provided"}
        
        try:
            item, score = await hass.async_add_executor_job(search, query)
            
            # Store the result as a state
            hass.states.async_set(
                f"{DOMAIN}.last_match",
                item["name"],
                {
                    "media_id": item["media_id"],
                    "score": score,
                    "artist": item.get("artist", ""),
                    "type": item.get("type", "track"),
                    "query": query,
                },
            )
            
            _LOGGER.info("Voice match found: %s (score: %.2f)", item["name"], score)
            
            return {
                "success": True,
                "name": item["name"],
                "artist": item.get("artist", ""),
                "media_id": item["media_id"],
                "score": float(score),
                "type": item.get("type", "track"),
            }
            
        except Exception as err:
            _LOGGER.error("Error matching voice: %s", err)
            return {"success": False, "error": str(err)}
    
    
    async def handle_play_match(call: ServiceCall) -> dict:
        """Match voice query and play the result on a media player."""
        query = call.data.get("query")
        media_player = call.data.get("media_player")
        
        # Get the configured Music Assistant entity if not provided
        if not media_player and entry:
            media_player = entry.data.get(CONF_MUSIC_ASSISTANT)
        
        if not media_player:
            _LOGGER.error("No media player specified and none configured")
            return {"success": False, "error": "No media player available"}
        
        try:
            # First, match the voice query
            item, score = await hass.async_add_executor_job(search, query)
            
            _LOGGER.info("Playing matched item: %s on %s (score: %.2f)", 
                        item["name"], media_player, score)
            
            # Play the matched item on the media player
            await hass.services.async_call(
                "media_player",
                "play_media",
                {
                    "entity_id": media_player,
                    "media_content_id": item["media_id"],
                    "media_content_type": item.get("type", "track"),
                },
                blocking=True,
            )
            
            # Update the state
            hass.states.async_set(
                f"{DOMAIN}.last_match",
                item["name"],
                {
                    "media_id": item["media_id"],
                    "score": score,
                    "artist": item.get("artist", ""),
                    "type": item.get("type", "track"),
                    "query": query,
                    "played_on": media_player,
                },
            )
            
            return {
                "success": True,
                "name": item["name"],
                "artist": item.get("artist", ""),
                "media_id": item["media_id"],
                "score": float(score),
                "type": item.get("type", "track"),
                "played_on": media_player,
            }
            
        except Exception as err:
            _LOGGER.error("Error playing matched voice: %s", err)
            return {"success": False, "error": str(err)}
    
    
    async def handle_rebuild_index(call: ServiceCall) -> dict:
        """Rebuild the vector index from Music Assistant library."""
        music_assistant = call.data.get("music_assistant")
        
        # Use configured Music Assistant if not provided
        if not music_assistant and entry:
            music_assistant = entry.data.get(CONF_MUSIC_ASSISTANT)
        
        if not music_assistant:
            _LOGGER.error("No Music Assistant entity specified")
            return {"success": False, "error": "No Music Assistant configured"}
        
        try:
            _LOGGER.info("Rebuilding Voice Match index from %s", music_assistant)
            
            # Fetch the library
            lib = await fetch_library_from_hass(hass, music_assistant)
            items = build_items(lib)
            
            # Build the index
            await hass.async_add_executor_job(build_index, items)
            
            _LOGGER.info("Voice Match index rebuilt successfully with %d items", len(items))
            
            return {
                "success": True,
                "items_indexed": len(items),
                "tracks": len(lib.get("tracks", [])),
                "artists": len(lib.get("artists", [])),
            }
            
        except Exception as err:
            _LOGGER.error("Error rebuilding Voice Match index: %s", err)
            return {"success": False, "error": str(err)}
    
    
    async def handle_load_index(call: ServiceCall) -> dict:
        """Load the cached vector index from disk."""
        try:
            _LOGGER.info("Loading Voice Match index from cache")
            items = await hass.async_add_executor_job(load_index)
            _LOGGER.info("Voice Match index loaded with %d items", len(items))
            return {"success": True, "items_loaded": len(items)}
        except Exception as err:
            _LOGGER.error("Error loading Voice Match index: %s", err)
            return {"success": False, "error": str(err)}
    
    
    # Register all services
    hass.services.async_register(
        DOMAIN,
        "match_voice",
        handle_match_voice,
        schema=MATCH_VOICE_SCHEMA,
    )
    
    hass.services.async_register(
        DOMAIN,
        "play_match",
        handle_play_match,
        schema=PLAY_MATCH_SCHEMA,
    )
    
    hass.services.async_register(
        DOMAIN,
        "rebuild_index",
        handle_rebuild_index,
        schema=REBUILD_INDEX_SCHEMA,
    )
    
    hass.services.async_register(
        DOMAIN,
        "load_index",
        handle_load_index,
    )
    
    _LOGGER.info("Voice Match services registered successfully")
