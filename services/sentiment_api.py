import logging
import time
from .social_api import get_cryptopanic_score
from .http_client import get
from .binance_api import get_funding_rate, get_open_interest

log = logging.getLogger(__name__)

# In-memory cache for sentiment
_CACHE = {}
_CACHE_TTL = 3600  # 1 hour


def get_fear_and_greed_index() -> tuple[float, str | None]:
    """Fetch the latest Fear & Greed Index."""
    url = "https://api.alternative.me/fng/?limit=1"
    data = get(url)
    if not data or 'data' not in data:
        log.error("FNG fetch failed")
        return 0.5, 'FNG unavailable'
    try:
        val = float(data['data'][0]['value']) / 100.0
        return max(0.0, min(1.0, val)), None
    except Exception as e:
        log.error(f"FNG parse error: {e}")
        return 0.5, str(e)


def get_combined_sentiment(symbol: str, is_futures: bool = False) -> dict:
    """
    Combine FNG, social, news, and futures metrics into a unified sentiment dict.
    """
    now = time.time()
    cache_key = f"sent_{symbol}"
    ts_key = f"sent_{symbol}_ts"
    if cache_key in _CACHE and now - _CACHE.get(ts_key, 0) < _CACHE_TTL:
        return _CACHE[cache_key]

    result = {'warnings': []}
    # Fear & Greed
    fng, warning = get_fear_and_greed_index()
    result['fng_score'] = fng
    if warning:
        result['warnings'].append(warning)

    # Social placeholder
    result['social_score'] = 0.5

    # CryptoPanic news sentiment
    news, warning = get_cryptopanic_score(symbol.upper())
    result['news_score'] = news
    if warning:
        result['warnings'].append(warning)

    # Futures-specific metrics
    if is_futures:
        fr, warning = get_funding_rate(symbol)
        result['funding_rate'] = fr
        if warning:
            result['warnings'].append(warning)
        oi, warning = get_open_interest(symbol)
        result['open_interest'] = oi
        if warning:
            result['warnings'].append(warning)

    # Combined sentiment: 50% FNG, 50% news
    combined = 0.5 * result['fng_score'] + 0.5 * result['news_score']
    result['combined'] = max(0.0, min(1.0, combined))

    # Cache the result
    _CACHE[cache_key] = result
    _CACHE[ts_key] = now

    log.info(f"Combined sentiment for {symbol}: {result}")
    return result
