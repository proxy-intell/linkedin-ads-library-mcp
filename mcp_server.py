from mcp.server.fastmcp import FastMCP
from src.services.scrapecreators_service import (
    search_ads,
    get_ad_details,
    collect_media_urls,
    get_scrapecreators_api_key,
)
from src.services.media_cache_service import media_cache, image_cache  # Keep image_cache for backward compatibility
from src.services.gemini_service import configure_gemini, upload_video_to_gemini, analyze_video_with_gemini, cleanup_gemini_file
from typing import Dict, Any, List, Optional
import requests
import base64
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


INSTRUCTIONS = """
This server provides access to LinkedIn's Ad Library data through the ScrapeCreators API.
It allows you to search for advertisers and retrieve the ads they are running on LinkedIn.

Workflow:
1. Use search_linkedin_ads with a company name, keyword, or LinkedIn company ID.
   Filters for countries and a date range are supported.
2. Use get_linkedin_ad_details with the id from a search result for full targeting
   (language, location, audience) and per-country impression data
3. Use analyze_ad_image/analyze_ad_video for comprehensive media analysis

LinkedIn ads carry B2B-specific signal the other ad libraries don't: the targeting
block describes the audience the advertiser selected, and posterTitle/promotedBy
reveal whether an ad runs from a company page or an employee's personal profile.
"""


mcp = FastMCP(
   name="LinkedIn Ads Library",
   instructions=INSTRUCTIONS
)

AD_LIBRARY_URL = "https://www.linkedin.com/ad-library/home"


@mcp.tool(
  description="Search LinkedIn's Ad Library for the ads a company is running. Search by company name, by keyword across ad copy, or by LinkedIn company ID (most precise). Supports country and date-range filters. Returns headline, description, CTA, destination URL, targeting, impressions and media URLs. For complete analysis of visual elements, colors, design, or creative content, you MUST also use analyze_ad_image or analyze_ad_video on the media returned by each ad.",
  annotations={
    "title": "Search LinkedIn Ads",
    "readOnlyHint": True,
    "openWorldHint": True
  }
)
def search_linkedin_ads(
    company: Optional[str] = None,
    keyword: Optional[str] = None,
    company_id: Optional[str] = None,
    countries: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: Optional[int] = 50,
    pagination_token: Optional[str] = None
) -> Dict[str, Any]:
    """Search the LinkedIn Ad Library by company, keyword, or company ID.

    At least one of company, keyword or company_id must be supplied. Prefer
    company_id when you have it — company name matching can pull in similarly
    named organisations.

    Args:
        company: Company/advertiser name to search for (e.g. "Salesforce").
        keyword: Keyword to match against ad copy — use to find ads by topic across advertisers.
        company_id: LinkedIn company ID for an exact advertiser match.
        countries: Country filter (e.g. "US" or "US,GB").
        start_date: Only return ads running on/after this date (YYYY-MM-DD).
        end_date: Only return ads running on/before this date (YYYY-MM-DD).
        limit: Maximum number of ads to retrieve (default: 50). Results are paged automatically.
        pagination_token: Token from a previous response to continue paging.

    Returns:
        A dictionary containing:
        - success: Boolean indicating if the ads were retrieved successfully
        - message: Status message describing the result
        - ads: List of ad objects with copy, CTA, targeting, impressions and media URLs
        - pagination_token: Token for retrieving the next page
        - is_last_page: Whether this is the final page of results
        - total_ads: Total ad count reported by LinkedIn, if provided
        - error: Error details if the retrieval failed
    """
    if not any([company, keyword, company_id]):
        return {
            "success": False,
            "message": "Provide at least one of company, keyword or company_id.",
            "ads": [],
            "pagination_token": None,
            "is_last_page": True,
            "error": "Missing search criteria"
        }

    try:
        # Get API key first
        get_scrapecreators_api_key()

        result = search_ads(
            company=company,
            keyword=keyword,
            company_id=company_id,
            countries=countries,
            start_date=start_date,
            end_date=end_date,
            limit=limit or 50,
            pagination_token=pagination_token
        )
        ads = result.get('ads', [])
        criterion = company or company_id or keyword

        if not ads:
            return {
                "success": True,
                "message": (
                    f"No ads found for '{criterion}' in the LinkedIn Ad Library. "
                    "Try the exact company name as it appears on their LinkedIn page, or search by company_id."
                ),
                "ads": [],
                "pagination_token": None,
                "is_last_page": True,
                "error": None
            }

        return {
            "success": True,
            "message": f"Successfully retrieved {len(ads)} LinkedIn ads for '{criterion}'.",
            "ads": ads,
            "pagination_token": result.get('pagination_token'),
            "is_last_page": result.get('is_last_page', False),
            "total_ads": result.get('total_ads'),
            "ad_library_url": AD_LIBRARY_URL,
            "source_citation": f"[LinkedIn Ad Library - {criterion}]({AD_LIBRARY_URL})",
            "error": None
        }

    except requests.exceptions.RequestException as e:
        return {
            "success": False,
            "message": f"Network error while retrieving ads: {str(e)}",
            "ads": [],
            "pagination_token": None,
            "is_last_page": True,
            "error": f"Network error: {str(e)}"
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"Failed to retrieve ads: {str(e)}",
            "ads": [],
            "pagination_token": None,
            "is_last_page": True,
            "error": str(e)
        }


