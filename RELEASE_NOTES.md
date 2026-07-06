## v0.1.0

### Added

- Exponential backoff on repeated check failures: once `FAILURE_ALERT_THRESHOLD` consecutive failures is reached, the delay between checks doubles each time (capped at `MAX_BACKOFF_SECONDS`, default 3600s) instead of retrying at the normal interval, so the bot backs off from a struggling or blocking site rather than hammering it.
- The existing "monitoring may be broken" Telegram alert now fires exactly once, at the moment backoff begins, with text explaining that backoff is starting.
- New `MAX_BACKOFF_SECONDS` env var; documented in `.env.example`, `docker-compose.yml`, and `README.md`.

## v0.0.3

### Added

- `PRODUCT_URL`, `CHECK_INTERVAL_SECONDS`, and `FAILURE_ALERT_THRESHOLD` are now configurable via environment variables, defaulting to their previous hardcoded values.
- The heartbeat is now throttled to once per `HEARTBEAT_INTERVAL_SECONDS` (default `3600`, i.e. 60 minutes) instead of firing on every check, cutting Telegram noise significantly. Last-sent time is tracked in `state.json` (`last_heartbeat_at`), which is backfilled automatically for state files created by older versions.
- `docker-compose.yml` and `.env.example` updated with the new config vars; `docker-compose.yml` now pulls `ghcr.io/eschanet/ubwg-bot:0.0.3`.

## v0.0.2

### Added

- Telegram heartbeat message sent on every successful stock check (in addition to the back-in-stock alert and the 5-failure escalation alert), so you can confirm the bot is alive and see the current status in near-real time.
- `docker-compose.yml` no longer requires a `.env` file — it's now optional (`required: false`), and `TELEGRAM_BOT_TOKEN`/`TELEGRAM_CHAT_ID` can instead be provided as shell environment variables when running `docker compose up`, which take precedence over `.env` if both are set.
- `docker-compose.yml` now pulls the published `ghcr.io/eschanet/ubwg-bot:0.0.2` image instead of building locally.

## v0.0.1 — Initial release

First working version of the UBWG stock monitor bot.

### Features

- Polls the [UBWG membership product page](https://ubwg.ch/product/ubwg-member-1-jahr-aktuell/) every 2 minutes for stock status.
- Detects availability from the page's JSON-LD `availability` field, with a fallback to the WooCommerce `instock`/`outofstock` CSS class.
- Sends a Telegram alert on the out-of-stock → in-stock transition only, so it won't spam repeated alerts while the item stays available.
- Sends a one-time alert if the page fails to load 5 checks in a row, so silent monitoring failures don't go unnoticed.
- Persists last-known stock status to `state.json` so restarts don't lose track of whether an alert has already been sent.

### Packaging & Ops

- Project managed with `uv`; dependencies locked via `uv.lock`.
- `Dockerfile` and `docker-compose.yml` for running the bot as a long-lived container with `restart: unless-stopped`.
- GitHub Actions:
  - `test.yml` runs the unit test suite on every push and pull request.
  - `docker-publish.yml` builds and pushes a Docker image to `ghcr.io/eschanet/ubwg-bot` on version tags (`v*.*.*`).
- Unit tests covering stock detection (JSON-LD and class-based paths), Telegram message sending, and state persistence.
