import logging
import math
from typing import Dict, List, Optional

from services.binance_api import get_ohlcv
from services.indicators import analyze_indicators
from services.sentiment_api import get_combined_sentiment
from services.multi_analysis import multi_coin_analysis, fetch_top5_spot
from services.decision_engine import generate_recommendation
from services.config import TP_PCT, SL_PCT

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# Globals to carry over from Futures → Very-Short
_last_futures_amount: Optional[float] = None
_last_futures_leverage: Optional[float] = None
_last_futures_risk: Optional[str] = None


def prompt_choice(prompt: str, options: Dict[str, str]) -> str:
    print(f"{prompt}")
    for key, label in options.items():
        print(f"{key}. {label}")
    return options.get(input("> ").strip(), "")


def run_spot():
    symbol = input("Symbol (e.g., ETH): ").strip().upper()
    try:
        amount = float(input("Amount (USDT): ").strip())
    except ValueError:
        print("Invalid amount.")
        return

    trade_opts = {"1": "scalping", "2": "short-term", "3": "long-term"}
    ttype = prompt_choice("Choose Trade Type:", trade_opts)
    if ttype not in trade_opts.values():
        print("Invalid type.")
        return

    risk_opts = {"1": "low", "2": "medium", "3": "high", "4": "ignore"}
    risk = prompt_choice("Select Risk Type:", risk_opts)
    if risk not in risk_opts.values():
        print("Invalid risk.")
        return

    df = get_ohlcv(symbol, ttype, False)
    if df is None or df.empty:
        print("No data.")
        return

    ind = analyze_indicators(df, ttype)
    sentiment = get_combined_sentiment(symbol, False)
    output = generate_recommendation(
        symbol, amount, ttype, risk, ind, sentiment, df)
    print(output)

    choice = input("\ny-Generate PDF, r-Restart, q-Menu\n> ").strip().lower()
    if choice == "y":
        from services.report_generator import generate_pdf_report
        path = generate_pdf_report(symbol, ttype, output, df)
        if path:
            print(f"✅ PDF: {path}")
            from services.email_sender import send_email_report, SENDER_EMAIL
            print("1-default email 2-custom")
            sel = input("> ").strip()
            to = input("Email: ").strip() if sel == "2" else SENDER_EMAIL
            try:
                send_email_report(to, path)
            except Exception as e:
                log.error(e)
                print("Email error")
    elif choice == "r":
        return run_spot()


def run_futures():
    global _last_futures_amount, _last_futures_leverage, _last_futures_risk

    symbol = input("Futures Symbol (e.g., ETH): ").strip().upper()
    try:
        amount = float(input("Amount (USDT): ").strip())
    except ValueError:
        print("Invalid amount.")
        return
    _last_futures_amount = amount

    try:
        lev = float(input("Leverage (1–10): ").strip())
        if not (1.0 <= lev <= 10.0):
            raise ValueError
    except ValueError:
        print("Invalid leverage; defaulting to 1×.")
        lev = 1.0
    _last_futures_leverage = lev

    risk_opts = {"1": "low", "2": "medium", "3": "high", "4": "ignore"}
    risk = prompt_choice("Select Risk Type:", risk_opts)
    if risk not in risk_opts.values():
        print("Invalid risk.")
        return
    _last_futures_risk = risk

    df = get_ohlcv(symbol, "futures", True)
    if df is None or df.empty:
        print("No data.")
        return

    ind = analyze_indicators(df, "futures")
    sentiment = get_combined_sentiment(symbol, True)
    output = generate_recommendation(
        symbol, amount, "futures", risk, ind, sentiment, df, True, lev
    )
    print(output)

    # If HOLD, immediately trigger Very-Short Futures
    if "HOLD" in output:
        print("\n💡 HOLD detected—running Very-Short (15m) futures analysis...\n")
        run_very_short_futures(symbol)
        return

    choice = input("\ny-Generate PDF, r-Restart, q-Menu\n> ").strip().lower()
    if choice == "y":
        from services.report_generator import generate_pdf_report
        path = generate_pdf_report(symbol, "futures", output, df)
        if path:
            print(f"✅ PDF: {path}")
            from services.email_sender import send_email_report, SENDER_EMAIL
            print("1-default email 2-custom")
            sel = input("> ").strip()
            to = input("Email: ").strip() if sel == "2" else SENDER_EMAIL
            try:
                send_email_report(to, path)
            except Exception as e:
                log.error(e)
                print("Email error")
    elif choice == "r":
        return run_futures()


def run_very_short_futures(symbol: str):
    """
    Very-Short-Term futures analysis (15m) using last amount, leverage, and risk.
    """
    if not all([_last_futures_amount, _last_futures_leverage, _last_futures_risk]):
        print("Missing prior futures parameters.")
        return

    ttype = "very-short"
    df = get_ohlcv(symbol, ttype, True)
    if df is None or df.empty:
        print("No 15m futures data.")
        return

    ind = analyze_indicators(df, ttype)
    sentiment = get_combined_sentiment(symbol, True)
    output = generate_recommendation(
        symbol,
        _last_futures_amount,
        ttype,
        _last_futures_risk,
        ind,
        sentiment,
        df,
        True,
        _last_futures_leverage
    )
    print(output)

    # No PDF/email in this quick trigger; just return to main menu.
    input("Press Enter to return to main menu.")


