"""Scoring logic and display formatting for the contrarian search engine."""

from __future__ import annotations

import json
import math

from domains.base import Item


def compute_breakout_score(item: Item) -> float:
    """Universal breakout formula: activity / (popularity x age).

    Guards against division by zero with sensible floors.
    """
    popularity = max(item.popularity, 1)
    age = max(item.age_days, 0.1)  # floor at ~2.4 hours
    return item.activity / (popularity * age)


def display_results(items: list[Item], output_format: str = "table") -> None:
    if not items:
        print("No results found.")
        return

    if output_format == "json":
        print(json.dumps([_item_to_dict(it) for it in items], indent=2))
        return

    # Table output
    print()
    print(f"  {'#':<4} {'Score':>8}  {'Pop':>7}  {'Activity':>10}  {'Age':>6}  {'Author':<20} {'Title'}")
    print(f"  {'─'*4} {'─'*8}  {'─'*7}  {'─'*10}  {'─'*6}  {'─'*20} {'─'*40}")

    for i, item in enumerate(items, 1):
        title = _truncate(item.title, 60)
        author = _truncate(item.author, 20)
        age_str = _format_age(item.age_days)
        print(
            f"  {i:<4} {item.breakout_score:>8.1f}  {item.popularity:>7,}  {item.activity:>10,.0f}  {age_str:>6}  {author:<20} {title}"
        )

    print()
    # Print URLs separately for easy clicking
    for i, item in enumerate(items, 1):
        print(f"  {i}. {item.url}")
    print()


def _item_to_dict(item: Item) -> dict:
    return {
        "title": item.title,
        "url": item.url,
        "author": item.author,
        "popularity": item.popularity,
        "activity": item.activity,
        "age_days": round(item.age_days, 2),
        "breakout_score": round(item.breakout_score, 2),
        "domain": item.domain,
        "metadata": item.metadata,
    }


def _truncate(s: str, n: int) -> str:
    return s if len(s) <= n else s[: n - 1] + "…"


def _format_age(days: float) -> str:
    if days < 1:
        return f"{days * 24:.0f}h"
    if days < 30:
        return f"{days:.0f}d"
    return f"{days / 30:.0f}mo"
