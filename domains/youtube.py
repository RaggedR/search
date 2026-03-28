"""YouTube domain using the Data API v3.

Quota budget per search: ~102 units out of 10,000/day.
- search.list: 100 units (up to 50 results)
- videos.list: 1 unit (batch of 50 IDs)
- channels.list: 1 unit per batch of 50
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
from dotenv import load_dotenv

from domains.base import Domain, Item
from engine import compute_breakout_score

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

API_BASE = "https://www.googleapis.com/youtube/v3"


class YouTubeDomain(Domain):
    name = "youtube"

    async def search(
        self, query: str, max_popularity: int, days: int, limit: int
    ) -> list[Item]:
        api_key = os.environ.get("YOUTUBE_API_KEY")
        if not api_key:
            raise RuntimeError(
                "YOUTUBE_API_KEY not set. Add it to .env or export it."
            )

        published_after = (
            datetime.now(timezone.utc) - timedelta(days=days)
        ).strftime("%Y-%m-%dT%H:%M:%SZ")

        async with httpx.AsyncClient(timeout=20) as client:
            # Step 1: Search for recent videos (100 quota units)
            search_resp = await client.get(
                f"{API_BASE}/search",
                params={
                    "part": "snippet",
                    "q": query,
                    "type": "video",
                    "order": "viewCount",
                    "publishedAfter": published_after,
                    "maxResults": 50,
                    "key": api_key,
                },
            )
            search_resp.raise_for_status()
            search_data = search_resp.json()

            video_ids = [
                item["id"]["videoId"]
                for item in search_data.get("items", [])
                if "videoId" in item.get("id", {})
            ]
            if not video_ids:
                return []

            # Step 2: Get video statistics (1 quota unit)
            videos_resp = await client.get(
                f"{API_BASE}/videos",
                params={
                    "part": "snippet,statistics",
                    "id": ",".join(video_ids),
                    "key": api_key,
                },
            )
            videos_resp.raise_for_status()
            videos_data = videos_resp.json()

            # Collect channel IDs for subscriber lookup
            channel_ids: set[str] = set()
            video_info: list[dict] = []
            for v in videos_data.get("items", []):
                ch_id = v["snippet"]["channelId"]
                channel_ids.add(ch_id)
                video_info.append({
                    "title": v["snippet"]["title"],
                    "channel_id": ch_id,
                    "channel_title": v["snippet"]["channelTitle"],
                    "published_at": v["snippet"]["publishedAt"],
                    "view_count": int(v["statistics"].get("viewCount", 0)),
                    "like_count": int(v["statistics"].get("likeCount", 0)),
                    "comment_count": int(v["statistics"].get("commentCount", 0)),
                    "video_id": v["id"],
                })

            # Step 3: Get channel subscriber counts (1 quota unit per batch of 50)
            channel_subs: dict[str, int] = {}
            ch_list = list(channel_ids)
            for i in range(0, len(ch_list), 50):
                batch = ch_list[i : i + 50]
                ch_resp = await client.get(
                    f"{API_BASE}/channels",
                    params={
                        "part": "statistics",
                        "id": ",".join(batch),
                        "key": api_key,
                    },
                )
                ch_resp.raise_for_status()
                for ch in ch_resp.json().get("items", []):
                    subs = int(ch["statistics"].get("subscriberCount", 0))
                    channel_subs[ch["id"]] = subs

            # Step 4: Filter and score
            now = datetime.now(timezone.utc)
            items: list[Item] = []

            for v in video_info:
                subs = channel_subs.get(v["channel_id"], 0)
                if subs > max_popularity:
                    continue

                published = datetime.fromisoformat(
                    v["published_at"].replace("Z", "+00:00")
                )
                age_days = max((now - published).total_seconds() / 86400, 0.1)

                item = Item(
                    title=v["title"],
                    url=f"https://youtube.com/watch?v={v['video_id']}",
                    author=v["channel_title"],
                    popularity=subs,
                    activity=float(v["view_count"]),
                    age_days=age_days,
                    domain=self.name,
                    metadata={
                        "likes": v["like_count"],
                        "comments": v["comment_count"],
                        "channel_id": v["channel_id"],
                        "views_per_sub": (
                            v["view_count"] / max(subs, 1)
                        ),
                    },
                )
                item.breakout_score = compute_breakout_score(item)
                items.append(item)

        items.sort(key=lambda x: x.breakout_score, reverse=True)
        return items[:limit]
