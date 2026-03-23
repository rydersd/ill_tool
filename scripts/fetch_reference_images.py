#!/usr/bin/env python3
"""
Fetch reference images from a URL (Pinterest board, gallery page, etc.)
for composite DNA synthesis.

USAGE:
    uv run python scripts/fetch_reference_images.py --url <url> [--count N] [--output-dir <path>]
    uv run python scripts/fetch_reference_images.py --url <url> --dna-name designers-republic --optimize

OPTIONS:
    --url         Source URL to scrape images from (required)
    --count       Maximum number of images to download (default: 12)
    --output-dir  Directory to save images (default: auto-created temp dir)
    --dna-name    Design DNA aesthetic name — auto-saves to .backup/claude/memory/design-dna/images/{name}/
    --optimize    Convert downloaded images to WebP (quality 60, max 1200px dimension, ~80-120KB each)

OUTPUT:
    JSON to stdout with image paths, metadata, and any warnings.

EXAMPLES:
    uv run python scripts/fetch_reference_images.py --url "https://pinterest.com/user/board/"
    uv run python scripts/fetch_reference_images.py --url "https://example.com/gallery" --count 8
    uv run python scripts/fetch_reference_images.py --url "https://dribbble.com/shots" --output-dir ./refs
    uv run python scripts/fetch_reference_images.py --url "https://pinterest.com/user/board/" --dna-name designers-republic --optimize
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


# ── Optional Pillow import for --optimize flag ──────────────────────────
# Pillow is required only when --optimize is used. Import lazily so the
# script works for basic downloads without it installed.
_PIL_AVAILABLE = False
try:
    from PIL import Image
    _PIL_AVAILABLE = True
except ImportError:
    pass


# Minimum image dimension heuristic — skip tiny icons/avatars
MIN_DIMENSION_HEURISTIC = 200

# WebP optimization defaults
OPTIMIZE_MAX_DIMENSION = 1200
OPTIMIZE_QUALITY = 60

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


def optimize_image(src_path: Path, dst_path: Path, max_dim: int = OPTIMIZE_MAX_DIMENSION, quality: int = OPTIMIZE_QUALITY) -> dict:
    """Convert an image to WebP with constrained dimensions.

    Resizes to fit within max_dim x max_dim (preserving aspect ratio) and
    saves as WebP at the given quality level. Target: ~80-120KB per image,
    compressed enough for storage but retains enough visual detail for LLM
    vision analysis to identify composition, typography, density, and color.

    Returns metadata dict with original and optimized sizes.
    """
    if not _PIL_AVAILABLE:
        raise RuntimeError(
            "Pillow is required for --optimize. Install with: uv pip install Pillow"
        )

    img = Image.open(src_path)

    # Convert RGBA/palette to RGB for WebP compatibility
    if img.mode in ("RGBA", "P", "LA"):
        img = img.convert("RGB")

    # Resize if either dimension exceeds max_dim, preserving aspect ratio
    original_size = img.size
    if img.width > max_dim or img.height > max_dim:
        img.thumbnail((max_dim, max_dim), Image.LANCZOS)

    img.save(dst_path, format="WEBP", quality=quality, method=4)

    return {
        "original_dimensions": list(original_size),
        "optimized_dimensions": list(img.size),
        "original_bytes": src_path.stat().st_size,
        "optimized_bytes": dst_path.stat().st_size,
    }


def resolve_dna_image_dir(dna_name: str) -> Path:
    """Resolve the image directory for a named Design DNA aesthetic.

    Looks for the DNA image storage relative to the project root:
        .backup/claude/memory/design-dna/images/{dna_name}/

    Creates the directory structure if it doesn't exist.
    """
    # Walk up from this script's location to find the project root
    # (script is at scripts/fetch_reference_images.py, root is one level up)
    project_root = Path(__file__).resolve().parent.parent
    dna_dir = project_root / ".backup" / "claude" / "memory" / "design-dna" / "images" / dna_name
    dna_dir.mkdir(parents=True, exist_ok=True)
    return dna_dir


def update_manifest(dna_dir: Path, images: list[dict], source_url: str) -> None:
    """Update the manifest.json in a DNA image directory with new image entries.

    Reads the existing manifest (if any), appends new image entries, and
    writes it back. Preserves existing key_observations and metadata.
    """
    manifest_path = dna_dir / "manifest.json"

    # Load existing manifest or create a new one
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text())
    else:
        manifest = {
            "aesthetic": dna_dir.name,
            "source": source_url,
            "image_count": 0,
            "format": "webp",
            "max_dimension": OPTIMIZE_MAX_DIMENSION,
            "quality": OPTIMIZE_QUALITY,
            "key_observations": [],
            "images": [],
        }

    # Build entries for newly added images
    for img in images:
        entry = {
            "file": Path(img["path"]).name,
            "original_url": img.get("original_url", ""),
            "size_bytes": img.get("optimized_bytes", img.get("size_bytes", 0)),
            "analysis": {
                "density": None,
                "typography_dominance": None,
                "composition": None,
                "hierarchy_contrast": None,
            },
        }
        # Include optimization metadata when available
        if "optimized_dimensions" in img:
            entry["dimensions"] = img["optimized_dimensions"]
        manifest["images"].append(entry)

    manifest["image_count"] = len(manifest["images"])
    manifest["source"] = source_url

    manifest_path.write_text(json.dumps(manifest, indent=4))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fetch reference images from a URL for composite DNA synthesis",
    )
    parser.add_argument("--url", required=True, help="Source URL to scrape images from")
    parser.add_argument("--count", type=int, default=12, help="Max images to download (default: 12)")
    parser.add_argument("--output-dir", help="Output directory (default: auto temp dir)")
    parser.add_argument(
        "--dna-name",
        help="Design DNA aesthetic name — auto-saves to .backup/claude/memory/design-dna/images/{name}/",
    )
    parser.add_argument(
        "--optimize",
        action="store_true",
        help="Convert images to WebP (quality 60, max 1200px) for efficient storage + LLM vision analysis",
    )
    args = parser.parse_args()

    # Validate --optimize has Pillow available
    if args.optimize and not _PIL_AVAILABLE:
        print(
            json.dumps({
                "error": "Pillow is required for --optimize. Install with: uv pip install Pillow",
            }),
        )
        sys.exit(1)

    # Setup output directory — --dna-name takes precedence over --output-dir
    if args.dna_name:
        output_dir = resolve_dna_image_dir(args.dna_name)
    elif args.output_dir:
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

    # Post-process: optimize images to WebP if requested
    if args.optimize and downloaded:
        optimized_images = []
        for img_info in downloaded:
            src = Path(img_info["path"])
            # Target filename: ref_NNN.webp (replace original extension)
            dst = src.with_suffix(".webp")

            try:
                opt_meta = optimize_image(src, dst)
                # Remove original if it's a different file than the optimized output
                if src != dst and src.exists():
                    src.unlink()
                # Update the image info with optimization data
                img_info["path"] = str(dst)
                img_info["optimized_bytes"] = opt_meta["optimized_bytes"]
                img_info["original_bytes"] = opt_meta["original_bytes"]
                img_info["optimized_dimensions"] = opt_meta["optimized_dimensions"]
                img_info["original_dimensions"] = opt_meta["original_dimensions"]
                optimized_images.append(img_info)
            except Exception as e:
                warnings.append(f"Failed to optimize {src.name}: {e}")
                # Keep the original if optimization fails
                optimized_images.append(img_info)

        downloaded = optimized_images

    # Update manifest.json if saving to a DNA directory
    if args.dna_name and downloaded:
        update_manifest(output_dir, downloaded, args.url)

    # Build output
    result = {
        "source_url": args.url,
        "output_dir": str(output_dir),
        "images": downloaded,
        "downloaded": len(downloaded),
        "total_found": len(image_urls),
        "warnings": warnings,
    }

    if args.dna_name:
        result["dna_name"] = args.dna_name
        result["manifest_path"] = str(output_dir / "manifest.json")

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
