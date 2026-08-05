"""Self-check for LinkedIn Ad Library response parsing. No network or API keys needed.

Run: python3 test_parsing.py
"""
from src.services.scrapecreators_service import (
    parse_linkedin_ads,
    collect_media_urls,
    build_ad_detail_url,
)

# Shape taken from the ScrapeCreators /v1/linkedin/ads/search response.
SEARCH_ADS = [
    {
        "id": "666281156",
        "headline": "Ship faster with less toil",
        "description": "See how teams cut deploy time by 40%.",
        "poster": "Acme Corp",
        "posterTitle": "Acme Corp",
        "promotedBy": None,
        "targeting": {"language": "English", "location": "United States", "audience": "Job seniority: Director"},
        "image": "https://media.licdn.com/img.jpg?e=123",
        "video": None,
        "carouselImages": [],
        "adType": "SPONSORED_CONTENT",
        "advertiser": "Acme Corp",
        "advertiserLinkedinPage": "https://www.linkedin.com/company/acme",
        "cta": "Learn more",
        "destinationUrl": "https://acme.com/demo",
        "adDuration": "3 months",
        "startDate": "2026-01-04T00:00:00.000Z",
        "endDate": "2026-04-02T00:00:00.000Z",
        "totalImpressions": "10k-50k",
        "impressionsByCountry": [{"country": "United States", "impressions": "80%"}],
    },
    {
        "id": "777000111",
        "headline": None,
        "description": "Webinar: scaling platform teams",
        "image": None,
        "video": "https://media.licdn.com/v.mp4?e=456",
        "carouselImages": [],
        "adType": "SPONSORED_VIDEO",
        "advertiser": "Acme Corp",
    },
]


def test_parse_search_results():
    parsed = parse_linkedin_ads(SEARCH_ADS)
    assert len(parsed) == 2

    image_ad, video_ad = parsed
    assert image_ad["ad_id"] == "666281156"
    assert image_ad["media_type"] == "image"
    assert image_ad["image_urls"] == ["https://media.licdn.com/img.jpg?e=123"]
    assert image_ad["video_url"] is None
    assert image_ad["cta"] == "Learn more"
    assert image_ad["targeting"]["audience"] == "Job seniority: Director"
    # Search results only carry a bare id, so the detail URL must be derivable.
    assert image_ad["ad_detail_url"] == "https://www.linkedin.com/ad-library/detail/666281156"

    assert video_ad["media_type"] == "video"
    assert video_ad["video_url"] == "https://media.licdn.com/v.mp4?e=456"


def test_carousel_images_accept_strings_and_objects():
    # LinkedIn returns carousel entries as bare URLs on some ads and objects on others.
    ad = {"carouselImages": ["https://a.jpg", {"url": "https://b.jpg"}, {"imageUrl": "https://c.jpg"}, {}]}
    assert collect_media_urls(ad)["image_urls"] == ["https://a.jpg", "https://b.jpg", "https://c.jpg"]


def test_text_only_ad_has_no_media():
    media = collect_media_urls({"headline": "Text only", "image": None, "video": None})
    assert media["media_type"] == "text"
    assert media["image_urls"] == [] and media["video_url"] is None


def test_malformed_ad_does_not_kill_the_batch():
    parsed = parse_linkedin_ads([{"id": "ok"}, {"id": "weird", "carouselImages": 42}])
    assert [a["ad_id"] for a in parsed] == ["ok"]


def test_build_ad_detail_url_accepts_id_or_url():
    assert build_ad_detail_url("666281156") == "https://www.linkedin.com/ad-library/detail/666281156"
    passthrough = "https://www.linkedin.com/ad-library/detail/666281156"
    assert build_ad_detail_url(passthrough) == passthrough

    for bad in ("", "   ", "not-an-id"):
        try:
            build_ad_detail_url(bad)
        except ValueError:
            continue
        raise AssertionError(f"expected ValueError for {bad!r}")


if __name__ == "__main__":
    test_parse_search_results()
    test_carousel_images_accept_strings_and_objects()
    test_text_only_ad_has_no_media()
    test_malformed_ad_does_not_kill_the_batch()
    test_build_ad_detail_url_accepts_id_or_url()
    print("all parsing checks passed")
