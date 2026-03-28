"""Medium domain using tag RSS feeds.

Medium's JSON endpoints (?format=json) are dead (403 since ~2025).
RSS feeds at /feed/tag/{tag} still work — return 10 most recent articles.

Limitation: RSS has no clap/follower counts, so we use response metadata
(reading time, tag count) as a proxy and score primarily on recency.
To cover broader queries, we fetch multiple related tag feeds and deduplicate.

No auth needed.
"""

from __future__ import annotations

import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import httpx

from domains.base import Domain, Item
from engine import compute_breakout_score


class MediumDomain(Domain):
    name = "medium"

    async def search(
        self, query: str, max_popularity: int, days: int, limit: int
    ) -> list[Item]:
        tags = _query_to_tags(query)
        cutoff = time.time() - (days * 86400)

        async with httpx.AsyncClient(
            timeout=20, follow_redirects=True
        ) as client:
            all_items: dict[str, Item] = {}  # dedupe by URL

            for tag in tags:
                feed_items = await _fetch_tag_feed(client, tag, cutoff)
                for item in feed_items:
                    if item.url not in all_items:
                        all_items[item.url] = item

        items = list(all_items.values())
        items.sort(key=lambda x: x.breakout_score, reverse=True)
        return items[:limit]


async def _fetch_tag_feed(
    client: httpx.AsyncClient,
    tag: str,
    cutoff: float,
) -> list[Item]:
    """Fetch and parse a Medium tag RSS feed."""
    url = f"https://medium.com/feed/tag/{tag}"
    try:
        resp = await client.get(url)
        if resp.status_code != 200:
            return []
    except httpx.HTTPError:
        return []

    return _parse_rss(resp.text, cutoff)


def _parse_rss(xml_text: str, cutoff: float) -> list[Item]:
    """Parse Medium RSS XML into Items."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []

    # RSS uses <channel><item> structure
    channel = root.find("channel")
    if channel is None:
        return []

    # Namespace for dc:creator
    ns = {"dc": "http://purl.org/dc/elements/1.1/"}

    now = time.time()
    items: list[Item] = []

    for entry in channel.findall("item"):
        title = _text(entry, "title")
        link = _text(entry, "link")
        author = _text(entry, "dc:creator", ns) or _text(entry, "author")
        pub_date_str = _text(entry, "pubDate")

        if not title or not link:
            continue

        # Parse publication date
        pub_ts = _parse_pub_date(pub_date_str)
        if pub_ts is None or pub_ts < cutoff:
            continue

        age_days = max((now - pub_ts) / 86400, 0.01)

        # Extract categories (tags) — more tags = broader reach signal
        categories = [c.text for c in entry.findall("category") if c.text]

        # Extract reading time from description if available
        description = _text(entry, "description") or ""
        reading_time = _extract_reading_time(description)

        # Since RSS doesn't give us claps or follower counts, we use:
        # - activity = tag_count * 2 + reading_time (more tags = more discoverable)
        # - popularity = 1 (unknown, so we treat everyone equally)
        # The scoring then becomes purely about recency — which is the point:
        # we're finding *fresh* content from the long tail.
        activity = float(len(categories) * 2 + reading_time)

        item = Item(
            title=title,
            url=link,
            author=author,
            popularity=1,  # RSS doesn't expose follower counts
            activity=activity,
            age_days=age_days,
            domain="medium",
            metadata={
                "categories": categories,
                "reading_time_min": reading_time,
            },
        )
        item.breakout_score = compute_breakout_score(item)
        items.append(item)

    return items


def _text(el: ET.Element, tag: str, ns: dict | None = None) -> str:
    child = el.find(tag, ns or {})
    return (child.text or "").strip() if child is not None else ""


def _parse_pub_date(s: str) -> float | None:
    """Parse RFC 2822 date string to unix timestamp."""
    if not s:
        return None
    try:
        dt = parsedate_to_datetime(s)
        return dt.timestamp()
    except (ValueError, TypeError):
        return None


def _extract_reading_time(html: str) -> float:
    """Estimate reading time from description HTML (word count / 250 wpm)."""
    text = re.sub(r"<[^>]+>", " ", html)
    words = len(text.split())
    return round(words / 250, 1)


def _query_to_tags(query: str) -> list[str]:
    """Convert a search query to one or more Medium tag slugs.

    Medium tags are lowercase, hyphenated. We generate the main tag
    plus individual word tags for broader coverage.
    e.g. 'machine learning' -> ['machine-learning', 'machine', 'learning']
    """
    clean = re.sub(r"[^a-z0-9\s-]", "", query.lower().strip())
    main_tag = re.sub(r"\s+", "-", clean)
    tags = [main_tag]

    # Add individual words as separate tags if multi-word query
    words = clean.split()
    if len(words) > 1:
        tags.extend(words)

    return tags
