import importlib
import json

import pytest
import requests

import main


class FakeResponse:
    def __init__(self, text="", status_code=200, json_data=None):
        self.text = text
        self.status_code = status_code
        self._json_data = json_data or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")

    def json(self):
        return self._json_data


IN_STOCK_JSONLD_HTML = (
    '<html><body><script type="application/ld+json">'
    '{"availability":"https:\\/\\/schema.org\\/InStock"}'
    "</script></body></html>"
)

OUT_OF_STOCK_JSONLD_HTML = (
    '<html><body><script type="application/ld+json">'
    '{"availability":"https:\\/\\/schema.org\\/OutOfStock"}'
    "</script></body></html>"
)

IN_STOCK_CLASS_HTML = (
    '<div id="product-41779" class="product type-product instock '
    'product_cat-ubwg-member"></div>'
)

OUT_OF_STOCK_CLASS_HTML = (
    '<div id="product-41779" class="product type-product outofstock '
    'product_cat-ubwg-member"></div>'
)

NO_INDICATOR_HTML = "<html><body>nothing useful here</body></html>"


def test_check_stock_detects_in_stock_via_jsonld(monkeypatch):
    monkeypatch.setattr(
        requests, "get", lambda *a, **k: FakeResponse(IN_STOCK_JSONLD_HTML)
    )
    assert main.check_stock() is True


def test_check_stock_detects_out_of_stock_via_jsonld(monkeypatch):
    monkeypatch.setattr(
        requests, "get", lambda *a, **k: FakeResponse(OUT_OF_STOCK_JSONLD_HTML)
    )
    assert main.check_stock() is False


def test_check_stock_detects_in_stock_via_class_fallback(monkeypatch):
    monkeypatch.setattr(
        requests, "get", lambda *a, **k: FakeResponse(IN_STOCK_CLASS_HTML)
    )
    assert main.check_stock() is True


def test_check_stock_detects_out_of_stock_via_class_fallback(monkeypatch):
    monkeypatch.setattr(
        requests, "get", lambda *a, **k: FakeResponse(OUT_OF_STOCK_CLASS_HTML)
    )
    assert main.check_stock() is False


def test_check_stock_raises_when_no_indicator_found(monkeypatch):
    monkeypatch.setattr(
        requests, "get", lambda *a, **k: FakeResponse(NO_INDICATOR_HTML)
    )
    with pytest.raises(ValueError):
        main.check_stock()


def test_check_stock_raises_on_http_error(monkeypatch):
    monkeypatch.setattr(
        requests, "get", lambda *a, **k: FakeResponse(status_code=500)
    )
    with pytest.raises(requests.HTTPError):
        main.check_stock()


def test_send_telegram_message_posts_correct_payload(monkeypatch):
    captured = {}

    def fake_post(url, data, timeout):
        captured["url"] = url
        captured["data"] = data
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr(requests, "post", fake_post)

    main.send_telegram_message("hello world")

    assert captured["url"] == (
        f"https://api.telegram.org/bot{main.TELEGRAM_BOT_TOKEN}/sendMessage"
    )
    assert captured["data"] == {
        "chat_id": main.TELEGRAM_CHAT_ID,
        "text": "hello world",
    }


def test_send_telegram_message_raises_on_failure(monkeypatch):
    monkeypatch.setattr(
        requests, "post", lambda *a, **k: FakeResponse(status_code=400)
    )
    with pytest.raises(requests.HTTPError):
        main.send_telegram_message("hello world")


def test_heartbeat_message_in_stock():
    assert main.heartbeat_message(True) == (
        "UBWG monitor heartbeat: product is currently in stock."
    )


def test_heartbeat_message_out_of_stock():
    assert main.heartbeat_message(False) == (
        "UBWG monitor heartbeat: product is currently out of stock."
    )


def test_config_defaults():
    assert main.PRODUCT_URL == "https://ubwg.ch/product/ubwg-member-1-jahr-aktuell/"
    assert main.CHECK_INTERVAL_SECONDS == 120
    assert main.FAILURE_ALERT_THRESHOLD == 5
    assert main.HEARTBEAT_INTERVAL_SECONDS == 60 * 60
    assert main.MAX_BACKOFF_SECONDS == 60 * 60


