# maintenance-calendar

Household maintenance scheduling. Add an item you own (espresso machine,
lawn mower, etc.). Claude researches a recommended schedule with supply
links and how-to videos. You review the draft, save it, and subscribe to
the resulting iCal feed.

## Stack

- Python 3.10+, FastAPI, SQLAlchemy 2, Alembic
- Jinja2 + HTMX (no SPA build)
- Postgres (Neon or Supabase free tier); SQLite works for local dev
- Anthropic Claude with web search (item research)
- YouTube Data API v3 (resolve video search queries to real videos)
- Magic-link email auth; ICS feed gated by an unguessable per-household token

## First-time setup

```sh
make install
cp .env.example .env
# Fill in: DATABASE_URL, ANTHROPIC_API_KEY, YOUTUBE_API_KEY, SESSION_SECRET
make migrate
make dev
```

For a local-only run without setting up Postgres, point DATABASE_URL at SQLite:

```sh
DATABASE_URL=sqlite:///./maintenance.db make migrate
DATABASE_URL=sqlite:///./maintenance.db make dev
```

`make dev` serves at `http://localhost:8000`.

## End-to-end flow

1. Visit `/`. Click **Sign in**.
2. Enter your email. The magic link is printed to the server console
   (`EMAIL_BACKEND=console`); click it to set your session cookie.
3. Click **Add item**. Provide a name (optional: Amazon URL or ASIN).
   The server runs `ResearchService.research_item`, which calls Claude
   with the web-search tool and produces a draft of maintenance tasks
   with supply queries and YouTube video search queries; YouTube and an
   Amazon-search URL builder enrich the supplies and videos.
4. Review and edit the draft. Save. Tasks land in the DB.
5. Visit `/settings`. Copy the `webcal://...` subscription URL. Add it
   to Apple Calendar (Subscribe to Calendar...) or Google Calendar
   (Add other calendars → From URL). New items appear on the next sync.

## Subscribing from a phone

Apple Calendar polls the webcal URL over HTTPS. For that to work from
outside your laptop you need to expose the dev server. Options:

- **Tailscale**: `tailscale serve --bg https / http://localhost:8000`
  and use the magic DNS hostname.
- **Cloudflared**: `cloudflared tunnel --url http://localhost:8000`
  prints a public `*.trycloudflare.com` URL. Replace the host in the
  `webcal://` URL on the settings page.
- For real deployment: Fly.io / Railway / Render all run this stack
  cleanly. See `pyproject.toml` for deps.

## Layout

```
app/
  main.py          FastAPI app, mounts routers + /static
  settings.py      pydantic-settings, .env loader
  db.py            SQLAlchemy Base + session
  deps.py          get_current_user / get_optional_user
  contracts.py     shared Pydantic shapes (ItemResearch, etc.)
  models/          Household, User, Item, MaintenanceTask, MagicLinkToken
  routers/         auth, calendar (ICS feed), items, settings
  services/        auth, email_sender, research, youtube, supplies,
                   ics, calendar_query, items
  templates/       Jinja2 (HTMX for inline rows)
  static/styles.css
alembic/           migrations
tests/             pytest (64 tests covering services + routes + smoke)
```

## Quality gates

```sh
make check         # ruff + mypy --strict + pytest
```

## Status

v0.1. MVP works end-to-end against a real Postgres / SQLite. Notable
gaps for v1.x:

- Webcal URL hard-codes `MAGIC_LINK_BASE_URL` from settings; deploy
  needs that to be the public host.
- ICS VEVENTs omit `DTSTAMP` (RFC 5545 requires it; most clients are
  lenient). Tracked as a follow-up.
- Research is synchronous; an add-item POST can take 10-30s. A queue +
  HTMX polling is the obvious next step.
- Single household per deployment (no invites, no multi-tenancy).
