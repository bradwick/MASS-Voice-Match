from homeassistant import config_entries

DOMAIN = "voice_match"

class VoiceMatchFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        return self.async_create_entry(title="Voice Match", data={})
