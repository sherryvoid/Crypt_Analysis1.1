import logging
import pandas as pd
import pandas_ta as ta
import numpy as np

log = logging.getLogger(__name__)


def calculate_pivot_points(df: pd.DataFrame) -> tuple[float, float]:
    """Calculate pivot points (S1, R1) manually."""
    try:
        high = df["high"].rolling(window=20).max().iloc[-1]
        low = df["low"].rolling(window=20).min().iloc[-1]
        close = df["close"].iloc[-1]
        pivot = (high + low + close) / 3
        support = 2 * pivot - high
        resistance = 2 * pivot - low
        return support, resistance
    except Exception as e:
        log.error(f"Pivot point calculation failed: {e}")
        return 0.0, 0.0


def analyze_indicators(df: pd.DataFrame, ttype: str) -> dict:
    """
    Analyze technical indicators for trading signals.
    Args:
        df: OHLCV DataFrame.
        ttype: Trade type (scalping, short-term, long-term, futures).
    Returns:
        Dictionary of indicator values.
    """
    log.info(f"Analyzing indicators for {ttype}")
    if df is None or df.empty:
        log.error("Empty or None OHLCV DataFrame")
        return {}

    indicators = {}
    try:
        # Price
        indicators["price"] = df["close"].iloc[-1]

        # RSI (14)
        rsi = ta.rsi(df["close"], length=14)
        indicators["rsi"] = rsi.iloc[-1] if not rsi.empty else None

        # MACD
        macd = ta.macd(df["close"], fast=12, slow=26, signal=9)
        if macd is not None and not macd.empty:
            indicators["macd"] = {
                "crossover": "bullish" if macd["MACDh_12_26_9"].iloc[-1] > 0 else "bearish",
                "histogram": macd["MACDh_12_26_9"].iloc[-1]
            }

        # Bollinger Bands
        bbands = ta.bbands(df["close"], length=20, std=2)
        if bbands is not None and not bbands.empty:
            upper, lower = bbands["BBU_20_2.0"], bbands["BBL_20_2.0"]
            breakout = "upper" if df["close"].iloc[-1] > upper.iloc[-1] else "lower" if df["close"].iloc[-1] < lower.iloc[-1] else "inside"
            indicators["bollinger"] = {"breakout": breakout}

        # Volume Spike
        if "volume" in df.columns and not df["volume"].empty:
            vol_sma = df["volume"].rolling(window=20).mean()
            indicators["volume_spike"] = df["volume"].iloc[-1] / \
                vol_sma.iloc[-1] if vol_sma.iloc[-1] != 0 else 1.0
        else:
            indicators["volume_spike"] = 1.0

        # Volume Divergence (OBV)
        obv = ta.obv(df["close"], df["volume"])
        if obv is not None and not obv.empty:
            price_trend = df["close"].pct_change().iloc[-1]
            obv_trend = obv.pct_change().iloc[-1]
            indicators["volume_divergence"] = "bearish" if price_trend > 0 and obv_trend < 0 else "bullish" if price_trend < 0 and obv_trend > 0 else "neutral"

        # ADX (14)
        adx = ta.adx(df["high"], df["low"], df["close"], length=14)
        if adx is not None and not adx.empty:
            indicators["adx"] = adx["ADX_14"].iloc[-1]

        # EMA Crossover (Trend)
        ema_fast = ta.ema(df["close"], length=20)
        ema_slow = ta.ema(df["close"], length=50)
        if ema_fast is not None and ema_slow is not None and not ema_fast.empty and not ema_slow.empty:
            crossover = "golden" if ema_fast.iloc[-1] > ema_slow.iloc[-1] and ema_fast.iloc[-2] <= ema_slow.iloc[-2] else \
                        "death" if ema_fast.iloc[-1] < ema_slow.iloc[-1] and ema_fast.iloc[-2] >= ema_slow.iloc[-2] else "neutral"
            indicators["trend"] = {"crossover": crossover}

        # Support/Resistance
        indicators["support"], indicators["resistance"] = calculate_pivot_points(
            df)

        # ATR (14)
        atr = ta.atr(df["high"], df["low"], df["close"], length=14)
        indicators["atr"] = atr.iloc[-1] if atr is not None and not atr.empty else 0.0

        # Fibonacci Retracement
        high, low = df["high"].max(), df["low"].min()
        diff = high - low
        indicators["fibonacci"] = {"fib_0.618": high - 0.618 * diff}

        log.info(f"Indicators calculated: {indicators}")
        return indicators
    except Exception as e:
        log.error(f"Indicator calculation failed: {e}")
        return indicators
# sherry
