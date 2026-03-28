"""GitHub domain using the REST API."""

from __future__ import annotations

import math
import subprocess
from datetime import datetime, timedelta, timezone

import httpx

from domains.base import Domain, Item
from engine import compute_breakout_score


def _get_github_token() -> str | None:
    """Try to get a GitHub token from gh CLI."""
    try:
        result = subprocess.run(
            ["gh", "auth", "token"], capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return None


class GitHubDomain(Domain):
    name = "github"

    async def search(
        self, query: str, max_popularity: int, days: int, limit: int
    ) -> list[Item]:
        token = _get_github_token()
        headers = {"Accept": "application/vnd.github+json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"

        created_after = (
            datetime.now(timezone.utc) - timedelta(days=days)
        ).strftime("%Y-%m-%d")

        # Search for repos with stars in range, created recently
        q = f"{query} stars:1..{max_popularity} created:>{created_after}"
        params = {
            "q": q,
            "sort": "stars",
            "order": "desc",
            "per_page": min(limit * 2, 100),
        }

        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(
                "https://api.github.com/search/repositories",
                params=params,
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()

            items: list[Item] = []
            now = datetime.now(timezone.utc)

            for repo in data.get("items", []):
                stars = repo.get("stargazers_count", 0)
                created_at = datetime.fromisoformat(
                    repo["created_at"].replace("Z", "+00:00")
                )
                age_days = max((now - created_at).total_seconds() / 86400, 0.1)

                # Try to get recent star activity from stargazer timestamps
                recent_stars = await _get_recent_stars(
                    client, headers, repo["full_name"], days=7
                )

                # If we got stargazer data, use it; otherwise estimate from age
                if recent_stars is not None:
                    activity = float(recent_stars)
                else:
                    # Estimate: assume linear star accumulation
                    activity = float(stars) * min(7 / age_days, 1.0)

                item = Item(
                    title=repo.get("name", ""),
                    url=repo.get("html_url", ""),
                    author=repo.get("owner", {}).get("login", ""),
                    popularity=stars,
                    activity=activity,
                    age_days=age_days,
                    domain=self.name,
                    metadata={
                        "description": repo.get("description", ""),
                        "language": repo.get("language", ""),
                        "forks": repo.get("forks_count", 0),
                        "recent_stars_7d": recent_stars,
                    },
                )
                # Custom scoring: recent_stars / total_stars * log(total+1)
                if stars > 0 and activity > 0:
                    item.breakout_score = activity / (stars * age_days) * math.log(stars + 1)
                else:
                    item.breakout_score = compute_breakout_score(item)
                items.append(item)

        items.sort(key=lambda x: x.breakout_score, reverse=True)
        return items[:limit]


async def _get_recent_stars(
    client: httpx.AsyncClient, headers: dict, full_name: str, days: int
) -> int | None:
    """Fetch stargazer timestamps to count recent stars. Returns None on failure."""
    try:
        star_headers = {
            **headers,
            "Accept": "application/vnd.github.star+json",
        }
        resp = await client.get(
            f"https://api.github.com/repos/{full_name}/stargazers",
            headers=star_headers,
            params={"per_page": 100},
        )
        if resp.status_code != 200:
            return None

        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        count = 0
        for entry in resp.json():
            starred_at = entry.get("starred_at", "")
            if starred_at:
                ts = datetime.fromisoformat(starred_at.replace("Z", "+00:00"))
                if ts >= cutoff:
                    count += 1
        return count
    except Exception:
        return None
