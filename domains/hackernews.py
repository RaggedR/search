"""Hacker News domain using the Algolia API."""

from __future__ import annotations

import time

import httpx

from domains.base import Domain, Item
from engine import compute_breakout_score


class HackerNewsDomain(Domain):
    name = "hn"

    async def search(
        self, query: str, max_popularity: int, days: int, limit: int
    ) -> list[Item]:
        cutoff = int(time.time()) - (days * 86400)
        params = {
            "query": query,
            "tags": "story",
            "numericFilters": f"points>5,created_at_i>{cutoff}",
            "hitsPerPage": min(limit * 3, 200),  # fetch extra, we'll trim
        }

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                "https://hn.algolia.com/api/v1/search", params=params
            )
            resp.raise_for_status()
            data = resp.json()

        items: list[Item] = []
        now = time.time()

        for hit in data.get("hits", []):
            points = hit.get("points", 0) or 0
            created = hit.get("created_at_i", now)
            age_days = max((now - created) / 86400, 0.01)
            hours = age_days * 24

            item = Item(
                title=hit.get("title", "") or "",
                url=f"https://news.ycombinator.com/item?id={hit['objectID']}",
                author=hit.get("author", ""),
                popularity=1,  # HN has no follower concept
                activity=float(points),
                age_days=age_days,
                domain=self.name,
                metadata={
                    "points": points,
                    "num_comments": hit.get("num_comments", 0),
                    "source_url": hit.get("url", ""),
                    "points_per_hour": points / max(hours, 0.1),
                },
            )
            item.breakout_score = compute_breakout_score(item)
            items.append(item)

        items.sort(key=lambda x: x.breakout_score, reverse=True)
        return items[:limit]
