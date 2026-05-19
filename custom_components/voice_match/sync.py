"""Sync library data from Music Assistant integration."""
import logging
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


async def fetch_library_from_hass(hass: HomeAssistant, music_assistant_entity: str) -> dict:
    """
    Fetch library from Music Assistant integration via the hass service.
    
    Args:
        hass: Home Assistant instance
        music_assistant_entity: Entity ID of the Music Assistant media player
        
    Returns:
        Dictionary containing tracks and artists from the library
    """
    try:
        # Call Music Assistant's get_library service
        response = await hass.services.async_call(
            "music_assistant",
            "get_library",
            {"media_player_entity_id": music_assistant_entity},
            blocking=True,
            return_response=True,
        )
        
        if response:
            _LOGGER.debug("Retrieved library from Music Assistant: %s items", 
                         len(response.get("tracks", [])) + len(response.get("artists", [])))
            return response
        else:
            _LOGGER.warning("No response from Music Assistant get_library service")
            return {"tracks": [], "artists": []}
            
    except Exception as err:
        _LOGGER.error("Error fetching library from Music Assistant: %s", err)
        return {"tracks": [], "artists": []}


async def fetch_library(hass: HomeAssistant, url: str) -> dict:
    """Legacy function for backwards compatibility. Use fetch_library_from_hass instead."""
    _LOGGER.warning("fetch_library(url) is deprecated. Use fetch_library_from_hass() instead.")
    return {"tracks": [], "artists": []}


def build_items(lib: dict) -> list:
    """
    Build searchable items from Music Assistant library.
    
    Creates multiple text variations for each track to improve matching accuracy:
    - "artist name" + "track name"
    - "track name" alone
    - "artist name" alone
    
    Args:
        lib: Dictionary with 'tracks' and 'artists' keys
        
    Returns:
        List of items with 'text', 'name', and 'media_id' keys
    """
    items = []

    # Add track variations (artist + name, and name only)
    for track in lib.get("tracks", []):
        track_name = track.get("name", "")
        artist_name = track.get("artist", "")
        media_id = track.get("id", track.get("media_id", ""))
        
        if not media_id:
            _LOGGER.warning("Track missing ID: %s", track_name)
            continue
        
        # Full text: artist + track
        if artist_name:
            items.append({
                "text": f"{artist_name} {track_name}",
                "name": track_name,
                "artist": artist_name,
                "media_id": media_id,
                "type": "track"
            })
        
        # Track name only
        items.append({
            "text": track_name,
            "name": track_name,
            "artist": artist_name,
            "media_id": media_id,
            "type": "track"
        })

    # Add artist entries
    for artist in lib.get("artists", []):
        artist_name = artist.get("name", "")
        media_id = artist.get("id", artist.get("media_id", ""))
        
        if not media_id:
            _LOGGER.warning("Artist missing ID: %s", artist_name)
            continue
        
        items.append({
            "text": artist_name,
            "name": artist_name,
            "artist": artist_name,
            "media_id": media_id,
            "type": "artist"
        })

    _LOGGER.info("Built %d searchable items from library", len(items))
    return items