@mcp.tool(
  description="Get detailed information about a specific LinkedIn ad including full targeting (language, location, audience), per-country impression breakdown, creative and destination URL. Use this with an ad id from search_linkedin_ads, or a linkedin.com/ad-library/detail/ URL. Essential for understanding who an advertiser is targeting and extracting media URLs for visual analysis.",
  annotations={
    "title": "Get LinkedIn Ad Details",
    "readOnlyHint": True,
    "openWorldHint": True
  }
)
def get_linkedin_ad_details(ad_id: str) -> Dict[str, Any]:
    """Get detailed information about a specific LinkedIn ad.

    Args:
        ad_id: The ad's numeric ID from search_linkedin_ads, or a full
               https://www.linkedin.com/ad-library/detail/... URL.

    Returns:
        A dictionary containing:
        - success: Boolean indicating if the details were retrieved successfully
        - headline / description / cta / destination_url: The ad's copy and click target
        - advertiser / poster / poster_title / promoted_by: Who is running the ad
        - targeting: Language, location and audience the advertiser selected
        - impressions_by_country: Per-country impression breakdown
        - image_urls / video_url: Creative media for analysis
        - error: Error details if the retrieval failed
    """
    if not ad_id or not str(ad_id).strip():
        return {
            "success": False,
            "message": "Ad ID must be provided and cannot be empty.",
            "error": "Missing or empty ad ID"
        }

    try:
        # No explicit key fetch here: get_ad_details validates the ad reference
        # before it needs the key, so a malformed id reports the id problem
        # rather than a missing-key error.
        details = get_ad_details(str(ad_id).strip())
        media = collect_media_urls(details)

        return {
            "success": True,
            "message": f"Successfully retrieved details for LinkedIn ad {details.get('id', ad_id)}.",
            "ad_id": details.get('id', ad_id),
            "headline": details.get('headline'),
            "description": details.get('description'),
            "advertiser": details.get('advertiser'),
            "advertiser_linkedin_page": details.get('advertiserLinkedinPage'),
            "poster": details.get('poster'),
            "poster_title": details.get('posterTitle'),
            "promoted_by": details.get('promotedBy'),
            "ad_type": details.get('adType'),
            "cta": details.get('cta'),
            "destination_url": details.get('destinationUrl'),
            "ad_duration": details.get('adDuration'),
            "start_date": details.get('startDate'),
            "end_date": details.get('endDate'),
            "total_impressions": details.get('totalImpressions'),
            "impressions_by_country": details.get('impressionsByCountry', []),
            "targeting": details.get('targeting', {}),
            "ad_detail_url": details.get('ad_detail_url'),
            "ad_library_url": AD_LIBRARY_URL,
            "source_citation": f"[LinkedIn Ad Details - {details.get('advertiser') or ad_id}]({details.get('ad_detail_url') or AD_LIBRARY_URL})",
            **media,
            "error": None
        }

    except ValueError as e:
        return {
            "success": False,
            "message": str(e),
            "error": str(e)
        }
    except requests.exceptions.RequestException as e:
        return {
            "success": False,
            "message": f"Network error while retrieving ad details: {str(e)}",
            "error": f"Network error: {str(e)}"
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"Failed to retrieve ad details: {str(e)}",
            "error": str(e)
        }


