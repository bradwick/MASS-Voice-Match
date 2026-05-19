from homeassistant.core import ServiceCall
from .embedding import build_index, search, load
from .sync import fetch_library, build_items

DOMAIN = "voice_match"

async def async_setup_services(hass):

    async def resolve(call: ServiceCall):
        query = call.data["query"]
        item, score = await hass.async_add_executor_job(search, query)

        hass.states.async_set(
            f"{DOMAIN}.last_match",
            item["name"],
            {"media_id": item["media_id"], "score": score}
        )

    async def rebuild(call: ServiceCall):
        url = call.data.get("url")
        lib = await fetch_library(hass, url)
        items = build_items(lib)

        await hass.async_add_executor_job(build_index, items)

    async def load_index(call):
        await hass.async_add_executor_job(load)

    hass.services.async_register(DOMAIN, "resolve", resolve)
    hass.services.async_register(DOMAIN, "rebuild_index", rebuild)
    hass.services.async_register(DOMAIN, "load_index", load_index)
