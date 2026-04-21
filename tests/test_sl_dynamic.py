import pandas as pd
import numpy as np
from services.decision_engine import generate_recommendation
from services.indicators import analyze_indicators


def test_sl_widens_with_big_atr(sample_ohlcv):
    df = sample_ohlcv.copy()
    df["high"] *= 1.05  # inflate ATR
    ind = analyze_indicators(df, "short-term")
    txt = generate_recommendation("BTC", 100, "short-term",
                                  "medium", ind,
                                  {"fng_label": "Neutral"}, ohlcv_df=df)
    assert "High volatility detected" in txt
