import logging
from typing import Callable, Tuple, List, Dict, Optional
import pandas as pd
from datetime import datetime
from math import exp

from services.binance_api import get_leverage_bracket
from services.confidence_engine import calculate_weighted_confidence
from services.config import TIMEFRAMES, LIMITS, SL_PCT, TP_PCT, ATR_VOL_THRESHOLD_PCT
from services.indicators import analyze_indicators
from services.sentiment_api import get_combined_sentiment

log = logging.getLogger(__name__)

# Decision thresholdspyt
MIN_SCORE = 5
MAX_NEG_SCORE = -5
MIN_CONFIDENCE = 55  # %


def calculate_futures_metrics(
    entry_price: float,
    amount: float,
    leverage: float,
    maintenance_margin: float
) -> Tuple[float, float, float]:
    position_size = amount * leverage
    liquidation_price = entry_price * (1 - (1 / leverage) + maintenance_margin)
    margin_fee = position_size * 0.0004
    return position_size, liquidation_price, margin_fee


def score_to_probability(score: float, k: float = 0.1) -> Tuple[float, float]:
    odds = 1 / (1 + exp(-k * score))
    return odds, 1 - odds


def fetch_latest_funding_rate(symbol: str) -> Optional[float]:
    import requests
    try:
        resp = requests.get(
            "https://fapi.binance.com/fapi/v1/premiumIndex",
            params={"symbol": symbol},
            timeout=5
        )
        resp.raise_for_status()
        return float(resp.json().get("lastFundingRate", 0.0))
    except Exception as e:
        log.warning(f"Funding rate fetch failed: {e}")
        return None


