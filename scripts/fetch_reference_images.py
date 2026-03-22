#!/usr/bin/env python3
"""
Fetch reference images from a URL (Pinterest board, gallery page, etc.)
for composite DNA synthesis.

USAGE:
    uv run python scripts/fetch_reference_images.py --url <url> [--count N] [--output-dir <path>]

OPTIONS:
    --url         Source URL to scrape images from (required)
    --count       Maximum number of images to download (default: 12)
    --output-dir  Directory to save images (default: auto-created temp dir)

OUTPUT:
    JSON to stdout with image paths, metadata, and any warnings.

EXAMPLES:
    uv run python scripts/fetch_reference_images.py --url "https://pinterest.com/user/board/"
    uv run python scripts/fetch_reference_images.py --url "https://example.com/gallery" --count 8
    uv run python scripts/fetch_reference_images.py --url "https://dribbble.com/shots" --output-dir ./refs
"""

import argparse
import hashlib
import json
import re
import sys
import tempfile
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse

import httpx


# Minimum image dimension heuristic — skip tiny icons/avatars
MIN_DIMENSION_HEURISTIC = 200

# Common icon/avatar path fragments to filter out
SKIP_PATTERNS = [
    "/favicon", "/icon-", "/logo-", "/avatar", "/badge",
    "/emoji", "/flag-", "sprite", "1x1", "spacer",
    "/ads/", "/tracking/", "/pixel",
]

# Image file extensions we accept
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tiff"}


def is_image_url(url: str) -> bool:
    """Check if a URL likely points to an image."""
    parsed = urlparse(url)
    path_lower = parsed.path.lower()
    # Direct extension check
    if any(path_lower.endswith(ext) for ext in IMAGE_EXTENSIONS):
        return True
    # Pinterest/CDN patterns with size suffixes
    if re.search(r"/\d+x/", url) or re.search(r"/originals/", url):
        return True
    # Content-type will be checked during download
    return False


def should_skip(url: str) -> bool:
    """Filter out icons, avatars, tracking pixels, etc."""
    url_lower = url.lower()
    return any(pattern in url_lower for pattern in SKIP_PATTERNS)


def extract_images_from_html(html: str, base_url: str) -> list[str]:
    """
    Extract image URLs from HTML using multiple strategies.
    Returns deduplicated list of absolute URLs.
    """
    found: set[str] = set()

    # Strategy 1: <img src="..."> and <img srcset="...">
    for match in re.finditer(r'<img[^>]+src=["\']([^"\']+)["\']', html, re.IGNORECASE):
        found.add(match.group(1))
    for match in re.finditer(r'<img[^>]+srcset=["\']([^"\']+)["\']', html, re.IGNORECASE):
        # srcset has "url size, url size" format — take the largest
        candidates = match.group(1).split(",")
        for candidate in candidates:
            parts = candidate.strip().split()
            if parts:
                found.add(parts[0])

    # Strategy 2: <meta og:image> and <link rel="image_src">
    for match in re.finditer(
        r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
        html, re.IGNORECASE,
    ):
        found.add(match.group(1))
    for match in re.finditer(
        r'<link[^>]+rel=["\']image_src["\'][^>]+href=["\']([^"\']+)["\']',
        html, re.IGNORECASE,
    ):
        found.add(match.group(1))

    # Strategy 3: Pinterest-specific data-pin-media attribute
    for match in re.finditer(r'data-pin-media=["\']([^"\']+)["\']', html, re.IGNORECASE):
        found.add(match.group(1))

    # Strategy 4: JSON-LD image properties
    for match in re.finditer(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html, re.DOTALL | re.IGNORECASE,
    ):
        try:
            data = json.loads(match.group(1))
            _extract_json_images(data, found)
        except (json.JSONDecodeError, TypeError):
            pass

    # Strategy 5: Inline background-image: url(...)
    for match in re.finditer(r'background-image:\s*url\(["\']?([^"\')\s]+)["\']?\)', html, re.IGNORECASE):
        found.add(match.group(1))

    # Strategy 6: Pinterest pin image URL patterns in any attribute/script
    for match in re.finditer(r'(https?://i\.pinimg\.com/[^\s"\'<>]+)', html):
        found.add(match.group(1))

    # Resolve relative URLs and filter
    absolute_urls: list[str] = []
    seen: set[str] = set()
    for url in found:
        absolute = urljoin(base_url, url)
        # Normalize for dedup: strip query/fragment AND normalize Pinterest size variants
        # e.g., /170x/abc.jpg and /236x/abc.jpg and /originals/abc.jpg are the same image
        normalized = urlparse(absolute)._replace(query="", fragment="").geturl()
        normalized = re.sub(r"/\d+x/", "/_SIZE_/", normalized)  # collapse Pinterest size dirs
        if normalized not in seen and not should_skip(absolute):
            seen.add(normalized)
            absolute_urls.append(absolute)

    return absolute_urls


def _extract_json_images(data, found: set[str]) -> None:
    """Recursively extract image URLs from JSON-LD data."""
    if isinstance(data, dict):
        for key, value in data.items():
            if key in ("image", "thumbnailUrl", "contentUrl") and isinstance(value, str):
                found.add(value)
            elif key == "image" and isinstance(value, dict) and "url" in value:
                found.add(value["url"])
            else:
                _extract_json_images(value, found)
    elif isinstance(data, list):
        for item in data:
            _extract_json_images(item, found)


