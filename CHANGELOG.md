# Changelog

v1.1.0 · Nov 20 · LinkedIn

## What's new since last week, and playbooks

B2B competitors don't launch ads often. So when they do, you want to know.

### new
- **See what's new since your last pull:** search a company again a day or more later and the result lists its new ads and how many stopped. Ads launched in the last 7 days show up on the first search too.
- **Playbooks:** competitor teardown, prospect lists and a weekly competitor watch, in your client's prompt menu or via `get_playbook`.

### fixed
- **Video analysis works again:** the Gemini model it used was retired. It now defaults to `gemini-3.1-flash-lite`, and `GEMINI_MODEL` in `.env` switches it.
- **Image analysis your AI can see:** `analyze_ad_image` now returns the image, not base64 text.
- **Searches survive a bad page:** server errors get one retry. If a later page still fails, you keep the ads already found plus a token to carry on.

Upgrade: `git pull && ./venv/bin/pip install -r requirements.txt`, then restart your MCP client.

Also self-hosted: [Facebook](https://github.com/proxy-intell/facebook-ads-library-mcp), [Google](https://github.com/proxy-intell/google-ads-library-mcp), [TikTok](https://github.com/proxy-intell/tiktok-ads-library-mcp). Or all four in one connection, no keys: [Proxy](https://useproxy.dev/me/selfhost-linkedin?utm_source=github&utm_medium=release&utm_campaign=linkedin-ads-library-mcp).
