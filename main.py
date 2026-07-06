import json
import logging
import os
import re
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

PRODUCT_URL = os.environ.get(
    "PRODUCT_URL", "https://ubwg.ch/product/ubwg-member-1-jahr-aktuell/"
)
CHECK_INTERVAL_SECONDS = int(os.environ.get("CHECK_INTERVAL_SECONDS", "120"))
STATE_FILE = Path(__file__).parent / "state.json"
FAILURE_ALERT_THRESHOLD = int(os.environ.get("FAILURE_ALERT_THRESHOLD", "5"))
HEARTBEAT_INTERVAL_SECONDS = int(
    os.environ.get("HEARTBEAT_INTERVAL_SECONDS", str(60 * 60))
)
MAX_BACKOFF_SECONDS = int(os.environ.get("MAX_BACKOFF_SECONDS", str(60 * 60)))

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    )
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("ubwg-bot")


def send_telegram_message(text: str) -> None:
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    resp = requests.post(
        url, data={"chat_id": TELEGRAM_CHAT_ID, "text": text}, timeout=15
    )
    resp.raise_for_status()


def load_state() -> dict:
    defaults = {"in_stock": False, "consecutive_failures": 0, "last_heartbeat_at": 0}
    if STATE_FILE.exists():
        return {**defaults, **json.loads(STATE_FILE.read_text())}
    return defaults


def save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state))


def heartbeat_message(in_stock: bool) -> str:
    status = "in stock" if in_stock else "out of stock"
    return f"UBWG monitor heartbeat: product is currently {status}."


def is_heartbeat_due(last_heartbeat_at: float, now: float) -> bool:
    if HEARTBEAT_INTERVAL_SECONDS == -1:
        return False
    return now - last_heartbeat_at >= HEARTBEAT_INTERVAL_SECONDS


def compute_sleep_seconds(consecutive_failures: int) -> int:
    """Normal interval below the failure-alert threshold; exponential backoff
    (capped at MAX_BACKOFF_SECONDS) once it's reached."""
    if consecutive_failures < FAILURE_ALERT_THRESHOLD:
        return CHECK_INTERVAL_SECONDS
    backoff_exponent = consecutive_failures - FAILURE_ALERT_THRESHOLD
    return min(CHECK_INTERVAL_SECONDS * (2**backoff_exponent), MAX_BACKOFF_SECONDS)


def check_stock() -> bool:
    """Returns True if the product is in stock, False if out of stock.
    Raises on network/parse failure."""
    resp = requests.get(PRODUCT_URL, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    html = resp.text

    if '"availability":"https:\\/\\/schema.org\\/InStock"' in html:
        return True
    if '"availability":"https:\\/\\/schema.org\\/OutOfStock"' in html:
        return False

    match = re.search(r'id="product-\d+"[^>]*class="([^"]+)"', html)
    if match:
        classes = match.group(1).split()
        if "instock" in classes:
            return True
        if "outofstock" in classes:
            return False

    raise ValueError("Could not find a stock status indicator on the page")


def main() -> None:
    state = load_state()
    log.info("Starting UBWG stock monitor (checking every %ss)", CHECK_INTERVAL_SECONDS)

    while True:
        try:
            in_stock = check_stock()
            state["consecutive_failures"] = 0

            now = time.time()
            if is_heartbeat_due(state["last_heartbeat_at"], now):
                try:
                    send_telegram_message(heartbeat_message(in_stock))
                    state["last_heartbeat_at"] = now
                except Exception as heartbeat_exc:
                    log.error("Failed to send heartbeat: %s", heartbeat_exc)

            if in_stock and not state["in_stock"]:
                log.info("Product is now IN STOCK - sending alert")
                send_telegram_message(
                    f"UBWG membership is back in stock!\n{PRODUCT_URL}"
                )
            elif not in_stock:
                log.info("Still out of stock")
            else:
                log.info("Still in stock (already alerted)")

            state["in_stock"] = in_stock

        except Exception as exc:
            state["consecutive_failures"] += 1
            log.error("Check failed (%s): %s", state["consecutive_failures"], exc)

            if state["consecutive_failures"] == FAILURE_ALERT_THRESHOLD:
                try:
                    send_telegram_message(
                        "UBWG stock monitor: failed to load the product page "
                        f"{FAILURE_ALERT_THRESHOLD} times in a row. It may be "
                        "down or blocking requests. Backing off exponentially "
                        f"(up to {MAX_BACKOFF_SECONDS}s between checks) until "
                        "it recovers."
                    )
                except Exception as alert_exc:
                    log.error("Also failed to send failure alert: %s", alert_exc)

        sleep_seconds = compute_sleep_seconds(state["consecutive_failures"])
        if sleep_seconds > CHECK_INTERVAL_SECONDS:
            log.info("Backing off for %ss before next check", sleep_seconds)

        save_state(state)
        time.sleep(sleep_seconds)


if __name__ == "__main__":
    main()
