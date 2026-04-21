import logging
from typing import List, Dict, Tuple

log = logging.getLogger(__name__)

# Category weights for confidence breakdown
WEIGHTS = {
    "technical": 0.5,
    "price_structure": 0.3,
    "sentiment": 0.2,
    "risk": 0.0,
}

# Define indicator categories
TECHNICAL = ["RSI", "MACD", "Bollinger",
             "ADX", "Volume Spike", "Volume Divergence"]
PRICE_STRUCTURE = ["Trend", "Support", "Resistance"]
SENTIMENT = ["Fear & Greed", "News", "Sentiment"]
FUTURES = ["Funding Rate", "Open Interest"]


def calculate_weighted_confidence(
    score: int,
    used: List[str],
    missing: List[str],
    indicators: Dict
) -> Tuple[float, Dict[str, float]]:
    """
    Calculate a confidence percentage and breakdown by category.

    - score: the overall strategy score
    - used: list of indicators included in scoring
    - missing: list of indicators not available
    - indicators: raw indicator dict for additional penalties
    """
    log.info(
        f"Calculating confidence for score={score}, used={used}, missing={missing}"
    )

    # ─── A) Base confidence: 50 + 2.5×|score|, capped at 100 ────────────────
    base = min(100, 50 + abs(score) * 2.5)

    # ─── B) Missing‐indicator penalty: −5 points per missing ────────────────
    missing_penalty = len(missing) * 5

    # ─── C) Category counts ─────────────────────────────────────────────────
    tech_count = sum(1 for i in used if i in TECHNICAL)
    price_count = sum(1 for i in used if i in PRICE_STRUCTURE)
    sentiment_count = sum(1 for i in used if i in SENTIMENT)
    futures_count = sum(1 for i in used if i in FUTURES)

    # ─── D) Compute breakdown (each category scaled by its WEIGHTS) ────────
    breakdown = {
        "Technical Indicators": (tech_count / len(TECHNICAL) * 100) * WEIGHTS["technical"],
        "Price Structure": (price_count / len(PRICE_STRUCTURE) * 100) * WEIGHTS["price_structure"],
        "Market Sentiment": (sentiment_count / len(SENTIMENT) * 100) * WEIGHTS["sentiment"],
        "Risk Factors": 0.0,
    }

    # ─── E) Apply missing penalties to base ─────────────────────────────────
    confidence = base - missing_penalty

    # ─── F) Additional penalties ────────────────────────────────────────────

    # 1) Neutral trend penalty
    trend = indicators.get("trend", {}).get("crossover")
    if trend == "neutral":
        confidence -= 5
        log.debug("Applied neutral trend penalty: -5%")

    # 2) Mixed RSI/MACD penalty
    rsi = indicators.get("rsi")
    macd = indicators.get("macd", {}).get("crossover")
    if rsi is not None and macd:
        rsi_bull = rsi < 40
        macd_bull = macd == "bullish"
        # if RSI and MACD disagree, apply −5
        if rsi_bull ^ macd_bull:
            confidence -= 5
            log.debug("Applied mixed RSI/MACD penalty: -5%")

    # ─── G) Cap between 0–90 to prevent overstating confidence ───────────────
    confidence = max(0, min(90, confidence))

    log.info(f"Confidence: {confidence}%, breakdown: {breakdown}")
    return confidence, breakdown
