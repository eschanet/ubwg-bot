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
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {"in_stock": False, "consecutive_failures": 0}


def save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state))


def heartbeat_message(in_stock: bool) -> str:
    status = "in stock" if in_stock else "out of stock"
    return f"UBWG monitor heartbeat: product is currently {status}."


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

            try:
                send_telegram_message(heartbeat_message(in_stock))
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
                        "down or blocking requests - please check."
                    )
                except Exception as alert_exc:
                    log.error("Also failed to send failure alert: %s", alert_exc)

        save_state(state)
        time.sleep(CHECK_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