def score_strategy(
    symbol: str,
    amount: float,
    ttype: str,
    risk: str,
    sentiment: dict,
    ohlcv_df: pd.DataFrame,
    ind: dict,
    is_futures: bool = False,
    leverage: float = 1.0,
    entry_price: float = 0.0
) -> Tuple[int, List[str], List[str]]:
    score, used, missing, comps = 0, [], [], []

    # RSI
    rsi = ind.get("rsi")
    if rsi is not None:
        used.append("RSI")
        if rsi < 30:
            score += 4
            comps.append("RSI: +4 (oversold)")
        elif rsi > 70:
            score -= 4
            comps.append("RSI: -4 (overbought)")
        elif rsi < 40:
            score += 3
            comps.append("RSI: +3 (near oversold)")
        elif rsi > 60:
            score -= 3
            comps.append("RSI: -3 (near overbought)")
        else:
            score += 1
            comps.append("RSI: +1 (neutral)")
    else:
        missing.append("RSI")
        score -= 3
        comps.append("RSI: -3 (missing)")

    # MACD
    macd = ind.get("macd", {})
    cross = macd.get("crossover")
    if cross in ("bullish", "bearish"):
        used.append("MACD")
        score += 4 if cross == "bullish" else -4
        comps.append(
            f"MACD: {'+4 (bullish)' if cross == 'bullish' else '-4 (bearish)'}")
    else:
        missing.append("MACD")
        score -= 3
        comps.append("MACD: -3 (missing)")

    # Bollinger
    bb = ind.get("bollinger", {}).get("breakout")
    used.append("Bollinger")
    if bb == "upper":
        score += 2
        comps.append("Bollinger: +2 (upper breakout)")
    elif bb == "lower":
        score -= 2
        comps.append("Bollinger: -2 (lower breakout)")
    else:
        comps.append("Bollinger: 0 (inside)")

    # ADX
    adx = ind.get("adx")
    if adx is not None:
        used.append("ADX")
        if adx > 25:
            score += 3
            comps.append("ADX: +3 (strong trend)")
    else:
        missing.append("ADX")
        score -= 2
        comps.append("ADX: -2 (missing)")

    # Volume Spike
    vs = ind.get("volume_spike")
    if vs is not None:
        used.append("Volume Spike")
        if vs > 1.5:
            score += 3
            comps.append("Volume Spike: +3 (high)")
        elif vs > 1.0:
            score += 2
            comps.append("Volume Spike: +2 (moderate)")
        elif vs > 0.5:
            score += 1
            comps.append("Volume Spike: +1 (slight)")
    else:
        missing.append("Volume Spike")
        score -= 2
        comps.append("Volume Spike: -2 (missing)")

    # Volume Divergence
    vd = ind.get("volume_divergence")
    if vd in ("bullish", "bearish"):
        used.append("Volume Divergence")
        score += 3 if vd == "bullish" else -3
        comps.append(
            f"Volume Divergence: {'+3 (bullish)' if vd == 'bullish' else '-3 (bearish)'}")
    else:
        comps.append("Volume Divergence: 0 (neutral)")

    # Trend crossover
    tr = ind.get("trend", {}).get("crossover")
    if tr in ("golden", "death", "neutral"):
        used.append("Trend")
        if tr == "golden":
            score += 4
            comps.append("Trend: +4 (golden cross)")
        elif tr == "death":
            score -= 4
            comps.append("Trend: -4 (death cross)")
        elif tr == "neutral" and adx and adx > 30:
            score += 2
            comps.append("Trend: +2 (neutral, strong ADX)")
    else:
        missing.append("Trend")
        score -= 3
        comps.append("Trend: -3 (missing)")

    # Support & Resistance
    price = ind.get("price", ohlcv_df["close"].iloc[-1])
    sup, res = ind.get("support"), ind.get("resistance")
    if sup:
        used.append("Support")
        if price < sup*1.02:
            score += 3
            comps.append("Support: +3 (near)")
    else:
        missing.append("Support")
        score -= 2
        comps.append("Support: -2 (missing)")
    if res:
        used.append("Resistance")
        if price > res*0.98:
            score -= 3
            comps.append("Resistance: -3 (near)")
    else:
        missing.append("Resistance")
        score -= 2
        comps.append("Resistance: -2 (missing)")

    # Fibonacci
    fib_618 = ind.get("fibonacci", {}).get("fib_0.618")
    if fib_618 and abs(price-fib_618)/fib_618 <= 0.01:
        used.append("Fibonacci")
        score += 2
        comps.append("Fibonacci: +2 (within 1% of 0.618)")

    # Sentiment
    fng = sentiment.get("fng_score")
    if fng is not None:
        used.append("Fear & Greed")
        if fng > 0.7:
            score += 3
            comps.append("Fear & Greed: +3 (greed)")
        elif fng < 0.3:
            score -= 3
            comps.append("Fear & Greed: -3 (fear)")
    else:
        missing.append("Fear & Greed")
        score -= 2
        comps.append("Fear & Greed: -2 (missing)")
    news = sentiment.get("news_score")
    if news is not None:
        used.append("News")
        if news > 0:
            score += 3
            comps.append("News: +3 (positive)")
        elif news < 0:
            score -= 3
            comps.append("News: -3 (negative)")
    else:
        missing.append("News")
        score -= 1
        comps.append("News: -1 (missing)")
    comb = sentiment.get("combined")
    if comb is not None:
        used.append("Sentiment")
        if comb > 0.7:
            score += 2
            comps.append("Sentiment: +2 (very bullish)")
        elif comb > 0.5:
            score += 1
            comps.append("Sentiment: +1 (bullish)")
        elif comb < 0.3:
            score -= 1
            comps.append("Sentiment: -1 (bearish)")

    # Futures extras
    if is_futures:
        fr = sentiment.get("funding_rate")
        if fr is None:
            fr = fetch_latest_funding_rate(symbol+"USDT")
            if fr is not None:
                sentiment["funding_rate"] = fr
        if fr is not None:
            used.append("Funding Rate")
            if fr < 0:
                score += 2
                comps.append("Funding Rate: +2 (negative)")
            else:
                score -= 2
                comps.append("Funding Rate: -2 (positive)")
        else:
            missing.append("Funding Rate")
            score -= 1
            comps.append("Funding Rate: -1 (missing)")
        oi = sentiment.get("open_interest")
        if oi is not None:
            used.append("Open Interest")
            avg_vol = ohlcv_df["volume"].mean()
            if oi > avg_vol*2:
                score -= 2
                comps.append("Open Interest: -2 (high)")
        else:
            missing.append("Open Interest")
            score -= 1
            comps.append("Open Interest: -1 (missing)")

    # Bonuses and penalties
    if ttype == "scalping":
        score += 2
        comps.append("Scalping Bonus: +2")
    if ttype == "long-term":
        score += 1
        comps.append("Long-Term Bonus: +1")
    if risk == "low":
        score += 1
        comps.append("Low Risk Bonus: +1")
    if risk == "high":
        score -= 1
        comps.append("High Risk Penalty: -1")

    return score, used, missing


