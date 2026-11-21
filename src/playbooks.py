"""Analysis playbooks: step-by-step methods for common LinkedIn ad research jobs.

Served two ways: as MCP prompts (the host's prompt menu) and through the get_playbook tool,
so the model can load one itself. Adapted from hosted Proxy's playbooks to this server's tools.
"""

OTHER_PLATFORMS = (
    "This server covers LinkedIn only. For Meta, Google or TikTok, add the sibling self-hosted servers "
    "(github.com/proxy-intell/facebook-ads-library-mcp, google-ads-library-mcp, tiktok-ads-library-mcp) "
    "or hosted Proxy, which has all four plus competitor discovery: "
    "https://useproxy.dev/me/selfhost-linkedin?utm_source=github&utm_medium=playbook&utm_campaign=linkedin-ads-library-mcp"
    " (MCP server URL: https://mcp.useproxy.dev/mcp?ref=linkedin-ads-library-mcp-playbook)"
)

RULES = """\
Rules:
- Ask at most one short question, only if a missing input blocks the work; otherwise state assumptions and go.
- Cite each ad with its ad_detail_url. Never build ad URLs.
- Run time is a proxy for performance, not proof. Say "long-running", not "winning". Impression bands are ranges, not counts. Mark inference ("likely", "suggests").
- A failed lookup is not "no ads": report the error the tool returned.
- End with the deliverables, ready to use. No recap."""

TRIGGERS = {
    "competitor_teardown": "competitors' B2B positioning, offers (demos, reports, webinars), audiences and formats on LinkedIn",
    "who_is_advertising": "which companies or prospects run LinkedIn ads; prospect lists for agencies and sellers",
    "competitor_watch": "tracking competitors' LinkedIn ads, what's new since last time, weekly updates",
}

_BODIES = {
    "competitor_teardown": """\
PLAYBOOK: competitor_teardown. How competitors sell on LinkedIn: positioning, offers, audiences, formats, gaps.
Inputs: competitors or market, the user's own company if any, country if named.

Method:
1. No names: search_linkedin_ads(keyword="<category or problem>", countries="<XX>", limit=50) and keep the 3-6 advertisers that recur.
2. Per competitor: search_linkedin_ads(company="<name>", countries="<XX>", limit=50). Use company_id="<id>" when the name pulls in look-alikes.
3. Tag every ad: offer (demo, free trial, report or whitepaper, webinar or event, case study, job posting, none), funnel stage (awareness, consideration, conversion), format (ad_type: single image, video, carousel, document), poster (company page vs employee: poster_title, promoted_by).
4. Audiences: get_linkedin_ad_details(ad_id="<ad_id>") on the 2-3 longest-running ads per brand for targeting (seniority, function, industry, location) and impressions_by_country.
5. Creatives: analyze_ad_image(media_url="<image_url>") or analyze_ad_video(media_url="<video_url>") on those same ads.

Look for: offers a brand keeps funding for months versus ones it tests; gated vs ungated content; thought-leader ads run from employee profiles; one audience targeted by several brands; claims and proof types nobody uses.

Output:
- Offer x brand table: ad count and longest run.
- Audience per brand: seniority, function, industry, top countries.
- Long-running ads: brand, offer, format, run time, link.
- Gaps: offers, audiences, formats nobody runs.
- 5 campaigns to test, one line each, tied to an ad or a gap.""",

    "who_is_advertising": """\
PLAYBOOK: who_is_advertising. Which companies on a list run LinkedIn ads, and an opener for each.
Inputs: company names or LinkedIn company IDs. Only a market given: build the list from search_linkedin_ads(keyword="<service or category>", countries="<XX>").

Method:
1. Per company: search_linkedin_ads(company="<name>", start_date="<90 days ago, YYYY-MM-DD>", limit=25). Check the advertiser field matches; re-run with company_id="<id>" when it pulls in another company.
2. Per advertiser: ad count, newest start_date, offer mix, whether ads run from employee profiles.
3. get_linkedin_ad_details(ad_id="<ad_id>") on 1-2 ads for targeting: the audience they pay to reach.

Status per company: yes / no (lookup worked, nothing in the window) / wrong match (results are another company) / error (retry once, then report). Wrong match and error are never "no".

Output:
- Table: company | LinkedIn status | ads found | newest ad | offer mix | audience | pitch opener with ad link.
- Top 5 to contact first, one line why each.""",

    "competitor_watch": """\
PLAYBOOK: competitor_watch. What competitors launched, dropped and kept on LinkedIn since last time.
How the diff works: search_linkedin_ads by company or company_id remembers the last fetch (same countries and dates). A re-fetch 24h+ later returns changes.new_since_last_fetch and changes.dropped_since_last_fetch; changes.launched_last_7d lists ads started in the last 7 days, even on a first run. Keyword searches and continuation pages are not tracked. The first run is the baseline: say so and report the last-7-day launches.

Method:
1. Per competitor, same parameters as last time: search_linkedin_ads(company="<name>", countries="<XX>").
2. Per brand: new (ids), dropped (count only), still running (the rest). "Dropped" can also mean an ad fell outside the limit: say so when the fetch hit it.
3. Only the new ads: get_linkedin_ad_details(ad_id="<ad_id>") for targeting, analyze_ad_image(media_url="<image_url>") or analyze_ad_video(media_url="<video_url>") for the creative.

Look for: a new offer (webinar series, report launch, event); a new audience or country; a burst of launches (product launch, quarter-end push); a mass drop; the same move from several brands.

Then offer a weekly scheduled task in the user's assistant with a prompt like "Run the competitor_watch playbook for A, B and C on LinkedIn with the same settings."

Output per brand: launched (count, links), dropped (count), still running (count), what it suggests (inference). Close with 3 lines: what to respond to and what to ignore.""",
}

PLAYBOOKS = {job: f"{body}\n\n{RULES}\n\n{OTHER_PLATFORMS}" for job, body in _BODIES.items()}
