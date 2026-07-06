# ubwg-bot

Polls the [UBWG membership product page](https://ubwg.ch/product/ubwg-member-1-jahr-aktuell/) every 2 minutes and sends a Telegram alert the moment it comes back in stock.

Stock status is read from the page's WooCommerce markup: the JSON-LD `availability` field (`schema.org/InStock` / `OutOfStock`), falling back to the product's `instock` / `outofstock` CSS class if the JSON-LD isn't found. An alert is only sent on the out-of-stock → in-stock transition, so it won't spam you on every check while the item stays available. A heartbeat message with the current status is also sent once per hour (configurable) so you can confirm the bot is alive.

If checks start failing (page down, network issue, etc.), the bot retries at the normal interval for the first few failures. Once it hits `FAILURE_ALERT_THRESHOLD` consecutive failures, it sends a one-time Telegram alert and starts backing off exponentially between checks (doubling each time, capped at `MAX_BACKOFF_SECONDS`) until a check succeeds again — so it doesn't hammer the site while it's having trouble.

## Setup

Requires [uv](https://docs.astral.sh/uv/).

```bash
uv sync
cp .env.example .env
```

Fill in `.env` with a Telegram bot token (from [@BotFather](https://t.me/BotFather)) and your chat ID:

```
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
```

### Configuration

All values below are optional and fall back to the defaults shown if unset:

| Env var | Default | Description |
| --- | --- | --- |
| `PRODUCT_URL` | `https://ubwg.ch/product/ubwg-member-1-jahr-aktuell/` | Product page to monitor |
| `CHECK_INTERVAL_SECONDS` | `120` | Seconds between checks |
| `FAILURE_ALERT_THRESHOLD` | `5` | Consecutive failed checks before sending a "monitoring may be broken" alert |
| `HEARTBEAT_INTERVAL_SECONDS` | `3600` (60 minutes) | Minimum time between heartbeat messages; set to `-1` to disable heartbeats entirely |
| `MAX_BACKOFF_SECONDS` | `3600` (60 minutes) | Cap on the exponential backoff delay once `FAILURE_ALERT_THRESHOLD` is reached |

## Running

```bash
uv run python main.py
```

Runs forever, checking every 2 minutes. Use `tmux`/`screen` (or the Docker setup below) to keep it running after you close the terminal.

Last known stock status is persisted to `state.json` next to `main.py`, so restarts don't lose track of whether an alert has already been sent.

## Running with Docker

```bash
docker compose up -d
```

Pulls the published image from `ghcr.io/eschanet/ubwg-bot`, persists `state.json` on the host, and restarts automatically (`restart: unless-stopped`). View logs with `docker compose logs -f`; stop with `docker compose down`.

`.env` is optional here — `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, and any of the config vars above can instead be exported in your shell before running `docker compose up`, which takes precedence over `.env` if both are set:

```bash
TELEGRAM_BOT_TOKEN=xxx TELEGRAM_CHAT_ID=yyy docker compose up -d
```

## Tests

```bash
uv run pytest -v
```

## CI/CD

- **[.github/workflows/test.yml](.github/workflows/test.yml)** runs the test suite on every push and pull request.
- **[.github/workflows/docker-publish.yml](.github/workflows/docker-publish.yml)** builds and pushes a Docker image to `ghcr.io/eschanet/ubwg-bot` whenever a tag matching `v*.*.*` is pushed:

  ```bash
  git tag v0.1.0
  git push origin v0.1.0
  ```
