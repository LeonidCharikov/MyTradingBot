import requests
import pandas as pd
import time
import config
import logging

# Logging do souboru
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("bot.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

BINANCE_INTERVALS = {
    "1day": "1d",
    "1h": "1h",
    "30min": "30m",
    "15min": "15m",
    "5min": "5m"
}

BINANCE_SYMBOLS = {
    "BTC/USD": "BTCUSDT",
    "ETH/USD": "ETHUSDT",
    "BNB/USD": "BNBUSDT",
    "SOL/USD": "SOLUSDT",
    "XRP/USD": "XRPUSDT",
    "ADA/USD": "ADAUSDT",
    "DOGE/USD": "DOGEUSDT",
    "DOT/USD": "DOTUSDT"
}

def notify_error(message):
    """Posle chybu na Telegram"""
    try:
        url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage"
        requests.post(url, json={
            "chat_id": config.TELEGRAM_CHAT_ID,
            "text": f"⚠️ <b>Chyba bota:</b>\n{message}",
            "parse_mode": "HTML"
        }, timeout=5)
    except Exception:
        pass

def get_candles_twelvedata(symbol, interval="1h", outputsize=50):
    url = "https://api.twelvedata.com/time_series"
    params = {
        "symbol": symbol,
        "interval": interval,
        "outputsize": outputsize,
        "apikey": config.TWELVEDATA_API_KEY
    }
    try:
        response = requests.get(url, params=params, timeout=10).json()
    except requests.exceptions.Timeout:
        msg = f"TwelveData timeout pro {symbol}"
        logger.error(msg)
        notify_error(msg)
        return None
    except Exception as e:
        msg = f"TwelveData chyba pro {symbol}: {e}"
        logger.error(msg)
        return None

    if "values" not in response:
        code = response.get("code", "?")
        msg = response.get("message", "Neznama chyba")

        if code == 429:
            err = f"TwelveData limit wycerpan pro {symbol}"
            logger.warning(err)
            notify_error(f"TwelveData limit wycerpan!\nSymbol: {symbol}\nPockej minutu.")
        elif code == 401:
            err = f"TwelveData neplatny API klic!"
            logger.error(err)
            notify_error(err)
        else:
            logger.warning(f"TwelveData {symbol}: {msg}")

        return None

    try:
        df = pd.DataFrame(response["values"])
        df["datetime"] = pd.to_datetime(df["datetime"])
        df = df.sort_values("datetime").reset_index(drop=True)
        for col in ["open", "high", "low", "close"]:
            df[col] = df[col].astype(float)
        logger.info(f"TwelveData OK: {symbol} {interval} ({len(df)} svicek)")
        return df
    except Exception as e:
        logger.error(f"Chyba parsovani TwelveData {symbol}: {e}")
        return None

def get_candles_binance(symbol, interval="1h", outputsize=50):
    binance_symbol = BINANCE_SYMBOLS.get(symbol)
    if not binance_symbol:
        binance_symbol = symbol.replace("/", "")
        if not binance_symbol.endswith("USDT"):
            binance_symbol = binance_symbol.replace("USD", "USDT")

    binance_interval = BINANCE_INTERVALS.get(interval, "1h")
    url = "https://api.binance.com/api/v3/klines"
    params = {
        "symbol": binance_symbol,
        "interval": binance_interval,
        "limit": outputsize
    }

    try:
        response = requests.get(url, params=params, timeout=10).json()
    except requests.exceptions.Timeout:
        msg = f"Binance timeout pro {symbol}"
        logger.error(msg)
        notify_error(msg)
        return None
    except Exception as e:
        logger.error(f"Binance chyba pro {symbol}: {e}")
        return None

    if isinstance(response, dict) and "code" in response:
        msg = f"Binance chyba {symbol}: {response.get('msg','?')}"
        logger.warning(msg)
        return None

    if not response:
        logger.warning(f"Binance prazdna odpoved pro {symbol}")
        return None

    try:
        df = pd.DataFrame(response, columns=[
            "datetime", "open", "high", "low", "close",
            "volume", "close_time", "quote_volume", "trades",
            "taker_buy_base", "taker_buy_quote", "ignore"
        ])
        df["datetime"] = pd.to_datetime(df["datetime"], unit="ms")
        df = df[["datetime", "open", "high", "low", "close"]].copy()
        for col in ["open", "high", "low", "close"]:
            df[col] = df[col].astype(float)
        df = df.sort_values("datetime").reset_index(drop=True)
        logger.info(f"Binance OK: {symbol} {interval} ({len(df)} svicek)")
        return df
    except Exception as e:
        logger.error(f"Chyba parsovani Binance {symbol}: {e}")
        return None

def is_crypto(symbol):
    crypto_symbols = list(BINANCE_SYMBOLS.keys()) + [
        "BTC", "ETH", "BNB", "SOL", "XRP", "ADA", "DOGE"
    ]
    return any(symbol.startswith(s.split("/")[0]) for s in crypto_symbols)

def calculate_atr(df, period=14):
    if df is None or len(df) < period:
        return None
    high = df["high"]
    low = df["low"]
    close = df["close"]
    tr1 = high - low
    tr2 = abs(high - close.shift(1))
    tr3 = abs(low - close.shift(1))
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.rolling(period).mean()

def get_market_data(symbol):
    logger.info(f"Stahuji data: {symbol}")

    if is_crypto(symbol):
        df_daily = get_candles_binance(symbol, interval="1day", outputsize=20)
        df_1h = get_candles_binance(symbol, interval="1h", outputsize=50)
    else:
        df_daily = get_candles_twelvedata(symbol, interval="1day", outputsize=20)
        time.sleep(8)
        df_1h = get_candles_twelvedata(symbol, interval="1h", outputsize=50)
        time.sleep(8)

    if df_daily is None or df_1h is None:
        logger.warning(f"Chybi data pro {symbol}")
        return None

    atr_daily_series = calculate_atr(df_daily)
    atr_1h_series = calculate_atr(df_1h)

    if atr_daily_series is None or atr_1h_series is None:
        logger.warning(f"Nelze vypocitat ATR pro {symbol}")
        return None

    return {
        "symbol": symbol,
        "daily": df_daily,
        "1h": df_1h,
        "atr_daily": round(atr_daily_series.iloc[-1], 5),
        "atr_1h": round(atr_1h_series.iloc[-1], 5),
        "last_close": df_1h["close"].iloc[-1],
        "last_high": df_1h["high"].iloc[-1],
        "last_low": df_1h["low"].iloc[-1],
        "source": "binance" if is_crypto(symbol) else "twelvedata"
    }