@mcp.tool(
  description="REQUIRED for analyzing images from LinkedIn ads. Download and analyze ad images (single image creatives, carousel cards and document/thumbnail covers) to extract visual elements, text content, colors, people, brand elements, and composition details. This tool should be used for EVERY image URL returned by search_linkedin_ads when doing comprehensive analysis. Uses intelligent caching so multiple image analysis calls are efficient and cost-free.",
  annotations={
    "title": "Analyze Ad Image Content",
    "readOnlyHint": True,
    "openWorldHint": True
  }
)
def analyze_ad_image(media_url: str, brand_name: Optional[str] = None, ad_id: Optional[str] = None) -> Dict[str, Any]:
    """Download LinkedIn ad images and prepare them for visual analysis by the MCP client.

    This tool downloads images from LinkedIn CDN URLs and provides them in a format
    that Claude can analyze using its vision capabilities. Images are cached locally
    to avoid re-downloading. The tool provides detailed analysis instructions to ensure
    comprehensive, objective visual analysis.

    Args:
        media_url: The direct URL to the LinkedIn ad image (image or carouselImages entry).
        brand_name: Optional brand name for cache organization.
        ad_id: Optional ad ID for tracking purposes.

    Returns:
        A dictionary containing:
        - success: Boolean indicating if download was successful
        - message: Status message
        - cached: Boolean indicating if image was retrieved from cache
        - image_data: Base64 encoded image data for vision analysis
        - media_url: Original image URL
        - analysis_instructions: Detailed prompt for objective visual analysis
        - cache_status: Information about cache usage
        - error: Error details if download failed
    """
    if not media_url or not media_url.strip():
        return {
            "success": False,
            "message": "Media URL must be provided and cannot be empty.",
            "cached": False,
            "analysis": {},
            "cache_info": {},
            "error": "Missing or empty media URL"
        }

    try:
        # Check cache first
        cached_data = image_cache.get_cached_image(media_url.strip())

        if cached_data and cached_data.get('analysis_results'):
            # Return cached analysis results
            return {
                "success": True,
                "message": f"Retrieved cached analysis for {media_url}",
                "cached": True,
                "analysis": cached_data['analysis_results'],
                "cache_info": {
                    "cached_at": cached_data.get('downloaded_at'),
                    "analysis_cached_at": cached_data.get('analysis_cached_at'),
                    "file_size": cached_data.get('file_size'),
                    "brand_name": cached_data.get('brand_name'),
                    "ad_id": cached_data.get('ad_id')
                },
                "error": None
            }

        # Determine if we need to download
        image_data = None

        if cached_data:
            # Image is cached but no analysis results yet
            try:
                with open(cached_data['file_path'], 'rb') as f:
                    image_bytes = f.read()
                image_data = base64.b64encode(image_bytes).decode('utf-8')
            except Exception:
                # Cache file corrupted, will re-download
                cached_data = None

        if not cached_data:
            # Download the image
            response = requests.get(media_url.strip(), timeout=30)
            response.raise_for_status()

            # Check if it's an image
            content_type = response.headers.get('content-type', '').lower()
            if not any(img_type in content_type for img_type in ['image/', 'jpeg', 'jpg', 'png', 'gif', 'webp']):
                return {
                    "success": False,
                    "message": f"URL does not point to a valid image. Content type: {content_type}",
                    "cached": False,
                    "analysis": {},
                    "cache_info": {},
                    "error": f"Invalid content type: {content_type}"
                }

            # Cache the downloaded image
            image_cache.cache_image(
                url=media_url.strip(),
                image_data=response.content,
                content_type=content_type,
                brand_name=brand_name,
                ad_id=ad_id
            )

            # Encode for analysis
            image_data = base64.b64encode(response.content).decode('utf-8')

        # Construct comprehensive analysis prompt - let the client control presentation
        analysis_prompt = """
Analyze this LinkedIn ad image and extract ALL factual information about:

**Overall Visual Description:**
- Complete description of what is shown in the image

**Text Elements:**
- Identify and transcribe ALL text present in the image
- Categorize each text element as:
  * "Headline Hook" (designed to grab attention)
  * "Value Proposition" (explains the benefit to the viewer)
  * "Call to Action (CTA)" (tells the viewer what to do next)
  * "Social Proof" (customer logos, stats, testimonials, analyst quotes)
  * "Disclaimer" (legal text, terms, conditions)
  * "Brand Name" (company or product names)
  * "Other" (any other text)

**People Description:**
- For each person visible: age range, gender, appearance, clothing, pose, facial expression, setting
- Whether they read as executives, practitioners, customers, or stock photography

**Brand Elements:**
- Logos present (describe and position), including any co-marketing or customer logos
- Product shots and UI screenshots (describe what is shown)
- Brand colors or visual identity elements

**Composition & Layout:**
- Layout structure (grid, asymmetrical, centered, etc.)
- Visual hierarchy (what draws attention first, second, third)
- Element positioning (top-left, center, bottom-right, etc.)
- Aspect ratio and whether it suits the LinkedIn feed
- Use of composition techniques (rule of thirds, leading lines, symmetry, etc.)

**Colors & Visual Style:**
- List ALL dominant colors (specific color names or hex codes if possible)
- Background color/type and style
- Style register (corporate photography, flat illustration, data-viz, screenshot, meme-style, etc.)
- Any filters, effects, or styling applied

**B2B Offer Signals:**
- What is actually being offered (demo, webinar, report/whitepaper, free trial, event, job posting)
- Funnel stage the creative implies (awareness, consideration, conversion)
- Seniority and function the creative appears aimed at (e.g. IT decision-makers, HR leaders, developers)
- Any gating cues (form fill, "download", "register")

**Technical & Target Audience Indicators:**
- Text readability and contrast
- Overall image quality
- Visual cues about target audience (industry, company size, role, seniority)
- Setting/environment details

**Message & Theme:**
- What story or message the visual conveys
- Emotional tone and mood
- Marketing strategy indicators

Extract ALL this information comprehensively. The presentation format (summary vs detailed breakdown) will be determined based on the user's specific request context.
"""

        result = {
            "success": True,
            "message": "Image downloaded and ready for analysis.",
            "cached": bool(cached_data),
            "image_data": image_data,
            "media_url": media_url,
            "brand_name": brand_name,
            "ad_id": ad_id,
            "analysis_instructions": analysis_prompt,
            "ad_library_url": AD_LIBRARY_URL,
            "source_citation": f"[LinkedIn Ad Library - {brand_name if brand_name else 'Ad'} #{ad_id if ad_id else 'Unknown'}]({media_url})",
            "cache_status": "Used cached image" if cached_data else "Downloaded and cached new image",
            "error": None
        }

        return result

    except requests.exceptions.RequestException as e:
        return {
            "success": False,
            "message": f"Failed to download image from {media_url}: {str(e)}",
            "cached": False,
            "analysis": {},
            "cache_info": {},
            "error": f"Network error: {str(e)}"
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"Failed to process image from {media_url}: {str(e)}",
            "cached": False,
            "analysis": {},
            "cache_info": {},
            "error": str(e)
        }


