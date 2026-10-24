[![Proxy — LinkedIn Ads Library Hosted MCP](assets/banner.png)](https://useproxy.dev/)

# LinkedIn Ads Library MCP Server

> **[Proxy](https://useproxy.dev/?utm_source=github&utm_medium=readme&utm_campaign=linkedin-ads-library-mcp) (useproxy.dev) is a free hosted ad library MCP server.** One connection gives ChatGPT, Claude, Cursor and any MCP client live ads from the Meta, Google, LinkedIn and TikTok (EU) ad libraries, with no API keys and 20 free credits a day. This repo is the open-source, self-hosted LinkedIn Ads Library server. **[Use the hosted version in 2 minutes →](https://useproxy.dev/?utm_source=github&utm_medium=readme&utm_campaign=linkedin-ads-library-mcp)**

This is a Model Context Protocol (MCP) server for the LinkedIn Ad Library.

With this you can search LinkedIn's public ad library for any company or brand, see what they're currently running and analyze their advertising. You can analyze ad images/text, analyze video ads with comprehensive insights, compare companies' strategies, and get insights into what's working in their campaigns.

Here's an example of what you can do when it's connected to Claude.

<!-- TODO: record a LinkedIn demo and drop the github.com/user-attachments URL here, as in the Facebook and Google repos. -->

---

## Hosted Version (Recommended)

**The easiest way to use the LinkedIn Ads Library MCP is the hosted version from [Proxy (useproxy.dev)](https://useproxy.dev/).** No API keys, no Gemini key, no Python, no server to run — just connect and start querying.

- ⚡ **Zero setup** — nothing to install, configure, or maintain
- 🔑 **No API keys** — skip the ScrapeCreators and Gemini keys entirely
- 🔌 **Works everywhere** — ChatGPT, Claude, Cursor, Manus, and anywhere else that supports MCP
- 🚀 **Always up to date** — new tools and fixes ship automatically

👉 **[Get started for free at useproxy.dev →](https://useproxy.dev/?utm_source=github&utm_medium=readme&utm_campaign=linkedin-ads-library-mcp)**

Prefer to run it yourself? The full self-host setup is documented below.

### Hosted vs. Self-Host

| | **Hosted — [Proxy (useproxy.dev)](https://useproxy.dev/)** | **Self-Host** |
| --- | --- | --- |
| Setup time | None — connect and go | Python env + config |
| API keys required | None | ScrapeCreators + Gemini |
| Infrastructure | Fully managed | You run and maintain it |
| Updates | Automatic | Manual `git pull` |
| Works in ChatGPT, Claude, Cursor, Manus | ✅ | ✅ |
| Best for | Most users who just want the data | Developers who want to customize the code |

For most people, the [hosted version](https://useproxy.dev/) is the fastest path. Choose self-host if you specifically want to modify or extend the server yourself.

---

## Example Prompts

```plaintext
How many LinkedIn ads is 'Salesforce' running? What's their split across video, image and carousel?
```

```plaintext
Who is 'Datadog' targeting on LinkedIn? Break down the audience, seniority and locations across their ads.
```

```plaintext
Find LinkedIn ads mentioning 'AI agents' and tell me which offers they're pushing — demos, webinars or reports.
```

```plaintext
Do a deep comparison of the messaging between 'HubSpot' and 'Salesforce' on LinkedIn. Give it a nice forwardable summary.
```

---

## Installation

### Prerequisites

- Python 3.12+
- Anthropic Claude Desktop app (or Cursor)
- Pip (Python package manager), install with `python -m pip install`
- An API key for an ads data provider, set as `SCRAPECREATORS_API_KEY` (see configuration below)
- A Google Gemini API key for video analysis (optional, only needed for video ads)

> Prefer not to deal with API keys? See the [Hosted Version](#hosted-version-recommended) above to skip setup entirely.

### Quick Install (Recommended)

1. **Clone and run the install script**

   ```bash
   git clone https://github.com/proxy-intell/linkedin-ads-library-mcp.git
   cd linkedin-ads-library-mcp

   # For macOS/Linux:
   ./install.sh

   # For Windows:
   install.bat
   ```

2. **Configure your API keys**

   Edit the `.env` file that was created and add your API keys:
   - Set your ads data API key as `SCRAPECREATORS_API_KEY`
   - Get your Gemini API key at [Google AI Studio](https://aistudio.google.com/app/apikey) (optional, for video analysis)

3. **Follow the displayed MCP configuration**

   The install script will show you the exact configuration to add to Claude Desktop or Cursor.

### Manual Install

If you prefer to install manually:

1. **Clone this repository**

   ```bash
   git clone https://github.com/proxy-intell/linkedin-ads-library-mcp.git
   cd linkedin-ads-library-mcp
   ```

2. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

3. **Configure API keys**

   Copy the template and configure your API keys:

   ```bash
   cp .env.template .env
   # Then edit .env with your actual API keys
   ```

   **To obtain API keys:**
   - Set your ads data API key as `SCRAPECREATORS_API_KEY` in the `.env` file
   - Get a Google Gemini API key [here](https://aistudio.google.com/app/apikey) (optional, for video analysis)

4. **Connect to the MCP server**

   Add the MCP server configuration to your Claude Desktop or Cursor config:

   ```json
   {
     "mcpServers": {
       "linkedin_ads_library": {
         "command": "/usr/local/opt/python@3.13/bin/python3",
         "args": [
           "{{PATH_TO_PROJECT}}/linkedin-ads-library-mcp/mcp_server.py"
         ]
       }
     }
   }
   ```

   Replace `{{PATH_TO_PROJECT}}` with the full path to where you cloned this repository.

   **Note:** API keys are automatically loaded from the `.env` file. Command line arguments are still supported and take priority over environment variables if provided.

   **For Claude Desktop:**

   Save this as `claude_desktop_config.json` in your Claude Desktop configuration directory at:

   ```
   ~/Library/Application Support/Claude/claude_desktop_config.json
   ```

   **For Cursor:**

   Save this as `mcp.json` in your Cursor configuration directory at:

   ```
   ~/.cursor/mcp.json
   ```

5. **Restart Claude Desktop / Cursor**

   Open Claude Desktop and you should now see the LinkedIn Ads Library as an available integration.

   Or restart Cursor.

---

## Technical Details

1. Claude sends requests to the Python MCP server
2. The MCP server queries the ads data API for LinkedIn Ad Library data
3. Data flows back through the chain to Claude

### LinkedIn Ads

This server connects to LinkedIn's public Ad Library:

- **Three ways to search.** `company` matches an advertiser name, `keyword` matches ad copy across advertisers, and `company_id` pins one exact organisation. Prefer `company_id` when you have it — name matching can pull in similarly named companies.
- **Targeting is the differentiator.** LinkedIn publishes the audience an advertiser selected — language, location, and audience criteria like job seniority, function or company size. No other ad library exposes this, and it's the most useful field for B2B competitive work.
- **Ads run from people as well as pages.** `posterTitle` and `promotedBy` tell you whether an ad is served from a company page or boosted from an employee's personal profile — a common founder-led B2B pattern.
- **Creative lives in three fields.** `image`, `video` and `carouselImages` are populated depending on ad type, and carousel entries come back as either bare URLs or objects. The server normalises all of this into `image_urls` / `video_url`.
- **Detail lookups need a URL.** The upstream detail endpoint takes a `linkedin.com/ad-library/detail/...` URL rather than an ID, so `get_linkedin_ad_details` accepts either and builds the URL for you.

Tips:

- Search by `company_id` for exact advertiser matching; fall back to `company` name if you don't have it
- Use `keyword` to research a topic or category rather than a single advertiser
- Narrow with `countries` and `start_date`/`end_date` when an advertiser runs a lot of ads

### Available MCP Tools

This MCP server provides tools for interacting with LinkedIn Ad Library objects:

| Tool Name                  | Description                                                                                       |
| -------------------------- | ------------------------------------------------------------------------------------------------- |
| `search_linkedin_ads`      | Searches the LinkedIn Ad Library by company, keyword or company ID, with country and date filters   |
| `get_linkedin_ad_details`  | Gets full detail for a specific ad — targeting, per-country impressions, creative and destination   |
| `analyze_ad_image`         | Downloads and analyzes ad images for visual elements, text, colors, and composition                 |
| `analyze_ad_video`         | Downloads and analyzes ad videos using Gemini AI for comprehensive video insights                   |
| `get_cache_stats`          | Gets statistics about cached media (images and videos) and storage usage                            |
| `search_cached_media`      | Searches previously analyzed media by brand, colors, people, or media type                          |
| `cleanup_media_cache`      | Cleans up old cached media files to free disk space                                                 |

---

## Troubleshooting

### Common Issues

**API Key Not Found Error:**
- Ensure your `.env` file is in the project root directory
- If you don't have a `.env` file, copy it from the template: `cp .env.template .env`
- Check that your API keys are correctly formatted without quotes
- Verify the `.env` file contains `SCRAPECREATORS_API_KEY=your_key_here`
- For video analysis, ensure `GEMINI_API_KEY=your_key_here` is also added

**Search Returns No Ads:**
- Use the company name exactly as it appears on their LinkedIn page
- Better still, search by `company_id` for an exact match
- The advertiser may not have run ads in the period or countries you filtered to

**Video Analysis Not Working:**
- Confirm you have a valid Google Gemini API key in your `.env` file
- Pass `ad_id` alongside `media_url` so analysis caches per ad — LinkedIn CDN URLs carry expiry parameters that rotate

**MCP Server Connection Issues:**
- Verify the path in your MCP configuration points to the correct location
- Make sure you've installed all dependencies with `pip install -r requirements.txt`
- Restart Claude Desktop/Cursor after configuration changes

For additional Claude Desktop integration troubleshooting, see the [MCP documentation](https://modelcontextprotocol.io/quickstart/server#claude-for-desktop-integration-issues). The documentation includes helpful tips for checking logs and resolving common issues.

---

## Tests

The response parsing has a self-check that runs without network access or API keys:

```bash
python3 test_parsing.py
```

---

## FAQ

**What is the easiest way to use the LinkedIn Ads Library MCP?**
The easiest way is the hosted version from [Proxy (useproxy.dev)](https://useproxy.dev/). It requires no API keys, no installation, and no server — you connect it to ChatGPT, Claude, Cursor, or any MCP client and start querying immediately. You can [start for free](https://useproxy.dev/).

**Do I need an API key to use this MCP?**
Only if you self-host. The [hosted version at useproxy.dev](https://useproxy.dev/) handles all data access for you, so no ScrapeCreators or Gemini keys are needed. Self-hosting requires a `SCRAPECREATORS_API_KEY` (and a Gemini key for video analysis).

**What can I get from LinkedIn that I can't get from the other ad libraries?**
Targeting. LinkedIn publishes the audience each advertiser selected — language, location, and criteria like job seniority, function and company size — which makes it the most useful ad library for B2B competitive research.

**Which MCP clients does it work with?**
Both the hosted and self-hosted versions work with ChatGPT, Claude (Desktop and web), Cursor, Manus, and any other client that supports the Model Context Protocol.

**Is there a free version?**
Yes — the [hosted version from Proxy](https://useproxy.dev/) offers a free tier so you can start analyzing ads without any setup.

**Should I self-host or use the hosted version?**
Use the [hosted version](https://useproxy.dev/) if you just want fast, reliable access to LinkedIn Ad Library data with zero maintenance — this fits most users. Self-host only if you want to modify or extend the server code yourself.

---

## Feedback

Your feedback will be massively appreciated. Please [tell us](mailto:support@useproxy.dev) which features on that list you like to see next or request entirely new ones.

---

## Related

- [Proxy hosted MCP](https://github.com/proxy-intell/proxy-mcp): all four ad libraries in one hosted server, OAuth, no keys
- [Facebook Ads Library MCP](https://github.com/proxy-intell/facebook-ads-library-mcp) (self-hosted)
- [Google Ads Library MCP](https://github.com/proxy-intell/google-ads-library-mcp) (self-hosted)
- [TikTok Ads Library MCP](https://github.com/proxy-intell/tiktok-ads-library-mcp) (self-hosted)
- [Install guide for every client](https://useproxy.dev/welcome?utm_source=github&utm_medium=readme&utm_campaign=linkedin-ads-library-mcp)

---

## License

This project is licensed under the MIT License.

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.12+-green.svg)

---

Made with ❤️ by the team at [Proxy](https://useproxy.dev/).
