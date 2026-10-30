# MyTradingBot

An experimental Python project for monitoring financial markets, performing
technical analysis, and sending trading signals through Telegram. The project
is not a trading platform and does not place orders with a broker.

> **IMPORTANT DISCLAIMER**
>
> This project is **experimental and educational**. Algorithm outputs are not
> investment recommendations, financial advice, or guarantees of profit. The
> code may contain bugs, incomplete models, and incorrect assumptions. Do not
> use it to make decisions involving real money or for live trading without
> thorough independent auditing, testing, and risk management. The author is
> not responsible for any losses or damages resulting from use of this project.

## What the Project Does

The bot runs as a simple loop that:

1. receives commands and callbacks from Telegram,
2. downloads market data for the selected symbol,
3. prepares data for the D1, 1H, 15M, and 5M timeframes,
4. calculates ATR and other supporting values,
5. selects one of two analysis engines,
6. evaluates conditions for a LONG or SHORT signal,
7. sends the result to Telegram, and
8. stores the signal and its later outcome in `trades.csv`.

The project only generates and records signals. It does not include broker
connectivity, order execution, account management, or performance guarantees.

## Main Features

- **Two analysis modes**
  - `new`: newer logic based on SMC, liquidity, levels, and short timeframes.
  - `old`: original logic with trend, level, bounce, breakout, and checklist
    detection.
- **Multiple data sources**
  - TwelveData for forex, commodities, and indices.
  - Binance API for supported cryptocurrencies without an API key.
- **Multiple timeframes**: daily data, 1H, 15M, and 5M.
- **ATR filters** for volatility estimation and distance checks.
- **Trend and time filters**, including London and New York sessions.
- **Correlation checks** for related pairs, channels, historical levels, and
  obstacles.
- **Protective limits** on daily signal counts and daily losses.
- **Market-data cache**: short timeframes are refreshed faster during repeated
  analysis, while older data is not unnecessarily downloaded again.
- **Telegram menus** for selecting forex, cryptocurrency, commodity, and index
  instruments.
- **CSV records** containing signals, models, signal strength, levels, stops,
  take-profit values, RRR, sessions, and outcomes.
- **Duplicate-signal prevention** for the same symbol within a short time
  window.

## Project Structure

```text
MyTradingBot/
├── main.py                 # Bot entry point, Telegram loop, and limits
├── config.py               # API, mode, and analysis configuration
├── data_fetcher.py         # Data download, normalization, ATR, and caching
├── analyzer.py             # Original analysis engine
├── analyzer_new.py         # Newer SMC/liquidity analysis engine
├── logic_selector.py       # Active analysis-engine selection
├── telegram_notifier.py    # Telegram messages, menus, and signal formatting
├── trade_logger.py         # Signal and statistics logging to CSV
├── trades.csv              # Local signal and outcome records
├── bot.log                 # Local runtime log
└── README.md               # Project documentation
```

## Requirements

- Python 3.10 or newer
- Internet access
- A Telegram bot for interactive control
- A TwelveData API key for forex, commodities, and indices
- No Binance account is required for public market data

Project dependencies:

```powershell
python -m pip install requests pandas numpy
```

## Configuration

Set local values in [config.py](./config.py). Never commit real tokens, API
keys, or Telegram IDs to the Git repository.

```python
TWELVEDATA_API_KEY = ""
TELEGRAM_BOT_TOKEN = ""
TELEGRAM_CHAT_ID = [""]

MODE = "demo"
ANALYSIS_METHOD = "new"
SCAN_INTERVAL = 60
INTERACTIVE_MODE = True
```

Important configuration groups:

- `MODE`, `ANALYSIS_METHOD`, and `SCAN_INTERVAL` control bot operation.
- `MAX_DAILY_LOSSES` and `MAX_TRADES_PER_DAY` limit daily activity.
- `SESSION_*` configures trading sessions and enables or disables session
  filtering.
- `EMA_*`, `ATR_*`, and `TREND_LOOKBACK_*` control trend and volatility
  filters.
- `BOUNCE_*`, `BREAKOUT_*`, and `LEVEL_*` control bounce, breakout, and level
  detection.
- `CHECKLIST_*` configures stop-loss, take-profit, and minimum RRR checks.

`MODE = "demo"` is recommended for development and testing. Even setting
`MODE = "real"` does not enable broker trading because this project contains
no broker connector.

## Running the Bot

After completing the configuration, run:

```powershell
python main.py
```

The bot then waits for Telegram commands. Basic commands include:

- `/menu` - show the main menu,
- `/status` - show the bot status,
- `/reset` - reset daily counters,
- `/logic_new` - switch to the newer analysis engine,
- `/logic_old` - switch to the original analysis engine.

## Data and Limits

Forex, commodities, and indices are retrieved through TwelveData, which may
enforce rate limits. Cryptocurrency symbols are retrieved through Binance's
public endpoints. If data is unavailable or invalid, no signal is generated;
details are written to `bot.log`.

`trades.csv` is a local runtime file containing signal history and outcomes.
Review it before sharing because it may contain personal notes or results.
`bot.log` may contain diagnostic information and should also be reviewed before
publication.

## Project Status

The project is under continuous experimentation and development. Analysis
models, thresholds, and data sources must be validated with independent data,
backtesting, and paper trading. This is not a finished production system.

## License and Responsibility

The project is provided without warranties. Review the licensing terms of
external data services and follow their usage limits. Use this code at your
own risk.
