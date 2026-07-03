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


def test_load_state_returns_default_when_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(main, "STATE_FILE", tmp_path / "state.json")
    assert main.load_state() == {"in_stock": False, "consecutive_failures": 0}


def test_load_state_reads_existing_file(monkeypatch, tmp_path):
    state_file = tmp_path / "state.json"
    state_file.write_text(json.dumps({"in_stock": True, "consecutive_failures": 2}))
    monkeypatch.setattr(main, "STATE_FILE", state_file)

    assert main.load_state() == {"in_stock": True, "consecutive_failures": 2}


def test_save_state_writes_json(monkeypatch, tmp_path):
    state_file = tmp_path / "state.json"
    monkeypatch.setattr(main, "STATE_FILE", state_file)

    main.save_state({"in_stock": True, "consecutive_failures": 0})

    assert json.loads(state_file.read_text()) == {
        "in_stock": True,
        "consecutive_failures": 0,
    }
