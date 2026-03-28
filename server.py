#!/usr/bin/env python3
"""Tiny local server for Trending From Obscurity.

Serves the frontend and proxies API calls to the domain engines.
Usage: python server.py [--port 8888]
"""

from __future__ import annotations

import argparse
from pathlib import Path

from aiohttp import web

from domains import DOMAINS, get_domain
from engine import _item_to_dict

HERE = Path(__file__).parent


async def handle_index(request: web.Request) -> web.FileResponse:
    return web.FileResponse(HERE / "index.html")


async def handle_search(request: web.Request) -> web.Response:
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"error": "Invalid JSON"}, status=400)

    domain_name = data.get("domain", "")
    query = data.get("query", "").strip()
    if not query:
        return web.json_response({"error": "Query is required"}, status=400)
    if domain_name not in DOMAINS:
        return web.json_response(
            {"error": f"Unknown domain: {domain_name!r}. Available: {', '.join(DOMAINS)}"},
            status=400,
        )

    max_popularity = int(data.get("max_popularity", 1000))
    days = int(data.get("days", 14))
    limit = int(data.get("limit", 20))

    try:
        domain = get_domain(domain_name)
        items = await domain.search(query, max_popularity, days, limit)
        return web.json_response({
            "results": [_item_to_dict(it) for it in items],
            "query": query,
            "domain": domain_name,
            "count": len(items),
        })
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)


def main() -> None:
    parser = argparse.ArgumentParser(description="Trending From Obscurity — web server")
    parser.add_argument("--port", type=int, default=8888)
    args = parser.parse_args()

    app = web.Application()
    app.router.add_get("/", handle_index)
    app.router.add_post("/api/search", handle_search)

    print(f"\n  Trending From Obscurity → http://localhost:{args.port}\n")
    web.run_app(app, host="localhost", port=args.port, print=None)


if __name__ == "__main__":
    main()
