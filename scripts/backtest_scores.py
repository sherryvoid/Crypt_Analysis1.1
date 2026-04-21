#!/usr/bin/env python3
from services.sentiment_api import get_combined_sentiment
from services.decision_engine import score_strategy
from services.indicators import analyze_indicators
from services.binance_api import get_ohlcv
import os
import sys
import logging
import pandas as pd
import matplotlib.pyplot as plt

# Make sure the project root is on sys.path
# __file__ is scripts/backtest_scores.py, so os.path.dirname(__file__) == "<project>/scripts"
# We go one level up (..) to reach "<project>"
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger(__name__)


def backtest_symbol(symbol: str, ttype: str, is_futures: bool = False):
    """
    For a given symbol and timeframe, fetch historical OHLCV,
    compute indicators + sentiment, score each candle,
    and return a DataFrame of scores.
    """
    log.info(f"Backtesting {symbol} ({'futures' if is_futures else ttype})")
    df = get_ohlcv(symbol, ttype, is_futures=is_futures)
    if df is None or df.empty:
        log.warning(f"No data for {symbol} - skipping.")
        return None

    scores = []
    timestamps = []
    for i in range(len(df)):
        # Run indicators/sentiment/score on all candles up to index i
        window = df.iloc[: i + 1].copy()
        ind = analyze_indicators(
            window, ttype if not is_futures else "futures")
        sentiment = get_combined_sentiment(symbol, is_futures=is_futures)
        score_val, _, _ = score_strategy(
            symbol,
            1000,              # use $1000 as dummy amount
            ttype,
            "medium",          # use "medium" risk for backtest
            sentiment,
            window,
            ind,
            is_futures,
            leverage=1.0,
            entry_price=ind.get("price", window["close"].iloc[-1])
        )
        scores.append(score_val)
        timestamps.append(window.index[-1])

    result = pd.DataFrame({"timestamp": timestamps, "score": scores})
    result.set_index("timestamp", inplace=True)
    return result


def plot_distribution(df_scores: pd.DataFrame, symbol: str, ttype: str, is_futures: bool):
    plt.figure(figsize=(8, 4))
    df_scores["score"].hist(bins=30)
    plt.title(
        f"{symbol} ({'Futures' if is_futures else ttype.capitalize()}) Score Distribution")
    plt.xlabel("Score")
    plt.ylabel("Frequency")
    os.makedirs("output", exist_ok=True)
    fname = f"output/{symbol}_{'futures' if is_futures else ttype}_scores.png"
    plt.savefig(fname)
    log.info(f"Saved histogram: {fname}")
    plt.close()


def main():
    # Adjust this list as you wish; these are the top-10 symbols we’ll backtest.
    symbols = ["BTC", "ETH", "SOL", "BNB", "ADA",
               "DOGE", "XRP", "DOT", "MATIC", "AVAX"]
    timeframes = [
        ("scalping", False),
        ("short-term", False),
        ("long-term", False),
        ("futures", True),
    ]

    for sym in symbols:
        for ttype, is_fut in timeframes:
            df_scores = backtest_symbol(sym, ttype, is_fut)
            if df_scores is not None:
                plot_distribution(df_scores, sym, ttype, is_fut)


if __name__ == "__main__":
    main()