@mcp.tool(
  description="REQUIRED for checking media cache status and storage usage. Use this tool when users ask about cache statistics, storage space used by cached media (images and videos), or how many files have been analyzed and cached. Essential for cache management and monitoring.",
  annotations={
    "title": "Get Media Cache Statistics",
    "readOnlyHint": True,
    "openWorldHint": False
  }
)
def get_cache_stats() -> Dict[str, Any]:
    """Get comprehensive statistics about the media cache (images and videos).

    Returns:
        A dictionary containing:
        - success: Boolean indicating if stats were retrieved successfully
        - message: Status message
        - stats: Cache statistics including:
            * total_files: Total number of cached files
            * total_images: Number of cached images
            * total_videos: Number of cached videos
            * total_size_mb/gb: Storage space used
            * analyzed_files: Number of files with cached analysis
            * unique_brands: Number of different brands cached
        - error: Error details if retrieval failed
    """
    try:
        stats = media_cache.get_cache_stats()

        total_files = stats.get('total_files', 0)
        total_images = stats.get('total_images', 0)
        total_videos = stats.get('total_videos', 0)

        return {
            "success": True,
            "message": f"Cache contains {total_files} files ({total_images} images, {total_videos} videos) using {stats.get('total_size_gb', 0)}GB storage",
            "stats": stats,
            "error": None
        }

    except Exception as e:
        return {
            "success": False,
            "message": f"Failed to retrieve cache statistics: {str(e)}",
            "stats": {},
            "error": str(e)
        }


