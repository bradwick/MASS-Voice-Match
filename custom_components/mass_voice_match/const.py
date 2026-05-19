"""Constants for the MASS Voice Match integration."""

DOMAIN = "mass_voice_match"

# Configuration keys
CONF_MUSIC_ASSISTANT_ENTRY = "music_assistant_entry"
CONF_DEFAULT_MEDIA_PLAYER = "default_media_player"
CONF_MODEL = "model"
CONF_THRESHOLD = "threshold"

# Default values
DEFAULT_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
DEFAULT_THRESHOLD = 0.5

# Service names
SERVICE_REBUILD_INDEX = "rebuild_index"

# Storage
STORAGE_VERSION = 1
STORAGE_KEY_ITEMS = f"{DOMAIN}.items"
INDEX_FILENAME = "mass_voice_match.faiss"
