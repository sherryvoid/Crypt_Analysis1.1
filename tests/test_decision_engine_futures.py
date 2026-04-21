import pathlib
import pandas as pd
import re
from services.indicators import analyze_indicators
from services.decision_engine import generate_recommendation

CSV_PATH = pathlib.Path(__file__).parent / "ohlcv_eth_1h.csv"


def test_futures_reco_has_liquidation_and_confidence():
    df = pd.read_csv(CSV_PATH, parse_dates=["timestamp"])
    ind = analyze_indicators(df, "futures")

    fake_sent = {"fng_label": "Neutral", "social_score": 0, "news_score": 0}
    text = generate_recommendation(
        sym="ETH", amt=500, ttype="futures", risk="medium",
        ind=ind, sent=fake_sent,
        is_futures=True, margin=500, leverage=5,
        entry_price=ind["price"], ohlcv_df=df
    )

    # --- Assertions --------------------------------------------------
    # Did not crash and returned str
    assert isinstance(text, str) and len(text) > 50

    # Confidence line exists and has %
    assert re.search(r"\*\*Confidence\*\*: \d+\.\d+% ", text)

    # Liquidation price line present
    assert "Liquidation Price" in text