@mcp.tool(
  description="REQUIRED for finding previously analyzed ad media (images and videos) in cache. Use this tool when users want to search for cached media by brand name, find media with people, search by colors, or filter by media type. Essential for retrieving past analysis results without re-downloading media.",
  annotations={
    "title": "Search Cached Media",
    "readOnlyHint": True,
    "openWorldHint": True
  }
)
def search_cached_media(
    brand_name: Optional[str] = None,
    has_people: Optional[bool] = None,
    color_contains: Optional[str] = None,
    media_type: Optional[str] = None,
    limit: Optional[int] = 20
) -> Dict[str, Any]:
    """Search cached media (images and videos) by various criteria.

    Args:
        brand_name: Filter by exact brand name match
        has_people: Filter by presence of people in media (True/False)
        color_contains: Filter by dominant color (partial match, e.g., "red", "blue")
        media_type: Filter by media type ('image' or 'video')
        limit: Maximum number of results to return (default: 20)

    Returns:
        A dictionary containing:
        - success: Boolean indicating if search was successful
        - message: Status message
        - results: List of matching cached media with metadata
        - count: Number of results returned
        - error: Error details if search failed
    """
    try:
        results = media_cache.search_cached_media(
            brand_name=brand_name,
            has_people=has_people,
            color_contains=color_contains,
            media_type=media_type
        )

        # Limit results
        if limit and len(results) > limit:
            results = results[:limit]

        # Remove large base64 data from results for cleaner output
        clean_results = []
        for result in results:
            clean_result = result.copy()
            if 'analysis_results' in clean_result and clean_result['analysis_results']:
                # Keep analysis but remove any base64 image data if present
                analysis = clean_result['analysis_results'].copy()
                if 'image_data_base64' in analysis:
                    analysis['image_data_base64'] = "[Image data available]"
                clean_result['analysis_results'] = analysis
            clean_results.append(clean_result)

        search_criteria = []
        if brand_name:
            search_criteria.append(f"brand: {brand_name}")
        if has_people is not None:
            search_criteria.append(f"has_people: {has_people}")
        if color_contains:
            search_criteria.append(f"color: {color_contains}")
        if media_type:
            search_criteria.append(f"media_type: {media_type}")

        criteria_str = ", ".join(search_criteria) if search_criteria else "no filters"

        return {
            "success": True,
            "message": f"Found {len(clean_results)} cached media files matching criteria: {criteria_str}",
            "results": clean_results,
            "count": len(clean_results),
            "error": None
        }

    except Exception as e:
        return {
            "success": False,
            "message": f"Failed to search cached media: {str(e)}",
            "results": [],
            "count": 0,
            "error": str(e)
        }


