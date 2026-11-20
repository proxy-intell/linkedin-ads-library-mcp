"""Tool behaviour through a real MCP client session, with ScrapeCreators stubbed. Run: python test_tools.py"""
import asyncio
import base64
import json
import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

os.environ["PROXY_TELEMETRY"] = "0"
os.environ["SCRAPECREATORS_API_KEY"] = "test"

import requests
from mcp.shared.memory import create_connected_server_and_client_session as connect

from src import ad_history, telemetry
from src.services import media_cache_service, scrapecreators_service

telemetry.STATE_FILE = Path(tempfile.mkdtemp()) / "state.json"
ad_history.HISTORY_FILE = Path(tempfile.mkdtemp()) / "history.json"
media_cache_service.image_cache.get_cached_image = lambda url: None
media_cache_service.image_cache.cache_image = lambda **kw: None
scrapecreators_service.time.sleep = lambda s: None

import mcp_server

PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==")
AD = {"id": "111", "headline": "Ship faster", "advertiser": "Acme", "startDate": "2026-01-04T00:00:00.000Z",
      "image": "https://media.licdn.com/img.jpg"}


class Resp:
    def __init__(self, status, payload=None, content=b"", content_type="application/json"):
        self.status_code, self._payload, self.content = status, payload, content
        self.headers = {"content-type": content_type}

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(str(self.status_code))


calls = []


def fake_get(url, headers=None, params=None, timeout=None):
    calls.append((url, dict(params or {})))
    if "ads/search" in url:
        if params.get("company") == "Broken":
            return Resp(400, {"success": False})
        if params.get("paginationToken") == "p2":
            return Resp(503)  # second page fails twice: keep page one
        first = sum("ads/search" in u for u, _ in calls) == 1
        return Resp(502) if first else Resp(200, {"success": True, "ads": [AD], "paginationToken": "p2", "isLastPage": False})
    return Resp(200, content=PNG, content_type="image/png")


requests.get = fake_get


async def main():
    async with connect(mcp_server.mcp._mcp_server) as c:
        tools = {t.name for t in (await c.list_tools()).tools}
        assert {"search_linkedin_ads", "get_playbook"} <= tools, tools
        assert len((await c.list_prompts()).prompts) == 3

        r = await c.call_tool("get_playbook", {"job": "competitor watch"})
        assert r.content[0].text.startswith("PLAYBOOK: competitor_watch")

        # A 502 is retried once; a failed later page keeps page one and its resume token.
        r = json.loads((await c.call_tool("search_linkedin_ads", {"company": "Acme", "limit": 5})).content[0].text)
        assert r["success"] and len(r["ads"]) == 1 and r["pagination_token"] == "p2", r
        assert "baseline saved" in r["changes"]["note"], r["changes"]

        # Keyword searches and continuation pages are not tracked.
        r = json.loads((await c.call_tool("search_linkedin_ads", {"keyword": "devops", "limit": 1})).content[0].text)
        assert r["changes"] is None

        # A first-page error is a failed lookup, not "no ads".
        r = json.loads((await c.call_tool("search_linkedin_ads", {"company": "Broken"})).content[0].text)
        assert not r["success"] and "400" in r["error"], r

        # The image comes back as an image block the model can see.
        r = await c.call_tool("analyze_ad_image", {"media_url": "https://media.licdn.com/img.jpg", "ad_id": "111"})
        assert [b.type for b in r.content] == ["text", "image"] and not r.isError
        assert json.loads(r.content[0].text)["ad_detail_url"].endswith("/detail/111")


asyncio.run(main())

# Diff: first fetch is a baseline, inside 24h keeps it, 24h+ later reports new and dropped.
t0 = datetime(2026, 11, 1, tzinfo=timezone.utc)
ads = lambda *ids: [{"ad_id": i, "start_date": "2026-10-01T00:00:00.000Z"} for i in ids]
assert "baseline saved" in ad_history.changes("k", ads("1", "2"), t0)["note"]
assert "under 24h" in ad_history.changes("k", ads("3"), t0 + timedelta(hours=2))["note"]
later = ad_history.changes("k", ads("2", "3"), t0 + timedelta(days=2))
assert later["new_since_last_fetch"] == ["3"] and later["dropped_since_last_fetch"] == 1 and later["since_last_fetch"] == "2026-11-01"
recent = [{"ad_id": "n", "start_date": "2026-11-05T00:00:00.000Z"}, {"ad_id": "o", "start_date": "2026-09-01T00:00:00.000Z"}]
assert ad_history.launched_recently(recent, t0 + timedelta(days=6)) == ["n"]

print("tool tests passed")
