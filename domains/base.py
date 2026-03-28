"""Abstract base class and universal result type for all domains."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class Item:
    """Universal result item across all domains."""

    title: str
    url: str
    author: str
    popularity: int  # subscribers, stars, citations, followers, etc.
    activity: float  # views, recent stars, citation velocity, claps, etc.
    age_days: float  # days since creation/upload/publication
    breakout_score: float = 0.0  # computed
    domain: str = ""
    metadata: dict = field(default_factory=dict)


class Domain(ABC):
    """Abstract base for a searchable domain."""

    name: str = ""

    @abstractmethod
    async def search(
        self, query: str, max_popularity: int, days: int, limit: int
    ) -> list[Item]:
        """Search this domain and return scored Items, sorted by breakout_score descending."""
        ...
