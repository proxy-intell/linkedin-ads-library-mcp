import requests
import sys
import os
import logging
import re
from typing import Dict, Any, List, Optional

# Set up logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# LinkedIn Ad Library API endpoints
SEARCH_API_URL = "https://api.scrapecreators.com/v1/linkedin/ads/search"
AD_DETAILS_API_URL = "https://api.scrapecreators.com/v1/linkedin/ad"

AD_DETAIL_URL_TEMPLATE = "https://www.linkedin.com/ad-library/detail/{}"

# Safety valve so a large `limit` can't page forever
MAX_PAGES = 10

SCRAPECREATORS_API_KEY = None

# Shown to the AI/user on any setup or quota failure — the zero-config escape hatch.
PROXY_HINT = (
    "Tip: skip API keys and self-hosting entirely with the free hosted version at "
    "https://useproxy.dev/ — no ScrapeCreators or Gemini keys, nothing to run."
)

# --- Custom Exceptions ---

class CreditExhaustedException(Exception):
    """Raised when ScrapeCreators API credits are exhausted."""
    def __init__(self, message: str, credits_remaining: int = 0, topup_url: str = "https://scrapecreators.com/dashboard"):
        self.credits_remaining = credits_remaining
        self.topup_url = topup_url
        super().__init__(message)

class RateLimitException(Exception):
    """Raised when ScrapeCreators API rate limit is exceeded."""
    def __init__(self, message: str, retry_after: int = None):
        self.retry_after = retry_after
        super().__init__(message)

# --- Helper Functions ---

def check_credit_status(response: requests.Response) -> None:
    """
    Raise a descriptive exception when the API refuses a request for billing reasons.

    Args:
        response: HTTP response from ScrapeCreators API

    Raises:
        CreditExhaustedException: If credits are exhausted
        RateLimitException: If rate limit is exceeded
    """
    if response.status_code == 402:  # Payment Required
        raise CreditExhaustedException(
            f"ScrapeCreators API credits exhausted. Top up your account to continue, or {PROXY_HINT}",
            credits_remaining=0
        )
    if response.status_code == 429:  # Too Many Requests
        retry_after = response.headers.get('retry-after')
        raise RateLimitException(
            "ScrapeCreators API rate limit exceeded. Please wait before making more requests.",
            retry_after=int(retry_after) if retry_after else None
        )
    if response.status_code == 403:  # Forbidden - may indicate credit issues
        try:
            error_data = response.json()
        except ValueError:
            return
        if 'credit' in str(error_data).lower() or 'quota' in str(error_data).lower():
            raise CreditExhaustedException(
                "ScrapeCreators API access denied. This may indicate insufficient credits.",
                credits_remaining=0
            )


def get_scrapecreators_api_key() -> str:
    """
    Get ScrapeCreators API key from command line arguments or environment variable.
    Caches the key in memory after first read.
    Priority: command line argument > environment variable

    Returns:
        str: The ScrapeCreators API key.

    Raises:
        Exception: If no key is provided in command line arguments or environment.
    """
    global SCRAPECREATORS_API_KEY
    if SCRAPECREATORS_API_KEY is None:
        # Try command line argument first
        if "--scrapecreators-api-key" in sys.argv:
            token_index = sys.argv.index("--scrapecreators-api-key") + 1
            if token_index < len(sys.argv):
                SCRAPECREATORS_API_KEY = sys.argv[token_index]
                logger.info("Using ScrapeCreators API key from command line arguments")
            else:
                raise Exception("--scrapecreators-api-key argument provided but no key value followed it")
        # Try environment variable
        elif os.getenv("SCRAPECREATORS_API_KEY"):
            SCRAPECREATORS_API_KEY = os.getenv("SCRAPECREATORS_API_KEY")
            logger.info("Using ScrapeCreators API key from environment variable")
        else:
            raise Exception(
                "No ScrapeCreators API key found. Provide one via the '--scrapecreators-api-key' "
                "argument or the 'SCRAPECREATORS_API_KEY' environment variable. " + PROXY_HINT
            )

    return SCRAPECREATORS_API_KEY


