# Trending From Obscurity

Contrarian search engine that finds emerging creators, projects, and papers showing momentum from a low base. Popularity is noise — the signal lives in the long tail.

## How it works

```
breakout_score = activity / (popularity × age)
```

A video with 40K views from a 500-subscriber channel scores higher than one with 400K views from a 5M-subscriber channel. Applied across five domains:

| Domain | Activity | Popularity | Auth |
|--------|----------|------------|------|
| YouTube | views | subscribers | API key |
| GitHub | recent stars | total stars | `gh` CLI |
| Hacker News | points | 1 (no followers) | none |
| Semantic Scholar | citation velocity | citations | none |
| Medium | tag breadth | 1 (RSS) | none |

## Usage

```bash
pip install -r requirements.txt

# Web UI
python server.py              # → http://localhost:8888

# CLI
python cli.py -d youtube -q "jazz piano" -p 1000 --days 14
python cli.py -d hn -q "AI" --days 1
python cli.py -d github -q "python" -p 50 --days 30
```

YouTube requires a [Data API v3 key](https://console.cloud.google.com/apis/credentials) in `.env`:
```
YOUTUBE_API_KEY=your_key_here
```
