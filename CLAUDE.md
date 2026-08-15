# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

Telegram bot for JAV (Japanese Adult Video) actress queries. Send actress name or AV ID; bot returns profile (bio, stats, social links), latest/top works, magnet links, and rankings.

## Commands

```bash
# Run locally (requires .env with TELEGRAM_BOT_TOKEN)
python -m app.main

# Docker
docker compose up -d --build
docker compose logs -f
docker compose down

# Single test (fast feedback)
pytest tests/unit/test_cache.py -v --no-header
pytest tests/unit/test_callback.py -v --no-header

# Test suites
pytest tests/unit/                 # Unit tests (fast, no external deps)
pytest tests/service/              # Service-layer tests
pytest tests/scraping/             # Scraping tests (slow, external sites)
pytest tests/integration/          # Integration tests (need full env)

# Standalone experimental scripts (no pytest)
python tests/scripts/test_avatar.py
python tests/scripts/test_javdb_curl.py

# Lint & format
ruff check app/
ruff format app/
mypy app/

# Install deps
pip install -r requirements.txt
```

## Architecture

```
app/
├── main.py              # Entry: builds telegram.ext.Application, registers handlers, starts polling
├── config.py            # BotConfig dataclass — all settings from env vars
├── service.py           # ActressService facade — coordinates sub-services for profile queries
├── health.py            # Health check: data source status, error-log ring buffer, report generation
│
├── models/              # Pydantic v2 models (profile/works/actors/magnets/wiki/favorites)
├── formatters/          # HTML message builders (profile/magnets/favorites/rankings)
├── fav/                 # Favorites data layer (manager.py: MySQL CRUD + per-user push dedup)
│
├── services/            # Sub-services called by ActressService (one per data source)
│   ├── wiki_service.py      # Wikipedia/Wikidata info extraction (bio, social links)
│   ├── javbus_service.py    # AV metadata & magnets via jvav library
│   ├── javdb_scraper.py     # JavDb scraper (curl_cffi + subprocess curl fallback)
│   ├── rank_service.py      # JavDb rankings + background refresh
│   ├── resolver.py          # ProfileResolver: name resolution (candidates → star)
│   ├── name_match_service.py# Fuzzy name matching, CJK conversion (OpenCC, pypinyin)
│   ├── i18n/                # Multi-language i18n (zh_CN/en_US/ja_JP)
│   └── text_utils.py        # Unicode normalization, CJK detection
│
├── handlers/            # Telegram update handlers
│   ├── __init__.py          # Shared state: _set_shared(config, service) / _get_shared()
│   ├── common.py            # @require_auth decorator, start/help/menu, send_photo_with_fallback
│   ├── search.py            # /s — actress lookup, free-text handler
│   ├── magnet.py            # /search /magnet /m — magnet link search
│   ├── favorites.py         # /fav /unfav /myfav /favlatest — favorites CRUD + inline keyboard
│   ├── push.py              # /push — new-work push notification toggle
│   ├── rank.py              # /rank — hot actress rankings with pagination
│   ├── history.py           # /history — recent search history
│   ├── works.py             # Interactive works browser (inline gallery)
│   ├── settings.py          # /language — language preference
│   ├── stats.py             # /stats — usage statistics
│   └── admin.py             # /admin — health check (admin only)
│
├── cache.py             # TTLCache: thread-safe OrderedDict with per-key TTL + JSON persistence
├── magnet_search.py     # sukebei.nyaa.si magnet search (httpx + BeautifulSoup)
├── secure_callback.py   # HMAC-SHA256 signed callback tokens (incl. plaintext navigation callbacks)
├── rate_limiter.py      # Token-bucket rate limiter (thread-safe, sync+async)
├── scheduler.py         # Daily DB cleanup job (90-day purge + optimize)
├── improved_utils.py    # Image download with retry + Referer headers (JavBus) + curl subprocess (JavDb)
└── models.py            # (split into the models/ package)
```

### Key distinctions

- **Favorites data vs handler**: `app/fav/manager.py` = FavoritesManager (MySQL data layer). `handlers/favorites.py` = Telegram command handlers for favorites UI.
- **Two service access layers**: `app/service.py` (ActressService, facade) coordinates profiles. `app/services/` (individual modules) are called independently for magnets/rankings.

## Key patterns

