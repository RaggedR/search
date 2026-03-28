#!/usr/bin/env python3
"""Trending From Obscurity — contrarian search engine.

Finds emerging creators, projects, and papers showing momentum from a low base.
The core insight: popularity is noise; the signal lives in the long tail.
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from domains import DOMAINS, get_domain
from engine import display_results


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Find breakout content from obscure creators.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
examples:
  %(prog)s --domain hn --query "AI" --days 1
  %(prog)s --domain github --query "python" --max-popularity 50 --days 30
  %(prog)s --domain youtube --query "jazz piano" --max-popularity 1000 --days 14
  %(prog)s --domain scholar --query "diffusion models" --max-popularity 20
  %(prog)s --domain medium --query "machine learning" --max-popularity 500 --days 7
""",
    )
    parser.add_argument(
        "--domain",
        "-d",
        required=True,
        choices=list(DOMAINS.keys()),
        help="Which domain to search",
    )
    parser.add_argument(
        "--query", "-q", required=True, help="Search query"
    )
    parser.add_argument(
        "--max-popularity",
        "-p",
        type=int,
        default=1000,
        help="Maximum popularity threshold (default: 1000)",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=14,
        help="Look back N days (default: 14)",
    )
    parser.add_argument(
        "--limit",
        "-n",
        type=int,
        default=20,
        help="Number of results to show (default: 20)",
    )
    parser.add_argument(
        "--format",
        "-f",
        choices=["table", "json"],
        default="table",
        help="Output format (default: table)",
    )
    args = parser.parse_args()

    domain = get_domain(args.domain)
    print(f"Searching {domain.name} for '{args.query}' (max popularity: {args.max_popularity:,}, last {args.days} days)...")

    items = asyncio.run(
        domain.search(args.query, args.max_popularity, args.days, args.limit)
    )
    display_results(items, args.format)


if __name__ == "__main__":
    main()