def recommend_best_strategy(
    symbol: str,
    amount: float,
    risk: str,
    sentiment: dict,
    get_ohlcv: Callable,
    analyze_indicators: Callable
) -> Tuple[str, Dict[str, int]]:
    strategies = ["scalping", "short-term", "long-term"]
    scores = {}
    for s in strategies:
        df = get_ohlcv(symbol, s)
        if df is None or df.empty:
            scores[s] = -999
            continue
        ind = analyze_indicators(df, s)
        sc, _, _ = score_strategy(
            symbol, amount, s, risk, get_combined_sentiment(symbol, False), df, ind)
        scores[s] = sc
    return max(scores, key=scores.get), scores


def generate_recommendation(
    symbol: str,
    amount: float,
    ttype: str,
    risk: str,
    ind: dict,
    sentiment: dict,
    ohlcv_df: Optional[pd.DataFrame] = None,
    is_futures: bool = False,
    leverage: float = 1.0,
    entry_price: Optional[float] = None
) -> str:
    if ohlcv_df is None or ohlcv_df.empty:
        return f"No data for {symbol}."

    tf = TIMEFRAMES.get(ttype, "N/A")
    n = LIMITS.get(ttype, 0)
    ts = datetime.now().strftime("%I:%M %p, %B %d, %Y")

    lines = [
        f"⏱ Using {tf} timeframe (last {n} candles) for {ttype.capitalize()}",
        f"=== {symbol}/USDT {ttype.capitalize()} Analysis (as of {ts}) ===",
        ""
    ]

    price = entry_price if (is_futures and entry_price) else ind.get(
        "price", ohlcv_df["close"].iloc[-1])
    score, used, missing = score_strategy(
        symbol, amount, ttype, risk, sentiment, ohlcv_df, ind, is_futures, leverage, entry_price or price)
    conf, breakdown = calculate_weighted_confidence(score, used, missing, ind)
    conf = max(0, min(conf, 100))
    p_up, p_down = score_to_probability(score)

    # Decide action
    if is_futures:
        if score >= MIN_SCORE and conf >= MIN_CONFIDENCE:
            action = "GO LONG"
        elif score <= MAX_NEG_SCORE and conf >= MIN_CONFIDENCE:
            action = "GO SHORT"
        else:
            action = "HOLD"
    else:
        if score >= MIN_SCORE and conf >= MIN_CONFIDENCE:
            action = "Bullish"
        elif score <= MAX_NEG_SCORE and conf >= MIN_CONFIDENCE:
            action = "Bearish"
        else:
            action = "Neutral"

    lines += [
        f"Investment: ${amount:.2f} | Entry Price: ${price:.2f}",
        f"Rule-Score: {score}  → P(Up): {p_up*100:.1f}%, P(Down): {p_down*100:.1f}%",
        f"Action: {action} ({int(conf)}% confidence)",
        ""
    ]

    sup = ind.get("support", 0.0)
    res = ind.get("resistance", 0.0)
    lines += [
        f"Support (20-period pivot on {tf}): ${sup:.4f}",
        f"Resistance (20-period pivot on {tf}): ${res:.4f}",
        ""
    ]

    # TP/SL
    atr_val = ind.get("atr")
    if atr_val and atr_val > 0:
        sl_val = price-atr_val
        tp_val = price+atr_val
        if (atr_val/price*100) < ATR_VOL_THRESHOLD_PCT:
            tp_val = price * \
                (1+TP_PCT[risk]["futures" if is_futures else "spot"])
            sl_val = price * \
                (1-SL_PCT[risk]["futures" if is_futures else "spot"])
    else:
        tp_val = price*(1+TP_PCT[risk]["futures" if is_futures else "spot"])
        sl_val = price*(1-SL_PCT[risk]["futures" if is_futures else "spot"])
    profit = (tp_val-price)*(amount*(leverage if is_futures else 1))/price
    loss = (price-sl_val)*(amount*(leverage if is_futures else 1))/price

    lines += [
        f"Take-Profit: ${tp_val:.2f} | Stop-Loss: ${sl_val:.2f}",
        f"Expected Profit (USD): +${profit:.2f} | Expected Loss (USD): −${abs(loss):.2f}",
        ""
    ]

    # Detailed explanations
    lines.append("Indicators & Explanations:")
    lines.append(
        f"- **RSI ({ind.get('rsi', float('nan')):.2f}):** {'oversold' if ind.get('rsi') < 30 else 'overbought' if ind.get('rsi') > 70 else 'neutral'}")
    lines.append(f"- **MACD ({ind.get('macd', {}).get('crossover', 'N/A')}):** {'bullish momentum' if ind.get('macd', {}).get('crossover') == 'bullish' else 'bearish momentum' if ind.get('macd', {}).get('crossover') == 'bearish' else 'neutral'}")
    lines.append(
        f"- **Bollinger Bands:** {ind.get('bollinger', {}).get('breakout', 'inside')}")
    lines.append(f"- **ADX:** {ind.get('adx', 0.0):.2f}")
    lines.append("")

    # Breakdown
    lines.append("Categories:")
    for cat, pct in breakdown.items():
        lines.append(f"- {cat}: {pct:.1f}%")
    lines.append("")

    # Warnings & missing
    if missing or sentiment.get("warnings"):
        lines.append("⚠️ Warnings & Missing Indicators:")
        for m in missing:
            lines.append(f"- {m}: missing (penalty applied)")
        for w in sentiment.get("warnings", []):
            lines.append(f"- {w}")
        lines.append("")

    # Final verdict
    if action in ("GO LONG", "Bullish"):
        verdict = f"🔍 Final Verdict: {action} ({int(conf)}% confidence)"
    elif action in ("GO SHORT", "Bearish"):
        verdict = f"🔍 Final Verdict: {action} ({int(conf)}% confidence)"
    else:
        verdict = "🔍 Final Verdict: HOLD (Consider very-short trade)"
    lines.append(verdict)
    lines.append("")

    # Summary block
    lines.append("---")
    if is_futures:
        lines.append(
            f"### Summary (Futures, {int(leverage)}×, {risk.capitalize()} Risk)")
    else:
        lines.append(
            f"### Summary (Spot, {ttype.capitalize()}, {risk.capitalize()} Risk)")
    lines.append("")
    lines.append(f"**Reliability Rating:** {int(conf)} / 100")
    lines.append("")
    if action in ("GO LONG", "Bullish"):
        lines.append(
            "• Recommendation: Enter long position as per above parameters.")
    elif action in ("GO SHORT", "Bearish"):
        lines.append(
            "• Recommendation: Enter short position as per above parameters.")
    else:
        lines.append(
            "• Recommendation: No clear signal—consider a very-short (15m) scalp.")
    lines.append("")

    return "\n".join(lines)