- **Facade**: `ActressService` delegates to sub-services in `services/`. Profile queries fan out via `asyncio.gather` (Wiki + JavBus + JavDb) with `return_exceptions=True` — failures in one source don't block others.
- **Shared state**: `handlers/__init__.py` holds global `_SharedState(config, service)`. Set once in `build_app()`, accessed by handlers via `_get_shared()`. `TYPE_CHECKING`-guarded import to avoid circular imports.
- **Async dispatch**: Handlers are async (python-telegram-bot v20+). Sync libraries (requests, BeautifulSoup) wrapped in `asyncio.to_thread`. Exception: JavDbScraper falls back to `subprocess curl` inside `asyncio.to_thread`.
- **Multi-layer cache**: `TTLCache` with thread-safe OrderedDict, per-key TTL, max-size eviction, JSON persistence (debounced 5s). Five instances in `ActressService` with TTLs ranging 900s–43200s.
- **Secure callbacks**: `secure_callback.py` — HMAC-SHA256 signed tokens for inline keyboard buttons. Format: `prefix:8hexkey:16hexsig:timestamp`. One-time use (consumed on resolve), 7d TTL, JSON persistence with dirty-flag delayed save. Convenience: `short_callback(prefix, data)` / `resolve_callback(prefix, token)`. Plaintext callbacks are allowed **only** for UI navigation (`menu:`, `lang:`, `hist:page:`, `rank:`, `rank_retry:`, `myfav:*`); anything carrying data must be HMAC-signed.
- **Rate limiter**: `RateLimiter(calls_per_second)` with thread lock + sleep-wait. JavBus: 0.5/s, Wiki API: 1.0/s.
- **I18n**: Dict-based, 3 languages (zh_CN/en_US/ja_JP). Fallback chain: requested lang → default lang → raw key. `t()` applies `str.format()` from 3rd positional arg onwards.
- **Scheduler**: `scheduled_cleanup()` via `Application.job_queue` daily. Purges `favorite_queries` >90 days, optimizes MySQL tables. Rank background refresh starts in `post_init` lifecycle hook.
- **Works browser**: `handlers/works.py` — inline gallery paginated via secure callbacks. Works merged from JavBus (latest) + JavDb (top), deduped by AV ID, sorted by date desc.
- **Favorites on-by-default for push**: `push_enabled_global` defaults to `1`.
- **Push dedup & modes**: `user_seen_works` dedups work pushes by `(user_id, av_id)`; `actress_works` stays as the work-info store / backfill source. `user_push_settings.push_mode` is planned as `instant`/`digest`/`off` (docs-first — not yet implemented).

## External data sources

| Source | Used for | Access method | Key constraint |
|--------|----------|---------------|----------------|
| JavBus | Actress search, AV metadata, magnets | `jvav` library | Rate-limited 0.5/s |
| JavDb | Works, rankings, avatar | `curl_cffi` (primary) + curl subprocess (fallback) | Requires macOS SecureTransport TLS |
| Wikipedia/Wikidata | Bio, social links | `wikipediaapi` lib + direct API | Rate-limited 1/s |
| sukebei.nyaa.si | Magnet links | httpx + BeautifulSoup | 20s timeout |

### JavDb Cloudflare bypass

macOS curl uses SecureTransport TLS. Python urllib3 uses OpenSSL. Cloudflare's JA3 fingerprint blocks OpenSSL/BoringSSL but passes macOS SecureTransport. Hence JavDbScraper uses `curl_cffi` (browser TLS impersonation) as primary, falling back to `subprocess curl` + browser User-Agent dispatched via `asyncio.to_thread`.

## Configuration

All settings via environment variables (see `.env.example`).
- `TELEGRAM_BOT_TOKEN` (required) — `BotConfig.from_env()` raises `RuntimeError` if missing
- `ALLOWED_USER_IDS` — comma-separated Telegram user ID whitelist; empty = open
- `ADMIN_USER_ID` — receives startup notification message
- `HTTP_PROXY` — proxy for outbound HTTP (e.g. `http://host.docker.internal:7890`)
- `UNCENSORED` — set `1` to include uncensored AV content
- `PUSH_ENABLED` — periodic push of new works to users who opted in
- `PUSH_CHECK_INTERVAL` — seconds between push checks (default 3600)
- `FAVORITES_DB_PATH` / `CALLBACK_DB_PATH` — persistence paths
- `LOG_LEVEL` — DEBUG/INFO/WARNING/ERROR
- Various `*_LIMIT` / `*_TTL` env vars for pagination and cache control

## Tooling

Configured in `pyproject.toml`:

| Tool | Config |
|------|--------|
| **mypy** | Strict: `disallow_untyped_defs`, `warn_return_any`, `strict_equality`, `no_implicit_optional`. Python 3.11 target. |
| **ruff** | Line length 100, target 3.11, rules E/F/I/W/UP/B/SIM/ARG/RUF |

## Tests

```
tests/
├── unit/                  # Pure unit tests (no external deps)
│   ├── test_cache.py      # TTLCache
│   ├── test_callback.py   # SecureCallback
│   ├── test_formatters.py # HTML formatting
│   ├── test_name_match.py # Name matching
│   ├── test_favorites.py  # Favorites data layer
│   ├── test_i18n.py       # i18n service
│   ├── test_resolver.py   # ProfileResolver
│   ├── test_service.py    # ActressService
│   ├── test_magnet_search.py
│   ├── test_javdb_scraper.py
│   ├── test_rank_service.py
│   ├── test_handlers_*.py # Handler unit tests
│   └── test_works_browser.py
├── service/               # Service-layer tests
├── scraping/              # External-site scraping tests
├── integration/           # Full-environment integration tests
└── scripts/               # One-off/experimental scripts
```

## Constraints

- **Python 3.11 required** — `jvav` native extension fails to compile on 3.13+
- **Callback tokens are single-use** — `resolve_callback()` pops from store; calling twice on same token returns None
- **Rank background refresh** starts in `post_init`, not lazily
- **No full async HTTP stack** — Wikipedia/JavBus/sukebei use sync libraries, dispatched via `to_thread`
- Playwright requires Chromium and system deps (see Dockerfile for full list)
- JavDb uses Cloudflare protection — curl subprocess (macOS SecureTransport) bypasses JA3 fingerprint blocking
- External sites (JavBus, JavDb, sukebei) may timeout or change page structure
- Docker runs as non-root `javbot` user; `data/` dir needs proper permissions in volume mounts
- `data/` directory files (`callbacks.json`, `cache/*.json`, `*.db`) are gitignored runtime state