@mcp.tool(
  description="REQUIRED for cleaning up old cached media files (images and videos) and freeing disk space. Use this tool when users want to remove old cached media, clean up storage space, or when cache becomes too large. Essential for cache maintenance and storage management.",
  annotations={
    "title": "Cleanup Media Cache",
    "readOnlyHint": False,
    "openWorldHint": False
  }
)
def cleanup_media_cache(max_age_days: Optional[int] = 30) -> Dict[str, Any]:
    """Clean up old cached media files (images and videos) and database entries.

    Args:
        max_age_days: Maximum age in days before media files are deleted (default: 30)

    Returns:
        A dictionary containing:
        - success: Boolean indicating if cleanup was successful
        - message: Status message with cleanup results
        - cleanup_stats: Statistics about what was cleaned up
        - error: Error details if cleanup failed
    """
    try:
        # Get stats before cleanup
        stats_before = media_cache.get_cache_stats()

        # Perform cleanup
        media_cache.cleanup_old_cache(max_age_days=max_age_days or 30)

        # Get stats after cleanup
        stats_after = media_cache.get_cache_stats()

        files_removed = stats_before.get('total_files', 0) - stats_after.get('total_files', 0)
        images_removed = stats_before.get('total_images', 0) - stats_after.get('total_images', 0)
        videos_removed = stats_before.get('total_videos', 0) - stats_after.get('total_videos', 0)
        space_freed_mb = stats_before.get('total_size_mb', 0) - stats_after.get('total_size_mb', 0)

        return {
            "success": True,
            "message": f"Cleanup completed: removed {files_removed} files ({images_removed} images, {videos_removed} videos), freed {space_freed_mb:.2f}MB",
            "cleanup_stats": {
                "total_files_removed": files_removed,
                "images_removed": images_removed,
                "videos_removed": videos_removed,
                "space_freed_mb": round(space_freed_mb, 2),
                "max_age_days": max_age_days or 30,
                "files_remaining": stats_after.get('total_files', 0),
                "images_remaining": stats_after.get('total_images', 0),
                "videos_remaining": stats_after.get('total_videos', 0),
                "space_remaining_mb": stats_after.get('total_size_mb', 0)
            },
            "error": None
        }

    except Exception as e:
        return {
            "success": False,
            "message": f"Failed to cleanup cache: {str(e)}",
            "cleanup_stats": {},
            "error": str(e)
        }


# Backward compatibility aliases
def search_cached_images(brand_name: Optional[str] = None, has_people: Optional[bool] = None,
                        color_contains: Optional[str] = None, limit: Optional[int] = 20) -> Dict[str, Any]:
    """Search cached images by criteria (backward compatibility)."""
    return search_cached_media(brand_name, has_people, color_contains, 'image', limit)

cleanup_image_cache = cleanup_media_cache


