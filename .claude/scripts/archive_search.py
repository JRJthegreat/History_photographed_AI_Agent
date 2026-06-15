#!/usr/bin/env python3
"""
archive_search.py — Public-domain photo search.

MVP: Wikimedia Commons only. Production cut extends to LoC, Europeana, NARA, Getty Open.

Returns RAW archive metadata untouched. The photo-curator agent reads structured fields
and never invents dates or licenses.

Usage:
    python archive_search.py "Halifax explosion 1917" --max 20
    python archive_search.py "Halifax explosion 1917" --max 20 --json
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Optional
from urllib.parse import urlencode

import requests

WIKIMEDIA_API = "https://commons.wikimedia.org/w/api.php"
USER_AGENT = "HistoryPhotographedAIAgent/0.1 (contact: info@damiermedia.com)"

LICENSE_ALLOWLIST = {
    "pd-us",
    "pd-1923",
    "pd-old",
    "pd-art",
    "pd-self",
    "cc0",
    "cc-zero",
    "noknowncopyrightrestrictions",
    "no known copyright restrictions",
    "public domain",
}


def _license_tag_from_imageinfo(imageinfo: dict) -> Optional[str]:
    """Extract a normalized license tag from Wikimedia extmetadata."""
    extmeta = imageinfo.get("extmetadata", {})
    license_short = (extmeta.get("LicenseShortName", {}).get("value") or "").strip()
    if license_short:
        return license_short
    license_field = (extmeta.get("License", {}).get("value") or "").strip()
    return license_field or None


def _is_in_allowlist(tag: Optional[str]) -> bool:
    if not tag:
        return False
    return tag.lower() in LICENSE_ALLOWLIST


def search_wikimedia(query: str, max_results: int = 20) -> list[dict]:
    """Search Wikimedia Commons for files matching the query.

    Returns a list of candidate dicts with raw archive metadata.
    """
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    search_params = {
        "action": "query",
        "format": "json",
        "list": "search",
        "srsearch": query,
        "srnamespace": 6,  # File: namespace
        "srlimit": max(max_results * 2, 20),
    }
    r = session.get(WIKIMEDIA_API, params=search_params, timeout=30)
    r.raise_for_status()
    hits = r.json().get("query", {}).get("search", [])
    if not hits:
        return []

    titles = [h["title"] for h in hits]
    candidates: list[dict] = []

    # imageinfo fetches in batches of 50
    for i in range(0, len(titles), 50):
        batch = titles[i : i + 50]
        info_params = {
            "action": "query",
            "format": "json",
            "titles": "|".join(batch),
            "prop": "imageinfo",
            "iiprop": "url|size|extmetadata|mime|mediatype",
            "iiextmetadatafilter": (
                "LicenseShortName|License|UsageTerms|Artist|Credit"
                "|DateTime|DateTimeOriginal|ObjectName|ImageDescription"
            ),
        }
        r = session.get(WIKIMEDIA_API, params=info_params, timeout=30)
        r.raise_for_status()
        pages = r.json().get("query", {}).get("pages", {})
        for _, page in pages.items():
            ii_list = page.get("imageinfo") or []
            if not ii_list:
                continue
            ii = ii_list[0]
            if ii.get("mediatype") not in (None, "BITMAP", "DRAWING"):
                continue
            license_tag = _license_tag_from_imageinfo(ii)
            if not _is_in_allowlist(license_tag):
                continue

            extmeta = ii.get("extmetadata", {})
            title = page.get("title", "")
            archive_id = title.replace("File:", "").rsplit(".", 1)[0]
            date_raw = (
                extmeta.get("DateTimeOriginal", {}).get("value")
                or extmeta.get("DateTime", {}).get("value")
                or ""
            ).strip()
            creator = (extmeta.get("Artist", {}).get("value") or "").strip()
            description = (extmeta.get("ImageDescription", {}).get("value") or "").strip()

            candidates.append(
                {
                    "source": "wikimedia",
                    "source_url": ii.get("descriptionurl") or "",
                    "archive_id": archive_id,
                    "title": title.replace("File:", ""),
                    "creator": creator,
                    "description_raw": description,
                    "recorded_date_raw": date_raw,
                    "license_tag": license_tag,
                    "image_url": ii.get("url") or "",
                    "dimensions": [ii.get("width", 0), ii.get("height", 0)],
                    "mime": ii.get("mime") or "",
                }
            )
            if len(candidates) >= max_results:
                return candidates

    return candidates


def main() -> int:
    parser = argparse.ArgumentParser(description="Search public-domain archives")
    parser.add_argument("query", help="Search query (e.g., 'Halifax explosion 1917')")
    parser.add_argument("--max", type=int, default=20, help="Max results (default: 20)")
    parser.add_argument("--json", action="store_true", help="Emit JSON (default: pretty)")
    args = parser.parse_args()

    candidates = search_wikimedia(args.query, args.max)
    if args.json:
        json.dump(candidates, sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
    else:
        print(f"Found {len(candidates)} candidates with allowed licenses\n")
        for c in candidates:
            print(f"  • {c['title']}")
            print(f"    license: {c['license_tag']}")
            print(f"    date:    {c['recorded_date_raw'] or '(unspecified)'}")
            print(f"    dims:    {c['dimensions'][0]}×{c['dimensions'][1]}")
            print(f"    url:     {c['source_url']}")
            print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
