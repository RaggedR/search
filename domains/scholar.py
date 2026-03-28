"""Semantic Scholar domain using their public API.

Rate limit: 5,000 requests per 5 minutes (unauthenticated).
Includes retry with backoff for 429 responses.
"""

from __future__ import annotations

import asyncio
import math

import httpx

from domains.base import Domain, Item
from engine import compute_breakout_score

API_BASE = "https://api.semanticscholar.org/graph/v1"


class ScholarDomain(Domain):
    name = "scholar"

    async def search(
        self, query: str, max_popularity: int, days: int, limit: int
    ) -> list[Item]:
        fields = "title,url,authors,citationCount,influentialCitationCount,year,externalIds,citationStyles"
        params = {
            "query": query,
            "limit": min(limit * 3, 100),
            "fields": fields,
        }

        async with httpx.AsyncClient(timeout=20) as client:
            # Retry with backoff on 429
            for attempt in range(3):
                resp = await client.get(
                    f"{API_BASE}/paper/search", params=params
                )
                if resp.status_code == 429:
                    wait = 2 ** attempt
                    print(f"  Rate limited, retrying in {wait}s...")
                    await asyncio.sleep(wait)
                    continue
                resp.raise_for_status()
                break
            else:
                print("  Semantic Scholar rate limit exceeded. Try again later.")
                return []
            data = resp.json()

        items: list[Item] = []

        for paper in data.get("data", []):
            citation_count = paper.get("citationCount", 0) or 0
            if citation_count > max_popularity:
                continue

            influential = paper.get("influentialCitationCount", 0) or 0
            year = paper.get("year")
            if year:
                # Rough age: assume mid-year publication
                age_days = max((2026 - year) * 365 + 180, 1)
            else:
                age_days = 365  # default 1 year if unknown

            # Citation velocity approximation: influential citations
            # carry more weight as a momentum signal
            velocity = influential * 5 + citation_count * 0.5

            authors = paper.get("authors", [])
            author_str = ", ".join(a.get("name", "") for a in authors[:3])
            if len(authors) > 3:
                author_str += f" +{len(authors) - 3}"

            paper_url = paper.get("url", "")
            doi = (paper.get("externalIds") or {}).get("DOI", "")

            item = Item(
                title=paper.get("title", ""),
                url=paper_url or (f"https://doi.org/{doi}" if doi else ""),
                author=author_str,
                popularity=citation_count,
                activity=velocity,
                age_days=age_days,
                domain=self.name,
                metadata={
                    "influential_citations": influential,
                    "year": year,
                    "doi": doi,
                },
            )
            # Score: velocity / log(citations + 1)
            if citation_count > 0:
                item.breakout_score = velocity / (
                    math.log(citation_count + 1) * age_days
                )
            else:
                item.breakout_score = velocity / age_days
            items.append(item)

        items.sort(key=lambda x: x.breakout_score, reverse=True)
        return items[:limit]