VIDEO_ANALYSIS_PROMPT = """
Analyze this LinkedIn ad video and provide a comprehensive, structured breakdown following this exact format:

**SCENE ANALYSIS:**
Analyze the video at a scene-by-scene level. For each identified scene, provide:

Scene [Number]: [Brief scene title]
1. Visual Description:
   - Detailed description of key visuals within the scene
   - Appearance and apparent role of featured individuals (executive, practitioner, customer, presenter)
   - Specific camera angles and movements used

2. Text Elements:
   - Document ALL text elements appearing in the scene, including burned-in subtitles
   - Categorize each text element as:
     * "Text Hook" (introductory text designed to grab attention)
     * "CTA (middle)" (call-to-action appearing mid-video)
     * "CTA (end)" (final call-to-action)
     * "Proof Point" (stats, customer names, analyst quotes)

3. Brand Elements:
   - Note any visible brand logos, customer logos or product/UI placements
   - Provide brief descriptions and specific timing within the scene

4. Audio Analysis:
   - Transcription or detailed summary of any voiceover or on-camera speech
   - Describe delivery characteristics: tone, pace, formality
   - Identify and briefly describe notable sound effects
   - Note whether the ad is intelligible with sound off (LinkedIn feed autoplays muted)

5. Music Analysis:
   - Music present: [true/false]
   - If true: Brief description of music style and how it sets the register

6. Scene Transition:
   - Describe the style and pacing of transition to next scene

**OVERALL VIDEO ANALYSIS:**

**Ad Format:**
- Identify the specific format (talking head, customer testimonial, product demo, event promo, animated explainer, etc.)
- Aspect ratio and orientation, and whether it suits the LinkedIn feed
- Duration and pacing style

**Sound-Off Readability:**
- Would this ad land for a viewer scrolling with sound off? Evidence for the assessment
- Are subtitles or on-screen text carrying the message?

**Notable Angles:**
- List all significant camera angles used throughout the video
- Comment on their effectiveness and purpose

**Overall Messaging:**
- Primary message or value proposition
- Secondary messages or supporting points
- Target audience indicators (industry, company size, role, seniority)

**B2B Offer & Funnel Stage:**
- What is actually being offered (demo, webinar, report, trial, event)
- Funnel stage the creative implies (awareness, consideration, conversion)

**Hook Analysis:**
- Primary hook type: Text, Visual, or VoiceOver
- What happens in the first 3 seconds specifically
- Effectiveness assessment of attention-grabbing elements

Provide detailed, factual observations that would help understand the video's marketing strategy and effectiveness. Focus on specific, actionable insights.
"""


