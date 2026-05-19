from .service import async_setup_services

DOMAIN = "voice_match"

async def async_setup(hass, config):
    hass.data.setdefault(DOMAIN, {})
    await async_setup_services(hass)
    return True
