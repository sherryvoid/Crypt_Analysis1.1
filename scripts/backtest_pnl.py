# File: scripts/backtest_pnl.py
# (or scripts/backtest_scores.py – whichever is your backtest file)

import sys
import logging
import matplotlib.pyplot as plt
import pandas as pd

from services.binance_api import get_ohlcv
from services.indicators import analyze_indicators
from services.sentiment_api import get_combined_sentiment
from services.decision_engine import score_strategy

log = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# PARAMETERS (you can adjust these)
ENTRY_THRESHOLD = 8    # enter long if score ≥ +8, short if score ≤ –8
EXIT_THRESHOLD = 0    # go flat when score crosses back through zero
RISK_LEVEL = "medium"
SYMBOL = "ETH"
TTYPE = "short-term"   # e.g. "scalping", "short-term", "long-term"
AMOUNT = 1.0            # use “1 unit” for percentage returns (i.e. 1.0 = \$1)
# ─────────────────────────────────────────────────────────────────────────────


def backtest_spot_strategy(symbol: str,
                           ttype: str,
                           amount: float,
                           entry_thresh: float,
                           risk: str) -> pd.DataFrame:
    """
    Returns a DataFrame indexed by timestamp that contains:
      - 'score'           : the raw score each bar
      - 'position'        : +1 for long, -1 for short, 0 for flat
      - 'strategy_return' : return for that bar (pct change * position)
      - 'cumulative_return': cumulative product of (1 + strategy_return) - 1
    """
    # 1) Fetch OHLCV
    df = get_ohlcv(symbol, ttype)
    if df is None or df.empty:
        print(f"❌ No OHLCV data for {symbol}/{ttype}")
        sys.exit(1)

    # 2) Prepare columns
    df = df.copy()
    df["score"] = float("nan")
    df["position"] = 0
    df["strategy_return"] = 0.0
    df["cumulative_return"] = 0.0

    # 3) Compute indicators up front (for each bar)
    #    We’ll call analyze_indicators on every row’s “past” data:
    for i in range(len(df)):
        # Only analyze indicators once we have ≥ 20–50 bars of history (depending on indicator lengths)
        if i < 20:
            continue

        subset = df.iloc[: i + 1]   # all bars up to index i
        ind = analyze_indicators(subset, ttype)
        sentiment = get_combined_sentiment(symbol, is_futures=False)

        # run your score_strategy on this single bar
        sc, used, missing = score_strategy(
            symbol,
            amount,
            ttype,
            risk,
            sentiment,
            subset,
            ind,
            is_futures=False,
            leverage=1.0,
            entry_price=ind.get("price", subset["close"].iloc[-1]),
        )

        df.iloc[i, df.columns.get_loc("score")] = sc

    # 4) Generate “position” column by scanning the score series
    #    Long if score ≥ entry_thresh; Short if score ≤ –entry_thresh; else flat.
    pos = 0
    for i in range(len(df)):
        sc = df["score"].iloc[i]
        if pd.notna(sc):
            if sc >= entry_thresh:
                pos = 1
            elif sc <= -entry_thresh:
                pos = -1
            # exit when crossing back through zero
            elif pos != 0 and abs(sc) < EXIT_THRESHOLD:
                pos = 0
        df.iloc[i, df.columns.get_loc("position")] = pos

    # 5) Compute strategy_return = position.shift(1) * bar_return
    df["close_prev"] = df["close"].shift(1)
    df["bar_return"] = df["close"] / df["close_prev"] - 1.0
    df["strategy_return"] = df["position"].shift(
        1).fillna(0) * df["bar_return"].fillna(0)

    # 6) Build cumulative return
    df["cumulative_return"] = (1.0 + df["strategy_return"]).cumprod() - 1.0

    # Drop intermediate helper cols
    df = df.drop(columns=["close_prev", "bar_return"])
    return df


def main():
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

    print(
        f"\nBacktesting {SYMBOL} / {TTYPE} (entry ≥ {ENTRY_THRESHOLD} or ≤ -{ENTRY_THRESHOLD}) …")
    bt_results = backtest_spot_strategy(
        SYMBOL, TTYPE, AMOUNT, ENTRY_THRESHOLD, RISK_LEVEL)

    # ─── ADDED: Print the first 100 rows of score/position/strategy_return ─────
    print("\nFirst 100 rows of backtest (timestamp, score, position, strategy_return):")
    cols_to_show = ["score", "position", "strategy_return"]
    print(bt_results[cols_to_show].head(100).to_string())
    # ─────────────────────────────────────────────────────────────────────────────

    # ─── ADDED: Find the first index where strategy_return ≠ 0 and only plot from there
    nonzero_idx = bt_results["strategy_return"].ne(0).idxmax()
    # If no nonzero at all, just plot the whole series
    if bt_results["strategy_return"].abs().sum() == 0:
        sub = bt_results
    else:
        sub = bt_results.loc[nonzero_idx:]
    # ─────────────────────────────────────────────────────────────────────────────

    # 7) Plot
    plt.figure(figsize=(10, 5))
    plt.plot(sub.index, sub["cumulative_return"],
             label=f"{SYMBOL} {TTYPE} Strategy")
    plt.title(
        f"{SYMBOL} ({TTYPE}) Backtest PnL (Threshold = ±{ENTRY_THRESHOLD})")
    plt.xlabel("Date")
    plt.ylabel("Cumulative Return")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    main()
