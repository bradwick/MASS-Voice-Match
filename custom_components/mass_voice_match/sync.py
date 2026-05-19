"""Sync library data from Music Assistant integration."""
import logging
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

def get_ma_domain(hass: HomeAssistant) -> str:
    """Detect whether to use 'mass' or 'music_assistant' domain."""
    if hass.services.has_service("mass", "get_library"):
        return "mass"
    if hass.services.has_service("music_assistant", "get_library"):
        return "music_assistant"
    return "mass" # Default fallback

async def fetch_library_from_hass(hass: HomeAssistant, config_entry_id: str) -> dict:
    """
    Fetch library from Music Assistant integration via the hass service.
    """
    domain = get_ma_domain(hass)
    _LOGGER.debug("Using domain '%s' to fetch Music Assistant library", domain)

    library = {
        "tracks": [],
        "artists": [],
        "albums": [],
        "playlists": [],
        "radio": []
    }

    for media_type in library.keys():
        try:
            _LOGGER.debug("Fetching %s from Music Assistant", media_type)
            response = await hass.services.async_call(
                domain,
                "get_library",
                {
                    "config_entry_id": config_entry_id,
                    "media_type": media_type
                },
                blocking=True,
                return_response=True,
            )

            if response and "items" in response:
                library[media_type] = response["items"]
                _LOGGER.debug("Retrieved %d %s from Music Assistant", len(response["items"]), media_type)

        except Exception as err:
            _LOGGER.error("Error fetching %s from Music Assistant: %s", media_type, err)

    return library


def build_items(lib: dict) -> list:
    """
    Build searchable items from Music Assistant library.
    """
    items = []

    # Tracks
    for track in lib.get("tracks", []):
        name = track.get("name", "")
        artist = ""
        if track.get("artists"):
            artist = track["artists"][0].get("name", "")
        elif track.get("artist"):
            artist = track["artist"]

        uri = track.get("uri", "")
        if not uri:
            continue

        # Variations
        if artist:
            items.append({"text": f"{artist} {name}", "name": name, "artist": artist, "uri": uri, "type": "track"})
            items.append({"text": f"{name} by {artist}", "name": name, "artist": artist, "uri": uri, "type": "track"})
        items.append({"text": name, "name": name, "artist": artist, "uri": uri, "type": "track"})

    # Artists
    for artist in lib.get("artists", []):
        name = artist.get("name", "")
        uri = artist.get("uri", "")
        if not uri:
            continue
        items.append({"text": name, "name": name, "uri": uri, "type": "artist"})

    # Albums
    for album in lib.get("albums", []):
        name = album.get("name", "")
        artist = ""
        if album.get("artists"):
            artist = album["artists"][0].get("name", "")
        elif album.get("artist"):
            artist = album.get("artist")

        uri = album.get("uri", "")
        if not uri:
            continue

        if artist:
            items.append({"text": f"{artist} {name}", "name": name, "artist": artist, "uri": uri, "type": "album"})
            items.append({"text": f"{name} by {artist}", "name": name, "artist": artist, "uri": uri, "type": "album"})
        items.append({"text": name, "name": name, "artist": artist, "uri": uri, "type": "album"})

    # Playlists
    for playlist in lib.get("playlists", []):
        name = playlist.get("name", "")
        uri = playlist.get("uri", "")
        if not uri:
            continue
        items.append({"text": name, "name": name, "uri": uri, "type": "playlist"})

    # Radio
    for radio in lib.get("radio", []):
        name = radio.get("name", "")
        uri = radio.get("uri", "")
        if not uri:
            continue
        items.append({"text": name, "name": name, "uri": uri, "type": "radio"})

    _LOGGER.info("Built %d searchable items from library", len(items))
    return items
