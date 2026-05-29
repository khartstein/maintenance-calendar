# maintenance-calendar

Household maintenance scheduling. Add items you own (espresso machine, lawn mower, etc.),
get an LLM-suggested maintenance schedule with supply links and how-to videos, then
subscribe to the result as an iCal feed.

## Stack

- Python 3.10+, FastAPI, SQLAlchemy 2, Alembic
- Jinja2 templates + HTMX (no SPA build)
- Postgres (Neon or Supabase free tier)
- Anthropic Claude (item research), YouTube Data API (video lookup)
- Magic-link email auth (dev backend logs links to console)

## Quickstart

```sh
make install
cp .env.example .env        # fill in DATABASE_URL, ANTHROPIC_API_KEY, YOUTUBE_API_KEY
make migrate
make dev                    # http://localhost:8000
```

## Layout

```
app/
  main.py        FastAPI app
  settings.py    pydantic-settings, .env loader
  db.py          SQLAlchemy Base + session
  contracts.py   shared Pydantic shapes (LLM research output, etc.)
  models/        SQLAlchemy models
  routers/       FastAPI route modules
  services/      business logic
  templates/     Jinja2
  static/        css, etc.
alembic/         migrations
tests/           pytest
```

## Status

v0.1 scaffold. See task list in the conversation that produced this repo.