def try_pinterest_rss(url: str) -> list[str]:
    """
    Pinterest boards are JS-rendered. Try the RSS feed as a fallback.
    Format: {board_url}.rss → <media:content url="...">
    """
    rss_url = url.rstrip("/") + ".rss"
    try:
        with httpx.Client(timeout=15, follow_redirects=True) as client:
            resp = client.get(rss_url, headers={"User-Agent": "Mozilla/5.0"})
            if resp.status_code != 200:
                return []
            # Extract <media:content url="..."> from RSS XML
            urls = re.findall(r'<media:content\s+url=["\']([^"\']+)["\']', resp.text)
            return urls
    except httpx.HTTPError:
        return []


def upgrade_pinterest_url(url: str) -> str:
    """Upgrade Pinterest image URL to highest resolution available."""
    # Replace /236x/ or /474x/ or /564x/ with /originals/ for full res
    upgraded = re.sub(r"/\d+x/", "/originals/", url)
    return upgraded


def download_images(
    urls: list[str],
    output_dir: Path,
    max_count: int,
) -> list[dict]:
    """Download images, returning metadata for each successful download."""
    downloaded: list[dict] = []
    index = 0

    with httpx.Client(timeout=20, follow_redirects=True) as client:
        for url in urls:
            if index >= max_count:
                break

            try:
                # Upgrade Pinterest URLs to full resolution
                download_url = upgrade_pinterest_url(url) if "pinimg.com" in url else url

                resp = client.get(download_url, headers={"User-Agent": "Mozilla/5.0"})
                if resp.status_code != 200:
                    continue

                # Verify it's actually an image via content-type
                content_type = resp.headers.get("content-type", "")
                if not content_type.startswith("image/"):
                    continue

                # Skip small images (content-length heuristic: <5KB likely an icon)
                content_length = len(resp.content)
                if content_length < 5000:
                    continue

                # Determine extension from content-type
                ext_map = {
                    "image/jpeg": ".jpg",
                    "image/png": ".png",
                    "image/webp": ".webp",
                    "image/gif": ".gif",
                }
                ext = ext_map.get(content_type.split(";")[0].strip(), ".jpg")

                index += 1
                filename = f"ref_{index:03d}{ext}"
                filepath = output_dir / filename

                filepath.write_bytes(resp.content)

                downloaded.append({
                    "path": str(filepath),
                    "original_url": url,
                    "index": index,
                    "size_bytes": content_length,
                })

            except httpx.HTTPError:
                continue
            except OSError:
                continue

            # Brief pause to be respectful to servers
            time.sleep(0.25)

    return downloaded


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fetch reference images from a URL for composite DNA synthesis",
    )
    parser.add_argument("--url", required=True, help="Source URL to scrape images from")
    parser.add_argument("--count", type=int, default=12, help="Max images to download (default: 12)")
    parser.add_argument("--output-dir", help="Output directory (default: auto temp dir)")
    args = parser.parse_args()

    # Setup output directory
    if args.output_dir:
        output_dir = Path(args.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
    else:
        output_dir = Path(tempfile.mkdtemp(prefix="dna_synthesis_"))

    warnings: list[str] = []
    all_image_urls: list[str] = []

    # Detect Pinterest URLs
    is_pinterest = "pinterest.com" in args.url or "pinterest." in args.url

    # Fetch the page HTML
    try:
        with httpx.Client(timeout=20, follow_redirects=True) as client:
            resp = client.get(args.url, headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                              "AppleWebKit/537.36 (KHTML, like Gecko) "
                              "Chrome/120.0.0.0 Safari/537.36",
            })
            if resp.status_code == 200:
                all_image_urls = extract_images_from_html(resp.text, args.url)
            else:
                warnings.append(f"HTTP {resp.status_code} fetching {args.url}")
    except httpx.HTTPError as e:
        warnings.append(f"Failed to fetch page: {e}")

    # Pinterest fallback: if HTML yielded few images (JS-rendered), try RSS
    if is_pinterest and len(all_image_urls) < 3:
        warnings.append("Few images from HTML (Pinterest is JS-rendered). Trying RSS feed...")
        rss_urls = try_pinterest_rss(args.url)
        if rss_urls:
            all_image_urls.extend(rss_urls)
            warnings.append(f"Found {len(rss_urls)} images via Pinterest RSS feed")
        else:
            warnings.append(
                "Pinterest RSS also returned no images. "
                "Pinterest blocks scraping — alternatives:\n"
                "  1. Save images from the board manually to a local folder\n"
                "  2. Use the Pinterest API with a developer token\n"
                "  3. Provide direct image URLs instead of a board URL\n"
                "  4. Use a browser extension to bulk-download pin images"
            )

    # Filter to likely-image URLs
    image_urls = [u for u in all_image_urls if is_image_url(u) or "pinimg.com" in u]

    # If we have very few image-extension URLs, include all found URLs
    # (some CDNs serve images without extensions)
    if len(image_urls) < 3 and len(all_image_urls) > len(image_urls):
        image_urls = all_image_urls

    # Deduplicate by URL hash
    seen_hashes: set[str] = set()
    deduped: list[str] = []
    for url in image_urls:
        url_hash = hashlib.md5(url.encode()).hexdigest()
        if url_hash not in seen_hashes:
            seen_hashes.add(url_hash)
            deduped.append(url)
    image_urls = deduped

    # Download
    downloaded = download_images(image_urls, output_dir, args.count)

    # Build output
    result = {
        "source_url": args.url,
        "output_dir": str(output_dir),
        "images": downloaded,
        "downloaded": len(downloaded),
        "total_found": len(image_urls),
        "warnings": warnings,
    }

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
