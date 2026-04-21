# Crypto Predictor CLI

Crypto Predictor CLI is a terminal-based market analyst for Binance spot and futures markets. It pulls live market data, calculates technical indicators, mixes in sentiment signals, scores each setup with rule-based logic, and returns a readable trade recommendation with confidence, take-profit, stop-loss, and optional PDF reporting.

Although the architecture could be adapted into a "Stock Analyst" later, the current implementation is crypto-focused and built around Binance market endpoints plus crypto sentiment sources.

## What This Project Does

The app acts like a lightweight research assistant for traders:

- analyzes a single coin in spot mode
- analyzes a single coin in futures mode
- scans multiple coins and selects the stronger market opportunity
- generates PDF reports for single-coin and multi-coin analysis
- emails generated reports
- includes backtesting utilities for score and PnL exploration

The project is rule-based, not machine-learning-based. Its recommendations come from transparent scoring logic that combines technical indicators, market structure, sentiment, and futures-specific signals.

## Core Workflow

1. The user launches the CLI from `main.py`.
2. The app fetches OHLCV candles from Binance.
3. Technical indicators are calculated from recent price and volume history.
4. Sentiment data is collected from Fear & Greed and CryptoPanic.
5. A decision engine converts the signals into a score and confidence level.
6. The CLI prints a recommendation such as `Bullish`, `Bearish`, `Neutral`, `GO LONG`, `GO SHORT`, or `HOLD`.
7. The result can be exported to PDF and optionally emailed.

## Key Features

- Spot market analysis for `scalping`, `short-term`, and `long-term` views
- Futures market analysis with leverage-aware recommendations
- Auto-triggered very-short futures check when a futures signal is too weak
- Multi-coin comparison across spot and futures setups
- Confidence scoring with category breakdown
- PDF report generation for single and multi-coin runs
- Email delivery for generated reports
- Backtesting scripts for score behavior and cumulative return analysis

## Important Libraries In Use

These are the main libraries actively used by the codebase:

- `requests` for API calls
- `pandas` for OHLCV data handling
- `pandas_ta` for technical indicators
- `numpy` for numeric support
- `reportlab` for PDF report generation
- `matplotlib` for backtesting charts
- `pytest` for tests

## Tech Notes About Dependencies

There are a few dependency mismatches worth knowing before setup:

- `requirements.txt` lists `fpdf`, but the code currently uses `reportlab`
- `python-dotenv` is listed, but the app does not currently call `load_dotenv()`
- `python-binance`, `websockets`, `asyncio`, and `ta` appear in `requirements.txt`, but they are not central to the current implementation

If you are setting the project up from scratch, make sure `reportlab` and `pytest` are installed even if they are missing from `requirements.txt`.

## Project Structure

```text
crypto_predictor/
├── main.py
├── requirements.txt
├── services/
│   ├── binance_api.py
│   ├── confidence_engine.py
│   ├── config.py
│   ├── decision_engine.py
│   ├── email_sender.py
│   ├── http_client.py
│   ├── indicators.py
│   ├── multi_analysis.py
│   ├── report_generator.py
│   ├── sentiment_api.py
│   └── social_api.py
├── scripts/
│   ├── backtest_pnl.py
│   └── backtest_scores.py
├── tests/
├── reports/
└── output/
```

## Main Modules

### `main.py`

Entry point for the terminal app. Presents the menu and routes the user into:

- spot analysis
- futures analysis
- multi-coin analysis

### `services/binance_api.py`

Handles Binance API integration:

- spot and futures OHLCV retrieval
- funding rate lookup
- open interest lookup
- leverage bracket lookup
- simple cache fallback behavior

### `services/indicators.py`

Builds the technical analysis layer using `pandas_ta`:

- RSI
- MACD
- Bollinger Bands
- ADX
- ATR
- EMA crossover
- OBV-based volume divergence
- pivot support and resistance
- Fibonacci level reference

### `services/sentiment_api.py`

Builds the sentiment snapshot using:

- Fear & Greed Index
- CryptoPanic news sentiment
- futures metrics when relevant

### `services/decision_engine.py`

The main rule engine. It:

- scores bullish and bearish signals
- applies penalties for missing indicators
- calculates confidence
- converts score into probability
- generates the final recommendation text

### `services/multi_analysis.py`

Runs spot and futures analysis for several symbols, compares both sides, and chooses the stronger market for each coin.

### `services/report_generator.py`

Creates PDF summaries for:

- a single coin analysis
- a multi-coin comparison run

## Installation

### 1. Create and activate a virtual environment