@mcp.tool(
  description="REQUIRED for analyzing video ads from LinkedIn. Downloads and analyzes ad videos using Gemini's video understanding to extract the hook, scene-by-scene storytelling, on-screen text, voiceover, sound-off readability and B2B offer positioning. Pass ad_id alongside media_url so results cache per ad rather than per (expiring) CDN URL. Uses intelligent caching for efficiency.",
  annotations={
    "title": "Analyze Ad Video Content",
    "readOnlyHint": True,
    "openWorldHint": True
  }
)
def analyze_ad_video(media_url: str, ad_id: Optional[str] = None, brand_name: Optional[str] = None) -> Dict[str, Any]:
    """Download LinkedIn ad videos and analyze them using Gemini's video understanding capabilities.

    Args:
        media_url: The direct URL to the LinkedIn ad video (the `video` field on an ad).
        ad_id: Optional ad ID. Pass it when you have it — LinkedIn CDN URLs carry
               expiry parameters, so keying the cache on the ad id means a second
               look at the same ad is free even once the URL has rotated.
        brand_name: Optional brand name for cache organization.

    Returns:
        A dictionary containing:
        - success: Boolean indicating if analysis was successful
        - message: Status message
        - cached: Boolean indicating if the analysis came from cache
        - analysis: Comprehensive video analysis results
        - media_url: Original video URL
        - cache_status: Information about cache usage
        - error: Error details if analysis failed
    """
    if not media_url or not media_url.strip():
        return {
            "success": False,
            "message": "Media URL must be provided and cannot be empty.",
            "cached": False,
            "analysis": {},
            "cache_info": {},
            "error": "Missing or empty media URL"
        }

    media_url = media_url.strip()
    ad_id = str(ad_id).strip() if ad_id else None

    # Key the cache on the ad id when we have one. LinkedIn CDN URLs carry expiry
    # parameters that rotate, so a URL-keyed cache would miss on the same ad.
    cache_key = f"linkedin:ad:{ad_id}" if ad_id else media_url

    cached_data = None
    gemini_file = None
    try:
        cached_data = media_cache.get_cached_media(cache_key, media_type='video')

        if cached_data and cached_data.get('analysis_results'):
            return {
                "success": True,
                "message": f"Retrieved cached video analysis for {ad_id or media_url}",
                "cached": True,
                "analysis": cached_data['analysis_results'],
                "cache_info": {
                    "cached_at": cached_data.get('downloaded_at'),
                    "analysis_cached_at": cached_data.get('analysis_cached_at'),
                    "file_size": cached_data.get('file_size'),
                    "brand_name": cached_data.get('brand_name'),
                    "ad_id": cached_data.get('ad_id'),
                    "duration_seconds": cached_data.get('duration_seconds')
                },
                "ad_library_url": AD_LIBRARY_URL,
                "source_citation": f"[LinkedIn Ad Library - {brand_name if brand_name else 'Ad'} #{ad_id if ad_id else 'Unknown'}]({AD_LIBRARY_URL})",
                "error": None
            }

        video_path = None
        file_size = None
        duration_seconds = None
        content_type = None

        if cached_data:
            # Video is cached but no analysis results yet
            video_path = cached_data['file_path']
            file_size = cached_data['file_size']
            duration_seconds = cached_data.get('duration_seconds')
            content_type = cached_data.get('content_type')
        else:
            response = requests.get(media_url, timeout=60)  # Longer timeout for videos
            response.raise_for_status()

            content_type = response.headers.get('content-type', '').lower()
            if not any(vid_type in content_type for vid_type in ['video/', 'mp4', 'mov', 'webm', 'avi']):
                return {
                    "success": False,
                    "message": f"URL does not point to a valid video. Content type: {content_type}",
                    "cached": False,
                    "analysis": {},
                    "cache_info": {},
                    "error": f"Invalid content type: {content_type}"
                }

            video_path = media_cache.cache_media(
                url=cache_key,
                media_data=response.content,
                content_type=content_type,
                media_type='video',
                brand_name=brand_name,
                ad_id=ad_id
            )
            file_size = len(response.content)

        # Configure Gemini API
        try:
            client = configure_gemini()
        except Exception as e:
            return {
                "success": False,
                "message": f"Failed to configure Gemini API: {str(e)}. Ensure --gemini-api-key is provided or GEMINI_API_KEY environment variable is set.",
                "cached": bool(cached_data),
                "analysis": {},
                "cache_info": {},
                "error": f"Gemini configuration error: {str(e)}"
            }

        # Upload video to Gemini and analyze
        gemini_file = upload_video_to_gemini(client, video_path)
        analysis_text = analyze_video_with_gemini(client, gemini_file, VIDEO_ANALYSIS_PROMPT)

        analysis_results = {
            "raw_analysis": analysis_text,
            "model_used": os.getenv("GEMINI_MODEL", "gemini-2.0-flash-exp"),
            "video_metadata": {
                "file_size_mb": round(file_size / (1024 * 1024), 2) if file_size else None,
                "duration_seconds": duration_seconds,
                "content_type": content_type
            }
        }

        media_cache.update_analysis_results(cache_key, analysis_results)
        cleanup_gemini_file(client, gemini_file.name)
        gemini_file = None

        return {
            "success": True,
            "message": "Video analysis completed successfully",
            "cached": bool(cached_data),
            "analysis": analysis_results,
            "media_url": media_url,
            "brand_name": brand_name,
            "ad_id": ad_id,
            "cache_status": "Used cached video" if cached_data else "Downloaded and cached new video",
            "ad_library_url": AD_LIBRARY_URL,
            "source_citation": f"[LinkedIn Ad Library - {brand_name if brand_name else 'Ad'} #{ad_id if ad_id else 'Unknown'}]({AD_LIBRARY_URL})",
            "error": None
        }

    except requests.exceptions.RequestException as e:
        return {
            "success": False,
            "message": f"Failed to download video from {media_url}: {str(e)}",
            "cached": False,
            "analysis": {},
            "cache_info": {},
            "error": f"Network error: {str(e)}"
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"Failed to analyze video from {media_url}: {str(e)}",
            "cached": bool(cached_data),
            "analysis": {},
            "cache_info": {},
            "error": str(e)
        }
    finally:
        # Gemini file uploads are billed storage; drop them even on the error path.
        if gemini_file is not None:
            try:
                cleanup_gemini_file(configure_gemini(), gemini_file.name)
            except Exception:
                pass


if __name__ == "__main__":
   mcp.run()
