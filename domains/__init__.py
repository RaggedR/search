"""Domain registry for the contrarian search engine."""

from domains.hackernews import HackerNewsDomain
from domains.github import GitHubDomain
from domains.youtube import YouTubeDomain
from domains.scholar import ScholarDomain
from domains.medium import MediumDomain

DOMAINS: dict[str, type] = {
    "hn": HackerNewsDomain,
    "github": GitHubDomain,
    "youtube": YouTubeDomain,
    "scholar": ScholarDomain,
    "medium": MediumDomain,
}


def get_domain(name: str):
    cls = DOMAINS.get(name)
    if cls is None:
        raise ValueError(f"Unknown domain: {name!r}. Available: {', '.join(DOMAINS)}")
    return cls()