def run_multi():
    pick = prompt_choice(
        "Select mode for Multi-Coin Analysis:",
        {"1": "Top 5 by volume", "2": "Custom list"}
    )
    if pick == "Top 5 by volume":
        print("\nFetching top 5 coins by 24h volume … ")
        symbols = fetch_top5_spot()
        print(f" → Top 5: {', '.join(symbols)}\n")
    else:
        raw = input(
            "\nEnter symbols separated by comma (e.g. BTC,ETH,SOL): "
        )
        symbols = [s.strip().upper() for s in raw.split(",") if s.strip()]

    if not symbols:
        print("No symbols provided.")
        return

    try:
        amount = float(input("Amount (USDT) for each coin: ").strip())
    except ValueError:
        print("Invalid amount.")
        return

    try:
        lev = float(input("Leverage (1–10) for futures: ").strip())
        if not (1.0 <= lev <= 10.0):
            raise ValueError
    except ValueError:
        print("Invalid leverage; defaulting to 1.0×.")
        lev = 1.0

    print(f"\nRunning analysis (Risk = Medium) for: {', '.join(symbols)}\n")
    results = multi_coin_analysis(symbols, amount, leverage=lev)

    header = (
        "Coin | Market            | Score | Conf |   Price    |    TP      |    SL      |  P(Up)/P(Down)"
    )
    print("—" * len(header))
    print(header)
    print("—" * len(header))

    flat, summaries = [], []
    for sym in symbols:
        row = results.get(sym, {})
        chosen = row.get("chosen_market")
        info = row.get(chosen, {})
        score = info.get("score", 0) or 0
        conf = info.get("confidence", 0.0) or 0.0

        if chosen == "spot":
            strat = row["spot"]["strategy"] or "scalping"
            df_spot = get_ohlcv(sym, strat, False)
            ind_spot = analyze_indicators(
                df_spot, strat) if df_spot is not None else {}
            price = ind_spot.get(
                "price", df_spot["close"].iloc[-1]) if df_spot is not None else 0.0
            tp = price * (1 + TP_PCT["medium"]["spot"])
            sl = price * (1 - SL_PCT["medium"]["spot"])
            full_txt = generate_recommendation(
                sym, amount, strat, "medium", ind_spot,
                get_combined_sentiment(sym, False), df_spot
            )
            market_str = f"Spot ({strat.capitalize()})"
        else:
            df_fut = get_ohlcv(sym, "futures", True)
            ind_fut = analyze_indicators(
                df_fut, "futures") if df_fut is not None else {}
            price = ind_fut.get(
                "price", df_fut["close"].iloc[-1]) if df_fut is not None else 0.0
            tp = price * (1 + TP_PCT["medium"]["futures"])
            sl = price * (1 - SL_PCT["medium"]["futures"])
            full_txt = generate_recommendation(
                sym, amount, "futures", "medium", ind_fut,
                get_combined_sentiment(sym, True), df_fut, True, lev
            )
            market_str = "Futures"

        p_up = 1.0 / (1.0 + math.exp(-float(score) / 10.0))
        p_dn = 1.0 - p_up

        print(
            f"{sym:<4} | "
            f"{market_str:<18} | "
            f"{score:>4} | "
            f"{int(conf):>3}% | "
            f"{price:>9.2f}  | "
            f"{tp:>9.2f}  | "
            f"{sl:>9.2f}  | "
            f"{p_up*100:5.1f}%/{p_dn*100:4.1f}%"
        )

        flat.append({
            "coin": sym, "market": market_str,
            "score": score, "conf": conf,
            "price": price, "tp": tp, "sl": sl,
            "p_up": p_up*100, "p_down": p_dn*100
        })

        # extract summary block
        parts = full_txt.split("### Summary", 1)
        summary_section = parts[1].strip() if len(parts) == 2 else full_txt
        summaries.append(f"**{sym}**\n\n{summary_section}")

    from services.report_generator import generate_multi_pdf_report
    pdf_path = generate_multi_pdf_report(flat, summaries)
    if pdf_path:
        print(f"✅ PDF report saved to {pdf_path}\n")
        from services.email_sender import send_email_report, SENDER_EMAIL
        print("Send report via email:\n1. Send to default email\n2. Enter a custom email address")
        sel = input("> ").strip()
        to = input("Enter recipient email address: ").strip(
        ) if sel == "2" else SENDER_EMAIL
        try:
            send_email_report(to, pdf_path)
        except Exception as e:
            log.error(f"Failed to send email: {e}")
            print(f"⚠️ Could not send email: {e}")

    input("\nPress Enter to return to main menu.")


def main_menu():
    while True:
        print("\n🚀 Crypto Predictor CLI")
        print("1. Spot Market")
        print("2. Futures Market")
        print("3. Multi-Coin Analysis")
        print("4. Quit")
        choice = input("> ").strip()
        if choice == "1":
            run_spot()
        elif choice == "2":
            run_futures()
        elif choice == "3":
            run_multi()
        elif choice == "4":
            print("Goodbye!")
            break
        else:
            print("Invalid option. Please choose 1, 2, 3, or 4.")


if __name__ == "__main__":
    main_menu()