def _request(url: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """Issue an authenticated GET against the ScrapeCreators API and return parsed JSON."""
    api_key = get_scrapecreators_api_key()

    response = requests.get(
        url,
        headers={"x-api-key": api_key},
        params=params,
        timeout=30
    )
    check_credit_status(response)
    response.raise_for_status()

    content = response.json()
    if not content.get('success'):
        raise Exception(f"API returned unsuccessful response: {content}")

    return content


def build_ad_detail_url(ad_id_or_url: str) -> str:
    """
    Normalise an ad reference into a LinkedIn ad-library detail URL.

    The detail endpoint only accepts a URL, while search results carry a bare
    `id`, so accept either and let callers pass whichever they have.
    """
    value = (ad_id_or_url or "").strip()
    if not value:
        raise ValueError("ad_id must be provided")

    if value.startswith("http://") or value.startswith("https://"):
        return value

    if not re.fullmatch(r"\d+", value):
        raise ValueError(
            f"'{value}' is neither a numeric LinkedIn ad id nor an ad-library URL"
        )

    return AD_DETAIL_URL_TEMPLATE.format(value)


def search_ads(
    company: Optional[str] = None,
    keyword: Optional[str] = None,
    company_id: Optional[str] = None,
    countries: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 50,
    pagination_token: Optional[str] = None
) -> Dict[str, Any]:
    """
    Search the LinkedIn Ad Library.

    Pages through results until `limit` ads are collected, the API reports the
    last page, or MAX_PAGES is hit.

    Args:
        company: Company/advertiser name to search for.
        keyword: Keyword to match against ad copy.
        company_id: LinkedIn company ID, the most precise way to pin an advertiser.
        countries: Country filter (e.g. "US" or "US,GB").
        start_date: Only return ads running on/after this date (YYYY-MM-DD).
        end_date: Only return ads running on/before this date (YYYY-MM-DD).
        limit: Maximum number of ads to return.
        pagination_token: Token from a previous response.

    Returns:
        Dictionary with parsed `ads`, `pagination_token`, `is_last_page` and `total_ads`.

    Raises:
        ValueError: If no search criterion is supplied.
        requests.RequestException: If the API request fails.
    """
    if not any([company, keyword, company_id]):
        raise ValueError("At least one of company, keyword or company_id must be provided")

    ads: List[Dict[str, Any]] = []
    total_ads = None
    is_last_page = False
    pages = 0

    while pages < MAX_PAGES:
        params = {}
        if company:
            params["company"] = company
        if keyword:
            params["keyword"] = keyword
        if company_id:
            params["companyId"] = company_id
        if countries:
            params["countries"] = countries
        if start_date:
            params["startDate"] = start_date
        if end_date:
            params["endDate"] = end_date
        if pagination_token:
            params["paginationToken"] = pagination_token

        content = _request(SEARCH_API_URL, params)
        pages += 1

        total_ads = content.get('totalAds', total_ads)
        ads.extend(parse_linkedin_ads(content.get('ads', [])))

        pagination_token = content.get('paginationToken')
        is_last_page = bool(content.get('isLastPage')) or not pagination_token
        if len(ads) >= limit or is_last_page:
            break

    if len(ads) > limit:
        ads = ads[:limit]
        is_last_page = False

    criterion = company or company_id or keyword
    logger.info(f"Retrieved {len(ads)} LinkedIn ads for '{criterion}' across {pages} page(s)")
    return {
        "ads": ads,
        "pagination_token": pagination_token,
        "is_last_page": is_last_page,
        "total_ads": total_ads,
    }


def get_ad_details(ad_id_or_url: str) -> Dict[str, Any]:
    """
    Get detailed information for a specific LinkedIn ad.

    Args:
        ad_id_or_url: Numeric ad ID from search results, or a full
                      linkedin.com/ad-library/detail/... URL.

    Returns:
        Dictionary containing the raw ad detail payload from the API.

    Raises:
        requests.RequestException: If the API request fails.
        Exception: For other errors.
    """
    detail_url = build_ad_detail_url(ad_id_or_url)

    content = _request(AD_DETAILS_API_URL, {"url": detail_url})
    content['ad_detail_url'] = detail_url
    logger.info(f"Retrieved LinkedIn ad details for {detail_url}")
    return content


def collect_media_urls(ad: Dict[str, Any]) -> Dict[str, Any]:
    """
    Pull every usable media URL out of an ad into a predictable shape.

    LinkedIn spreads creative across three mutually-exclusive-ish fields
    (`image`, `video`, `carouselImages`) depending on ad type, and
    `carouselImages` entries are sometimes plain URL strings and sometimes
    objects wrapping one.
    """
    images = []
    if ad.get('image'):
        images.append(ad['image'])

    for item in ad.get('carouselImages') or []:
        if isinstance(item, str):
            images.append(item)
        elif isinstance(item, dict):
            url = item.get('url') or item.get('image') or item.get('imageUrl')
            if url:
                images.append(url)

    video = ad.get('video') or None

    return {
        "image_urls": images,
        "video_url": video,
        "media_type": 'video' if video else ('image' if images else 'text'),
    }


def parse_linkedin_ads(ads: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Flatten LinkedIn Ad Library search results into a consistent shape.

    Args:
        ads: List of raw ad objects from the search endpoint.

    Returns:
        List of parsed ad objects with media URLs surfaced for analysis tools.
    """
    parsed_ads = []

    for ad in ads:
        try:
            media = collect_media_urls(ad)
            ad_id = ad.get('id')

            ad_obj = {
                'ad_id': ad_id,
                'headline': ad.get('headline'),
                'description': ad.get('description'),
                'advertiser': ad.get('advertiser'),
                'advertiser_linkedin_page': ad.get('advertiserLinkedinPage'),
                'poster': ad.get('poster'),
                'poster_title': ad.get('posterTitle'),
                'promoted_by': ad.get('promotedBy'),
                'ad_type': ad.get('adType'),
                'cta': ad.get('cta'),
                'destination_url': ad.get('destinationUrl'),
                'ad_duration': ad.get('adDuration'),
                'start_date': ad.get('startDate'),
                'end_date': ad.get('endDate'),
                'total_impressions': ad.get('totalImpressions'),
                'impressions_by_country': ad.get('impressionsByCountry', []),
                'targeting': ad.get('targeting', {}),
                'ad_detail_url': AD_DETAIL_URL_TEMPLATE.format(ad_id) if ad_id else None,
                **media,
            }

            parsed_ads.append(ad_obj)

        except Exception as e:
            logger.error(f"Error parsing LinkedIn ad {ad.get('id', 'unknown')}: {str(e)}")
            continue

    return parsed_ads
