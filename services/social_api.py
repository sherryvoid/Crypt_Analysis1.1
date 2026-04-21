import logging
import time
import json
import os
from typing import Tuple, Optional, Dict
from .http_client import get

log = logging.getLogger(__name__)

CACHE_FILE = os.path.join(os.path.dirname(__file__), 'cryptopanic_cache.json')
CACHE_TTL = 3600  # 1 hour


def _load_cache() -> Dict:
    try:
        with open(CACHE_FILE, 'r') as f:
            return json.load(f)
    except Exception:
        return {}


def _save_cache(cache: Dict):
    try:
        os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
        with open(CACHE_FILE, 'w') as f:
            json.dump(cache, f)
    except Exception as e:
        log.error(f"Failed to save cache: {e}")


def get_cryptopanic_score(symbol: str) -> Tuple[float, Optional[str]]:
    """
    Fetch news sentiment from CryptoPanic API v2.
    Returns normalized [-1,1] score and optional warning.
    """
    now = time.time()
    cache = _load_cache()
    key = symbol.upper()
    if key in cache and now - cache[key]['ts'] < CACHE_TTL:
        return cache[key]['score'], None

    api_key = os.getenv('CRYPTOPANIC_API_KEY')
    if not api_key:
        msg = 'CryptoPanic API key missing'
        log.error(msg)
        return 0.0, msg

    url = 'https://cryptopanic.com/api/developer/v2/posts/'
    params = {
        'auth_token': api_key,
        'currencies': symbol.upper(),
        'public': 'true',
        'limit': 20
    }
    try:
        data = get(url, params)
    except Exception as e:
        msg = f"CryptoPanic API error for {symbol}: {e}"
        log.error(msg)
        return 0.0, msg

    # Validate response structure
    if not isinstance(data, dict) or 'results' not in data:
        log.error(f"Unexpected CryptoPanic response for {symbol}: {data}")
        return 0.0, f"Invalid response format from CryptoPanic for {symbol}"

    posts = data.get('results', [])
    sentiment_sum = 0.0
    count = 0
    for post in posts:
        if post.get('kind') != 'news':
            continue
        votes = post.get('votes', {})
        pos = votes.get('positive', 0)
        neg = votes.get('negative', 0)
        total = pos + neg
        if total > 0:
            sentiment_sum += (pos - neg) / total
            count += 1
    score = (sentiment_sum / count) if count > 0 else 0.0
    score = max(-1.0, min(1.0, score))

    cache[key] = {'score': score, 'ts': now}
    _save_cache(cache)
    log.info(f"Fetched CryptoPanic score for {symbol}: {score}")
    return score, None
