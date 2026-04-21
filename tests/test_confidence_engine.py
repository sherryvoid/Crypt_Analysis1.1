from services.confidence_engine import calculate_weighted_confidence


def test_breakdown_sum_to_confidence():
    conf, breakdown = calculate_weighted_confidence(
        score=4,               # 40 %
        indicators_used=["RSI", "MACD", "Support", "Fear & Greed"],
        indicators_missing=[]
    )
    assert conf == 40.0
    assert round(sum(breakdown.values()), 2) == conf
