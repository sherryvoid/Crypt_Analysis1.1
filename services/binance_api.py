# services/binance_api.py

import time
import logging
import pandas as pd
import hmac
import hashlib
from urllib.parse import urlencode
import os
import json
from typing import Tuple, Optional

from .http_client import get
from .config import API_URLS, TIMEFRAMES, LIMITS

log = logging.getLogger(__name__)

# Cache file for persistent fallback data
CACHE_PATH = os.path.join(os.path.dirname(__file__), "cache.json")
CACHE_TTL = 24 * 3600  # 24 hours
DEFAULT_MAINT_MARGIN = 0.01


def _load_cache() -> dict:
    try:
        with open(CACHE_PATH, "r") as f:
            data = json.load(f)
        return data
    except Exception:
        return {}


def _save_cache(cache: dict):
    try:
        os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
        with open(CACHE_PATH, "w") as f:
            json.dump(cache, f)
    except Exception as e:
        log.error(f"Failed to save cache: {e}")


def _cache_margin(cache: dict, key: str, margin: float, ts: float) -> None:
    cache[key] = {"margin": margin, "ts": ts}
    _save_cache(cache)


def _extract_maint_margin_ratio(data) -> Optional[float]:
    """Extract the first maintenance margin ratio from Binance's mixed response shapes."""
    if isinstance(data, dict):
        if "maintMarginRatio" in data:
            try:
                return float(data["maintMarginRatio"])
            except (TypeError, ValueError):
                return None
        brackets = data.get("brackets")
        if isinstance(brackets, list) and brackets:
            return _extract_maint_margin_ratio(brackets[0])
        return None

    if isinstance(data, list) and data:
        return _extract_maint_margin_ratio(data[0])

    return None


def validate_crypto_symbol(symbol: str) -> bool:
    """Quick check for valid spot symbol."""
    url = API_URLS["binance"]["spot"]["klines"]
    params = {"symbol": f"{symbol}USDT",
              "interval": TIMEFRAMES["scalping"], "limit": 1}
    resp = get(url, params)
    valid = isinstance(resp, list) and len(resp) > 0
    log.debug(f"Spot symbol {symbol} valid: {valid}")
    return valid


def validate_futures_symbol(symbol: str) -> bool:
    """Quick check for valid futures symbol."""
    url = API_URLS["binance"]["futures"]["klines"]
    params = {"symbol": f"{symbol}USDT",
              "interval": TIMEFRAMES["futures"], "limit": 1}
    resp = get(url, params)
    valid = isinstance(resp, list) and len(resp) > 0
    log.debug(f"Futures symbol {symbol} valid: {valid}")
    return valid


def get_ohlcv(
    symbol: str, ttype: str, is_futures: bool = False
) -> pd.DataFrame | None:
    """
    Fetch OHLCV data. Returns DataFrame or None.
    """
    # enforce ttype/is_futures consistency
    if is_futures and ttype != "futures":
        log.warning("Inconsistent params: forcing ttype to 'futures'")
        ttype = "futures"
    if not is_futures and ttype == "futures":
        log.warning("Inconsistent params: setting is_futures=True")
        is_futures = True

    interval = TIMEFRAMES.get(ttype)
    limit = LIMITS.get(ttype)
    base = API_URLS["binance"]["futures" if is_futures else "spot"]["klines"]
    params = {"symbol": f"{symbol}USDT", "interval": interval, "limit": limit}
    data = get(base, params)
    if not isinstance(data, list) or not data:
        log.error(f"Failed fetching OHLCV for {symbol}")
        return None
    try:
        cols = ["timestamp", "open", "high", "low",
                "close", "volume"] + list(range(6, 12))
        df = pd.DataFrame(data, columns=cols)
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        df.set_index("timestamp", inplace=True)
        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = df[col].astype(float)
        log.info(f"Fetched {len(df)} candles for {symbol} ({ttype})")
        return df
    except Exception as e:
        log.error(f"Error parsing OHLCV data: {e}")
        return None


def get_funding_rate(symbol: str) -> Tuple[float, Optional[str]]:
    """Fetch funding rate, with cache and default fallback."""
    cache = _load_cache()
    key = f"{symbol}_funding"
    now = time.time()
    if key in cache and now - cache[key]["ts"] < CACHE_TTL:
        return cache[key]["rate"], None

    api_key = os.getenv("BINANCE_API_KEY")
    if not api_key:
        log.warning("BINANCE_API_KEY missing, using default funding rate 0.0")
        rate = 0.0
        cache[key] = {"rate": rate, "ts": now}
        _save_cache(cache)
        return rate, "Funding rate unavailable"

    url = API_URLS["binance"]["futures"]["funding"]
    params = {"symbol": f"{symbol}USDT"}
    data = get(url, params)
    try:
        rate = float(data[0]["fundingRate"])
    except Exception as e:
        log.error(f"Funding fetch error: {e}")
        rate = 0.0
    cache[key] = {"rate": rate, "ts": now}
    _save_cache(cache)
    return rate, None


