from services.decision_engine import generate_recommendation
from services.indicators import analyze_indicators


def test_generate_reco_no_crash(sample_ohlcv, monkeypatch):
    # stub sentiment to zeros so we don't hit network
    fake_sent = {"fng_label": "Neutral", "social_score": 0, "news_score": 0}

    ind = analyze_indicators(sample_ohlcv, "scalping")
    text = generate_recommendation(
        sym="SOL", amt=100, ttype="scalping", risk="medium",
        ind=ind, sent=fake_sent, ohlcv_df=sample_ohlcv
    )
    # Should include the word "SOL/USDT"
    assert "SOL/USDT" in text
