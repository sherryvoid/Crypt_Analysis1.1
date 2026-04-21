from __future__ import annotations

"""
Configuration for Crypto Predictor:
- API endpoints
- HTTP and Binance parameters
- Default trading settings
"""

# Environment variable keys
ENV_VARS = {
    'BINANCE_API_KEY': 'Your Binance API key',
    'BINANCE_API_SECRET': 'Your Binance API secret',
    'CRYPTOPANIC_API_KEY': 'CryptoPanic API key',
    'DEFAULT_EMAIL': 'Default email for reports',
}

# Binance API endpoints
API_URLS = {
    'binance': {
        'spot': {
            'klines': 'https://api.binance.com/api/v3/klines',
        },
        'futures': {
            'klines': 'https://fapi.binance.com/fapi/v1/klines',
            'price': 'https://fapi.binance.com/fapi/v1/ticker/price',
            'funding': 'https://fapi.binance.com/fapi/v1/fundingRate',
            'open_interest': 'https://fapi.binance.com/fapi/v1/openInterest',
            'leverage_bracket': 'https://fapi.binance.com/fapi/v1/leverageBracket',
        },
    },
}

# Timeframes for OHLCV data
TIMEFRAMES = {
    'very-short': '15m',   # 15-minute candles
    'scalping':    '1h',   # 1-hour candles
    'short-term':  '1h',   # 1-hour candles
    'long-term':   '1d',   # 1-day candles
    'futures':     '4h',   # 4-hour candles
}

# Data limits (number of candles)
LIMITS = {
    'very-short': 40,      # ~10h at 15m
    'scalping':    100,    # ~4d at 1h
    'short-term':  168,    # 7d at 1h
    'long-term':   365,    # 1y at 1d
    'futures':     672,    # 28d at 4h
}

# Stop-loss and take-profit percentages by risk level
SL_PCT = {
    'low':    {'spot': 0.008, 'futures': 0.012},
    'medium': {'spot': 0.016, 'futures': 0.024},
    'high':   {'spot': 0.032, 'futures': 0.048},
}

TP_PCT = {
    'low':    {'spot': 0.012, 'futures': 0.018},
    'medium': {'spot': 0.024, 'futures': 0.036},
    'high':   {'spot': 0.048, 'futures': 0.072},
}

# HTTP client retry settings
MAX_HTTP_RETRIES = 5
TIMEOUT_SECONDS = 10
RATE_LIMIT_DELAY = 1.2  # sec between requests

# Volatility thresholds (used for TP/SL logic)
ATR_VOL_THRESHOLD_PCT = 3.0  # ATR >3% of price
ATR_SL_EXTRA_CAP = 0.5  # Cap extra SL adjustment