def get_open_interest(symbol: str) -> Tuple[float, Optional[str]]:
    """Fetch open interest, fallback to mean volume if API key missing."""
    cache = _load_cache()
    key = f"{symbol}_oi"
    now = time.time()
    if key in cache and now - cache[key]["ts"] < CACHE_TTL:
        return cache[key]["oi"], None

    api_key = os.getenv("BINANCE_API_KEY")
    if not api_key:
        df = get_ohlcv(symbol, "futures", is_futures=True)
        oi = float(df["volume"].mean()) if df is not None else 0.0
        cache[key] = {"oi": oi, "ts": now}
        _save_cache(cache)
        return oi, "Open interest unavailable"

    url = API_URLS["binance"]["futures"]["open_interest"]
    params = {"symbol": f"{symbol}USDT"}
    data = get(url, params)
    try:
        oi = float(data["openInterest"])
    except Exception as e:
        log.error(f"Open interest fetch error: {e}")
        oi = 0.0
    cache[key] = {"oi": oi, "ts": now}
    _save_cache(cache)
    return oi, None


def get_leverage_bracket(symbol: str) -> Tuple[float, Optional[str]]:
    """
    Fetch maintenance margin ratio for a futures contract, or return a default if:
      - the symbol is not listed in Binance Futures
      - API credentials are missing
      - any other error occurs
    """

    cache = _load_cache()
    key = f"{symbol}_bracket"
    now = time.time()
    cached_entry = cache.get(key)
    if cached_entry and now - cached_entry["ts"] < CACHE_TTL:
        return cached_entry["margin"], None

    # Step 1: check if this futures symbol is valid at all
    if not validate_futures_symbol(symbol):
        log.warning(
            f"Symbol {symbol} not valid on Binance Futures; using default margin.")
        default_margin = DEFAULT_MAINT_MARGIN
        _cache_margin(cache, key, default_margin, now)
        return default_margin, "Symbol not listed on Binance Futures"

    # Step 2: ensure API credentials exist
    api_key = os.getenv("BINANCE_API_KEY")
    api_secret = os.getenv("BINANCE_API_SECRET")
    if not api_key or not api_secret:
        log.warning("API credentials missing, default margin=0.01")
        margin = DEFAULT_MAINT_MARGIN
        _cache_margin(cache, key, margin, now)
        return margin, "Using default maintenance margin (no API key)"

    # Step 3: get serverTime first to avoid timestamp mismatch
    time_url = API_URLS["binance"]["futures"].get(
        "time", "https://fapi.binance.com/fapi/v1/time"
    )
    try:
        resp = get(time_url, {})
        server_time = resp.get("serverTime", int(time.time() * 1000))
    except Exception:
        log.warning(
            "Could not fetch Binance serverTime; using local time instead.")
        server_time = int(time.time() * 1000)

    # Step 4: build the signed request to /fapi/v1/leverageBracket
    bracket_url = API_URLS["binance"]["futures"]["leverage_bracket"]
    params = {"symbol": f"{symbol}USDT", "timestamp": server_time}
    query = urlencode(params)
    signature = hmac.new(
        api_secret.encode(), query.encode(), hashlib.sha256
    ).hexdigest()
    signed_params = {**params, "signature": signature}
    headers = {"X-MBX-APIKEY": api_key}

    try:
        data = get(bracket_url, signed_params, headers)
    except Exception as e:
        log.error(f"Bracket fetch error: {e}")
        margin = (
            cached_entry["margin"] if cached_entry is not None else DEFAULT_MAINT_MARGIN
        )
        warning = (
            "Could not fetch official bracket; using cached maintenance margin."
            if cached_entry is not None
            else "Could not fetch official bracket; using default maintenance margin."
        )
        _cache_margin(cache, key, margin, now)
        return margin, warning

    # Step 5: interpret the response structure
    if data is None:
        margin = (
            cached_entry["margin"] if cached_entry is not None else DEFAULT_MAINT_MARGIN
        )
        warning = (
            "Could not fetch official bracket; using cached maintenance margin."
            if cached_entry is not None
            else "Could not fetch official bracket; using default maintenance margin."
        )
        log.warning(
            f"Binance leverageBracket returned no data for {symbol}; using margin={margin}."
        )
        _cache_margin(cache, key, margin, now)
        return margin, warning

    margin = DEFAULT_MAINT_MARGIN
    warning: Optional[str] = None
    parsed_margin = _extract_maint_margin_ratio(data)
    if parsed_margin is not None:
        margin = parsed_margin
    else:
        log.error(f"Unrecognized leverageBracket response: {data}")
        warning = "Unexpected response format; using default maintenance margin."

    _cache_margin(cache, key, margin, now)
    return margin, warning