def test_config_overridable_via_env_vars(monkeypatch):
    monkeypatch.setenv("PRODUCT_URL", "https://example.com/product")
    monkeypatch.setenv("CHECK_INTERVAL_SECONDS", "30")
    monkeypatch.setenv("FAILURE_ALERT_THRESHOLD", "2")
    monkeypatch.setenv("HEARTBEAT_INTERVAL_SECONDS", "300")
    monkeypatch.setenv("MAX_BACKOFF_SECONDS", "900")

    try:
        importlib.reload(main)
        assert main.PRODUCT_URL == "https://example.com/product"
        assert main.CHECK_INTERVAL_SECONDS == 30
        assert main.FAILURE_ALERT_THRESHOLD == 2
        assert main.HEARTBEAT_INTERVAL_SECONDS == 300
        assert main.MAX_BACKOFF_SECONDS == 900
    finally:
        monkeypatch.undo()
        importlib.reload(main)


def test_compute_sleep_seconds_below_threshold_uses_normal_interval():
    for failures in range(main.FAILURE_ALERT_THRESHOLD):
        assert main.compute_sleep_seconds(failures) == main.CHECK_INTERVAL_SECONDS


def test_compute_sleep_seconds_doubles_once_threshold_reached():
    at_threshold = main.compute_sleep_seconds(main.FAILURE_ALERT_THRESHOLD)
    one_more = main.compute_sleep_seconds(main.FAILURE_ALERT_THRESHOLD + 1)
    two_more = main.compute_sleep_seconds(main.FAILURE_ALERT_THRESHOLD + 2)

    assert at_threshold == main.CHECK_INTERVAL_SECONDS
    assert one_more == main.CHECK_INTERVAL_SECONDS * 2
    assert two_more == main.CHECK_INTERVAL_SECONDS * 4


def test_compute_sleep_seconds_caps_at_max_backoff():
    assert main.compute_sleep_seconds(main.FAILURE_ALERT_THRESHOLD + 100) == (
        main.MAX_BACKOFF_SECONDS
    )


def test_is_heartbeat_due_when_never_sent():
    assert main.is_heartbeat_due(last_heartbeat_at=0, now=main.HEARTBEAT_INTERVAL_SECONDS) is True


def test_is_heartbeat_due_before_interval_elapsed():
    assert main.is_heartbeat_due(last_heartbeat_at=1000, now=1000 + 60) is False


def test_is_heartbeat_due_disabled_via_negative_one(monkeypatch):
    monkeypatch.setenv("HEARTBEAT_INTERVAL_SECONDS", "-1")
    try:
        importlib.reload(main)
        assert main.is_heartbeat_due(last_heartbeat_at=0, now=10**9) is False
    finally:
        monkeypatch.undo()
        importlib.reload(main)


def test_is_heartbeat_due_after_interval_elapsed():
    assert (
        main.is_heartbeat_due(last_heartbeat_at=1000, now=1000 + main.HEARTBEAT_INTERVAL_SECONDS)
        is True
    )


def test_load_state_returns_default_when_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(main, "STATE_FILE", tmp_path / "state.json")
    assert main.load_state() == {
        "in_stock": False,
        "consecutive_failures": 0,
        "last_heartbeat_at": 0,
    }


def test_load_state_reads_existing_file(monkeypatch, tmp_path):
    state_file = tmp_path / "state.json"
    state_file.write_text(
        json.dumps(
            {"in_stock": True, "consecutive_failures": 2, "last_heartbeat_at": 123}
        )
    )
    monkeypatch.setattr(main, "STATE_FILE", state_file)

    assert main.load_state() == {
        "in_stock": True,
        "consecutive_failures": 2,
        "last_heartbeat_at": 123,
    }


def test_load_state_backfills_missing_last_heartbeat_at(monkeypatch, tmp_path):
    state_file = tmp_path / "state.json"
    state_file.write_text(json.dumps({"in_stock": True, "consecutive_failures": 2}))
    monkeypatch.setattr(main, "STATE_FILE", state_file)

    assert main.load_state() == {
        "in_stock": True,
        "consecutive_failures": 2,
        "last_heartbeat_at": 0,
    }


def test_save_state_writes_json(monkeypatch, tmp_path):
    state_file = tmp_path / "state.json"
    monkeypatch.setattr(main, "STATE_FILE", state_file)

    main.save_state({"in_stock": True, "consecutive_failures": 0})

    assert json.loads(state_file.read_text()) == {
        "in_stock": True,
        "consecutive_failures": 0,
    }
