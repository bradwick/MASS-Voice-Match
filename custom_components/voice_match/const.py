"""Constants for the Voice Match integration."""

DOMAIN = "voice_match"
DATA_INDEX = "index"
DATA_ITEMS = "items"
DATA_PATH = "/config/voice_match"

# Configuration keys
CONF_MODEL = "model"
CONF_SENSITIVITY = "sensitivity"
CONF_PROCESSING_MODE = "processing_mode"
CONF_MAX_PROFILES = "max_profiles"
CONF_MUSIC_ASSISTANT = "music_assistant"

# Default values
DEFAULT_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
DEFAULT_SENSITIVITY = 0.7
DEFAULT_PROCESSING_MODE = "local"
DEFAULT_MAX_PROFILES = 10

# Service names
SERVICE_MATCH_VOICE = "match_voice"
SERVICE_ADD_PROFILE = "add_profile"
SERVICE_REMOVE_PROFILE = "remove_profile"
SERVICE_LIST_PROFILES = "list_profiles"
SERVICE_PLAY_MATCH = "play_match"

# Music Assistant constants
MUSIC_ASSISTANT_BASE_URL = "http://localhost:8849"
