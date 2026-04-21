from services.report_generator import generate_pdf_report, generate_multi_pdf_report
from services.decision_engine import score_strategy, generate_recommendation
import pandas as pd
import pytest
import os
import sys

# ───────────────────────────────────────────────────────────────────────────────
# Insert project root into sys.path so "import services.*" will work.
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
# ───────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def minimal_ohlcv():
    """
    A tiny OHLCV DataFrame with predictable values.
    """
    data = {
        'open':   [100.0, 101.0, 102.0, 103.0, 104.0],
        'high':   [101.0, 102.0, 103.0, 104.0, 105.0],
        'low':    [99.0, 100.0, 101.0, 102.0, 103.0],
        'close':  [100.0, 101.0, 102.0, 103.0, 104.0],
        'volume': [10.0,  10.0,  10.0,  10.0,  10.0]
    }
    return pd.DataFrame(data)


def test_score_strategy_all_neutral(minimal_ohlcv):
    """
    If all indicators and sentiment are neutral, score_strategy
    should return a reasonable integer and place MACD in `missing`.
    """
    ind = {
        'price': 104.0,
        'rsi': 50.0,                            # neutral RSI
        'macd': {'crossover': 'neutral', 'histogram': 0.0},
        'bollinger': {'breakout': 'inside'},
        'volume_spike': 0.3,                    # below spike thresholds
        'volume_divergence': 'neutral',
        'adx': 20.0,                            # below strong-trend cutoff
        'trend': {'crossover': 'neutral'},
        'support': 100.0,
        'resistance': 110.0,
        'fibonacci': {'fib_0.618': 102.0},
        'atr': 1.0
    }

    sentiment = {
        'fng_score': 0.5,
        'news_score': 0.0,
        'combined': 0.5
    }

    score, used, missing = score_strategy(
        symbol="TEST",
        amount=100.0,
        ttype="scalping",
        risk="medium",
        sentiment=sentiment,
        ohlcv_df=minimal_ohlcv,
        ind=ind,
        is_futures=False
    )

    # Score is an integer in a plausible range
    assert isinstance(score, int)
    assert -10 < score < 20

    # “RSI” was provided → should appear in used, not missing
    assert "RSI" in used
    assert "RSI" not in missing

    # “MACD” had a "neutral" crossover → code treats this as missing
    assert "MACD" in missing
    assert "MACD" not in used


@pytest.fixture
def dummy_multi_results_only():
    """
    A minimal “multi_results” list with one coin’s row for testing.
    """
    return [{
        'coin': 'ABC',
        'market': 'Spot (Scalping)',
        'score': 5,
        'conf': 50.0,
        'price': 100.0,
        'tp': 102.0,
        'sl': 98.0,
        'p_up': 60.0,
        'p_down': 40.0
    }]


@pytest.fixture
def dummy_result_text_single():
    """
    A minimal dummy result_text that has a “### Summary” block.
    """
    return (
        "=== TEST/USDT Scalping Analysis ===\n"
        "Some trade summary line\n"
        "---\n"
        "### Summary (Spot, Scalping, Medium Risk)\n"
        "Dummy summary here."
    )


def test_generate_recommendation_contains_summary(minimal_ohlcv):
    """
    generate_recommendation(...) must embed a “### Summary” block
    containing “Reliability Rating” and “Trade Plan.”
    """
    ind = {
        'price': 104.0,
        'rsi': 20.0,                            # strongly oversold
        'macd': {'crossover': 'bullish', 'histogram': 1.0},
        'bollinger': {'breakout': 'inside'},
        'volume_spike': 2.0,                    # high volume spike
        'volume_divergence': 'bullish',
        'adx': 30.0,
        'trend': {'crossover': 'golden'},
        'support': 100.0,
        'resistance': 110.0,
        'fibonacci': {'fib_0.618': 103.0},
        'atr': 1.0
    }

    sentiment = {
        'fng_score': 0.8,
        'news_score': 1.0,
        'combined': 0.9
    }

    text = generate_recommendation(
        symbol="TEST",
        amount=100.0,
        ttype="scalping",
        risk="low",
        ind=ind,
        sentiment=sentiment,
        ohlcv_df=minimal_ohlcv,
        is_futures=True,
        leverage=2.0,
        entry_price=104.0
    )

    # It should contain “### Summary”
    assert "### Summary" in text

    # It should contain “Reliability Rating” and “Trade Plan”
    assert "Reliability Rating" in text
    assert "Trade Plan" in text


def test_generate_multi_pdf_report_creates_file(tmp_path, dummy_multi_results_only):
    """
    generate_multi_pdf_report(...) should write out a .pdf file when given a second argument `summaries`.
    """
    # Pass an empty list/dict as `summaries` (the second parameter)
    out_path = generate_multi_pdf_report(
        dummy_multi_results_only, summaries=[])

    # Must return a .pdf path that exists on disk
    assert out_path is not None
    assert out_path.lower().endswith(".pdf")
    assert os.path.isfile(out_path)

    # Cleanup
    os.remove(out_path)


def test_generate_pdf_report_creates_file(tmp_path, dummy_result_text_single):
    """
    generate_pdf_report(...) should write out a .pdf file.
    """
    df = pd.DataFrame({
        'open':   [1.0, 2.0],
        'high':   [2.0, 3.0],
        'low':    [1.0, 2.0],
        'close':  [2.0, 3.0],
        'volume': [10.0, 20.0]
    })

    out_path = generate_pdf_report(
        symbol="TEST",
        ttype="scalping",
        result_text=dummy_result_text_single,
        df=df,
        best_strategy=None,
        best_strategy_scores=None,
        confidence=50.0,
        verdict=""
    )

    # Must return a valid .pdf path that exists on disk
    assert out_path is not None
    assert out_path.lower().endswith(".pdf")
    assert os.path.isfile(out_path)

    # Cleanup
    os.remove(out_path)


if __name__ == "__main__":
    # Running “python tests/test_suite.py” will invoke pytest on this file
    pytest.main([__file__])
