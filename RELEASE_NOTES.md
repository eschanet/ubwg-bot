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
