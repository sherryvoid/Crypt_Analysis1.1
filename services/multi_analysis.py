import logging
from typing import List, Dict, Any, Tuple
import pandas as pd

from .binance_api import get_ohlcv, get_funding_rate, get_open_interest, get_leverage_bracket
from .indicators import analyze_indicators
from .sentiment_api import get_combined_sentiment
from .decision_engine import (
    recommend_best_strategy,
    score_strategy,
)
from .confidence_engine import calculate_weighted_confidence
from .http_client import get

log = logging.getLogger(__name__)


def fetch_top5_spot() -> List[str]:
    """
    Fetch top 5 spot symbols by 24h quote volume (USDT pairs).
    """
    url = "https://api.binance.com/api/v3/ticker/24hr"
    data = get(url)
    if not isinstance(data, list):
        log.warning(
            "Could not fetch top‐5 spot tickers; falling back to default list.")
        return ["BTC", "ETH", "BNB", "XRP", "SOL"]

    # Filter only USDT pairs
    usdt_pairs = [d for d in data if d.get("symbol", "").endswith("USDT")]
    # Sort by quoteVolume (as float) descending
    usdt_pairs.sort(key=lambda d: float(d.get("quoteVolume", 0)), reverse=True)
    top5 = [d["symbol"][:-4] for d in usdt_pairs[:5]]
    return top5


def multi_coin_analysis(
    symbols: List[str],
    amount: float,
    leverage: float = 1.0,
) -> Dict[str, Dict[str, Any]]:
    """
    For each symbol in `symbols`, run both spot and futures analysis (risk=medium).
    Decide which “market” (spot vs. futures) yields a stronger “rule‐score.”
    Return a dict mapping each symbol to:
      {
        "spot": {
            "strategy": <"scalping"/"short-term"/"long-term">,
            "score": <int>,
            "confidence": <float>
        },
        "futures": {
            "strategy": "futures",
            "score": <int>,
            "confidence": <float>
        },
        "chosen_market": <"spot" or "futures">
      }
    """
    results: Dict[str, Dict[str, Any]] = {}

    for sym in symbols:
        sym = sym.upper()
        log.info(f"Starting multi‐coin analysis for {sym}")

        # ── SPOT SIDE ──
        spot_best_strategy = None
        spot_score = None
        spot_conf = None

        # First, run recommend_best_strategy (spot only)
        try:
            # Always use risk="medium"
            sentiment_spot = get_combined_sentiment(sym, is_futures=False)
            best_spot, spot_scores = recommend_best_strategy(
                sym, amount, "medium", sentiment_spot, get_ohlcv, analyze_indicators
            )

            # Once we know best_spot, recompute its exact score+confidence
            df_spot = get_ohlcv(sym, best_spot, is_futures=False)
            if df_spot is not None and not df_spot.empty:
                ind_spot = analyze_indicators(df_spot, best_spot)
                score_spot_val, used_spot, missing_spot = score_strategy(
                    sym,
                    amount,
                    best_spot,
                    "medium",
                    sentiment_spot,
                    df_spot,
                    ind_spot,
                    is_futures=False,
                )
                conf_spot_val, _ = calculate_weighted_confidence(
                    score_spot_val, used_spot, missing_spot, ind_spot
                )
                spot_best_strategy = best_spot
                spot_score = score_spot_val
                spot_conf = conf_spot_val
            else:
                spot_best_strategy = None
                spot_score = None
                spot_conf = None
        except Exception as e:
            log.error(f"Spot analysis failed for {sym}: {e}")
            spot_best_strategy = None
            spot_score = None
            spot_conf = None

        # ── FUTURES SIDE ──
        futures_score = None
        futures_conf = None

        try:
            df_fut = get_ohlcv(sym, "futures", is_futures=True)
            if df_fut is not None and not df_fut.empty:
                ind_fut = analyze_indicators(df_fut, "futures")
                sentiment_fut = get_combined_sentiment(sym, is_futures=True)

                # We treat the “strategy” name as simply "futures"
                # Score + confidence:
                score_fut_val, used_fut, missing_fut = score_strategy(
                    sym,
                    amount,
                    "futures",
                    "medium",
                    sentiment_fut,
                    df_fut,
                    ind_fut,
                    is_futures=True,
                    leverage=leverage,
                    entry_price=ind_fut.get("price", None),
                )
                conf_fut_val, _ = calculate_weighted_confidence(
                    score_fut_val, used_fut, missing_fut, ind_fut
                )
                futures_score = score_fut_val
                futures_conf = conf_fut_val
            else:
                futures_score = None
                futures_conf = None
        except Exception as e:
            log.error(f"Futures analysis failed for {sym}: {e}")
            futures_score = None
            futures_conf = None

        # ── CHOOSE MARKET ──
        if spot_score is None and futures_score is None:
            chosen = None
        elif spot_score is None:
            chosen = "futures"
        elif futures_score is None:
            chosen = "spot"
        else:
            # pick whichever has higher absolute “rule‐score”
            if abs(futures_score) > abs(spot_score):
                chosen = "futures"
            else:
                chosen = "spot"

        results[sym] = {
            "spot": {
                "strategy": spot_best_strategy,
                "score": spot_score,
                "confidence": spot_conf,
            },
            "futures": {
                "strategy": "futures",
                "score": futures_score,
                "confidence": futures_conf,
            },
            "chosen_market": chosen,
        }

        log.info(
            f"→ {sym} chosen={chosen}, spot_score={spot_score}, fut_score={futures_score}")

    return results