```bash
python3 -m venv venv
source venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
pip install reportlab pytest
```

## Configuration

The code expects these environment variables:

- `BINANCE_API_KEY`
- `BINANCE_API_SECRET`
- `CRYPTOPANIC_API_KEY`
- `DEFAULT_EMAIL`

Example shell setup:

```bash
export BINANCE_API_KEY="your_binance_key"
export BINANCE_API_SECRET="your_binance_secret"
export CRYPTOPANIC_API_KEY="your_cryptopanic_key"
export DEFAULT_EMAIL="you@example.com"
```

### Important Configuration Caveat

There is a `.env` file in the project, but the current codebase does not automatically load it with `python-dotenv`. That means environment variables should be exported in the shell before running the app, unless you update the startup flow to load `.env`.

### Email Sending Caveat

`services/email_sender.py` currently contains hardcoded sender credentials. That is not safe for production or public repos. A better next step is to move email settings into environment variables before wider use.

## Running the CLI

Start the app with:

```bash
python main.py
```

You will see a menu like:

```text
1. Spot Market
2. Futures Market
3. Multi-Coin Analysis
4. Quit
```

## Analysis Modes

### Spot Market

The user provides:

- symbol
- amount in USDT
- trade type: `scalping`, `short-term`, or `long-term`
- risk profile: `low`, `medium`, `high`, or `ignore`

The engine then:

- fetches candles from Binance spot
- calculates indicators
- fetches sentiment
- generates a recommendation
- optionally creates a PDF and emails it

### Futures Market

The user provides:

- symbol
- amount in USDT
- leverage
- risk profile

The engine then:

- fetches futures candles
- calculates indicators
- adds funding rate and open interest context
- produces `GO LONG`, `GO SHORT`, or `HOLD`
- optionally creates a PDF and emails it

If the signal is weak and returns `HOLD`, the app automatically runs a very-short futures analysis on a 15-minute view.

### Multi-Coin Analysis

This mode can:

- fetch the top 5 spot coins by volume
- accept a custom coin list

For each symbol, it compares:

- best spot strategy
- futures setup

It then chooses the stronger market for each coin, prints a comparison table, and generates a combined PDF report.

## Output and Artifacts

### `reports/`

Stores generated PDF reports for:

- single coin analysis
- multi-coin analysis

### `output/`

Stores charts created by backtesting scripts.

### `services/cache.json` and related cache files

Used as lightweight persistent caches for:

- Binance fallback values
- CryptoPanic sentiment
- other fetched metrics

## Backtesting Scripts

### Score distribution backtest

```bash
python scripts/backtest_scores.py
```

This script loops through multiple symbols and timeframes, scores historical candles, and saves histogram charts of score distributions.

### PnL-style backtest

```bash
python scripts/backtest_pnl.py
```

This script applies threshold-based position logic to historical scores and plots cumulative returns for a chosen symbol and trade type.

## Testing

Run tests with:

```bash
PYTHONPATH=. ./venv/bin/pytest -q
```

### Current Test Status

The repository includes useful tests, but some are currently out of sync with the latest function signatures and behavior. In the current state, several tests fail because:

- some tests reference older parameter names
- one test references a missing `services.coinstats_api` module
- some assertions expect output text that the current code no longer emits

So the test suite is present and valuable, but it needs cleanup before it can be treated as a green baseline.

## Known Limitations

- The project is crypto-only today and tied mainly to Binance endpoints.
- Sentiment is only partially implemented; `social_score` is currently a placeholder.
- The app is rule-based, not predictive AI or machine learning.
- `.env` is not auto-loaded yet.
- Email credentials are hardcoded in source code and should be moved to environment variables.
- Dependency declarations do not fully match runtime imports.

## Good Use Cases

- quickly checking a crypto setup from the terminal
- comparing spot versus futures opportunities
- generating client-style PDF reports
- experimenting with rule-based trade scoring
- using the codebase as a starting point for a broader market analyst tool

## Future Improvement Ideas

- add proper `.env` loading
- move all secrets to environment variables
- clean and update the test suite
- align `requirements.txt` with actual runtime dependencies
- add real social sentiment sources instead of placeholder values
- extend the engine to stocks, ETFs, or forex with a market-agnostic data layer

## Summary

Crypto Predictor CLI is a practical, modular trading analysis project that combines market data, technical indicators, sentiment inputs, and reporting into one terminal workflow. Its strongest quality is its clean separation of responsibilities across services, which makes it a solid foundation for a more polished crypto analyst or future stock analyst platform.
