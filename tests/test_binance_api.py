import services.binance_api as binance_api


def _mock_cache(monkeypatch, cache=None):
    monkeypatch.setattr(binance_api, "_load_cache", lambda: {} if cache is None else cache)
    monkeypatch.setattr(binance_api, "_save_cache", lambda _: None)


def _set_fake_credentials(monkeypatch):
    monkeypatch.setenv("BINANCE_API_KEY", "test-key")
    monkeypatch.setenv("BINANCE_API_SECRET", "test-secret")


def test_get_leverage_bracket_falls_back_when_request_returns_none(monkeypatch):
    _mock_cache(monkeypatch)
    _set_fake_credentials(monkeypatch)
    monkeypatch.setattr(binance_api, "validate_futures_symbol", lambda _: True)

    responses = iter([
        {"serverTime": 1234567890},
        None,
    ])
    monkeypatch.setattr(
        binance_api,
        "get",
        lambda url, params=None, headers=None: next(responses),
    )

    margin, warning = binance_api.get_leverage_bracket("BTC")

    assert margin == binance_api.DEFAULT_MAINT_MARGIN
    assert warning == "Could not fetch official bracket; using default maintenance margin."


def test_get_leverage_bracket_parses_wrapped_list_response(monkeypatch):
    _mock_cache(monkeypatch)
    _set_fake_credentials(monkeypatch)
    monkeypatch.setattr(binance_api, "validate_futures_symbol", lambda _: True)

    responses = iter([
        {"serverTime": 1234567890},
        [{"symbol": "BTCUSDT", "brackets": [{"maintMarginRatio": "0.004"}]}],
    ])
    monkeypatch.setattr(
        binance_api,
        "get",
        lambda url, params=None, headers=None: next(responses),
    )

    margin, warning = binance_api.get_leverage_bracket("BTC")

    assert margin == 0.004
    assert warning is None
