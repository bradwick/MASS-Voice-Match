import aiohttp

async def fetch_library(hass, url):
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{url}/api/music_assistant/library") as r:
            return await r.json()


def build_items(lib):
    items = []

    for t in lib.get("tracks", []):
        items.append({"text": f"{t.get('artist','')} {t['name']}", "name": t["name"], "media_id": t["id"]})
        items.append({"text": t["name"], "name": t["name"], "media_id": t["id"]})

    for a in lib.get("artists", []):
        items.append({"text": a["name"], "name": a["name"], "media_id": a["id"]})

    return items
