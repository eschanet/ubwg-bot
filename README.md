# ubwg-bot

Polls the [UBWG membership product page](https://ubwg.ch/product/ubwg-member-1-jahr-aktuell/) every 2 minutes and sends a Telegram alert the moment it comes back in stock.

Stock status is read from the page's WooCommerce markup: the JSON-LD `availability` field (`schema.org/InStock` / `OutOfStock`), falling back to the product's `instock` / `outofstock` CSS class if the JSON-LD isn't found. An alert is only sent on the out-of-stock → in-stock transition, so it won't spam you on every check while the item stays available. If the page fails to load 5 checks in a row, you get a one-time alert that monitoring may be broken.

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

## Running

```bash
uv run python main.py
```

Runs forever, checking every 2 minutes. Use `tmux`/`screen` (or the Docker setup below) to keep it running after you close the terminal.

Last known stock status is persisted to `state.json` next to `main.py`, so restarts don't lose track of whether an alert has already been sent.

## Running with Docker

```bash
docker compose up -d --build
```

Reads secrets from `.env`, persists `state.json` on the host, and restarts automatically (`restart: unless-stopped`). View logs with `docker compose logs -f`; stop with `docker compose down`.

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
