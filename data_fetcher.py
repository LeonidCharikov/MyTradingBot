"""
data_fetcher.py - Stahování tržních dat

Zdroje:
- TwelveData: Forex, Komodity (limit 8 req/min na free tier)
- Binance: Krypto (bez limitu, bez API klice)

Cache: Pri opakovane analyze stejneho symbolu pouzije
ulozena data (max 5 minut stara) misto znovu stahovat.
"""

import requests
import pandas as pd
import time
import config
import logging
from datetime import datetime, timedelta

# Logging do souboru i konzole
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("bot.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Cache pro opakovane analyzy
# Format: { symbol: { "data": market_data, "time": datetime } }
_data_cache = {}

BINANCE_INTERVALS = {
    "1day": "1d",
    "1h":   "1h",
    "30min": "30m",
    "15min": "15m",
    "5min":  "5m"
}

BINANCE_SYMBOLS = {
    "BTC/USD":  "BTCUSDT",
    "ETH/USD":  "ETHUSDT",
    "BNB/USD":  "BNBUSDT",
    "SOL/USD":  "SOLUSDT",
    "XRP/USD":  "XRPUSDT",
    "ADA/USD":  "ADAUSDT",
    "DOGE/USD": "DOGEUSDT",
    "DOT/USD":  "DOTUSDT"
}


def notify_error(message):
    """Posle chybovou zpravu na Telegram"""
    try:
        url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage"
        requests.post(url, json={
            "chat_id": config.TELEGRAM_CHAT_ID,
            "text": f"⚠️ <b>Chyba:</b>\n{message}",
            "parse_mode": "HTML"
        }, timeout=5)
    except Exception:
        pass


def get_candles_twelvedata(symbol, interval="1h", outputsize=50):
    """Stahuje OHLCV data z TwelveData API"""
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
        msg = f"TwelveData timeout: {symbol}"
        logger.error(msg)
        notify_error(msg)
        return None
    except Exception as e:
        logger.error(f"TwelveData chyba {symbol}: {e}")
        return None

    if "values" not in response:
        code = response.get("code", "?")
        msg = response.get("message", "Neznama chyba")
        if code == 429:
            notify_error(f"TwelveData limit! Symbol: {symbol}\nPockej minutu.")
        elif code == 401:
            notify_error("TwelveData: neplatny API klic!")
        else:
            logger.warning(f"TwelveData {symbol}: {msg}")
        return None

    try:
        df = pd.DataFrame(response["values"])
        df["datetime"] = pd.to_datetime(df["datetime"])
        df = df.sort_values("datetime").reset_index(drop=True)
        for col in ["open", "high", "low", "close"]:
            df[col] = df[col].astype(float)
        logger.info(f"TwelveData: {symbol} {interval} ({len(df)} svicek)")
        return df
    except Exception as e:
        logger.error(f"Chyba parsovani TwelveData {symbol}: {e}")
        return None


def get_candles_binance(symbol, interval="1h", outputsize=50):
    """Stahuje OHLCV data z Binance API (bez API klice)"""
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
        msg = f"Binance timeout: {symbol}"
        logger.error(msg)
        notify_error(msg)
        return None
    except Exception as e:
        logger.error(f"Binance chyba {symbol}: {e}")
        return None

    if isinstance(response, dict) and "code" in response:
        logger.warning(f"Binance {symbol}: {response.get('msg','?')}")
        return None

    if not response:
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
        logger.info(f"Binance: {symbol} {interval} ({len(df)} svicek)")
        return df
    except Exception as e:
        logger.error(f"Chyba parsovani Binance {symbol}: {e}")
        return None


def is_crypto(symbol):
    """Zjisti zda je symbol krypto (pouzit Binance)"""
    crypto_bases = [s.split("/")[0] for s in BINANCE_SYMBOLS.keys()]
    return any(symbol.startswith(base) for base in crypto_bases)


def calculate_atr(df, period=14):
    """Vypocita Average True Range"""
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


def _fetch_all_data(symbol):
    """
    Stahne vsechna data pro dany symbol (D1, 1H, 15M, 5M).
    Vraci None pokud stazeni selhalo.
    """
    if is_crypto(symbol):
        # Binance - bez rate limitu
        df_daily = get_candles_binance(symbol, "1day", outputsize=20)
        df_1h    = get_candles_binance(symbol, "1h",   outputsize=50)
        df_15m   = get_candles_binance(symbol, "15min", outputsize=50)
        df_5m    = get_candles_binance(symbol, "5min",  outputsize=30)
    else:
        # TwelveData - s rate limitem (8 req/min)
        df_daily = get_candles_twelvedata(symbol, "1day",  outputsize=20)
        time.sleep(8)
        df_1h    = get_candles_twelvedata(symbol, "1h",    outputsize=50)
        time.sleep(8)
        df_15m   = get_candles_twelvedata(symbol, "15min", outputsize=50)
        time.sleep(8)
        df_5m    = get_candles_twelvedata(symbol, "5min",  outputsize=30)
        time.sleep(8)

    if df_daily is None or df_1h is None:
        logger.warning(f"Chybi zakladni data pro {symbol}")
        return None

    # Vypocet ATR pro vsechny timeframy
    atr_d = calculate_atr(df_daily)
    atr_1h = calculate_atr(df_1h)
    atr_15m = calculate_atr(df_15m) if df_15m is not None else None
    atr_5m  = calculate_atr(df_5m)  if df_5m  is not None else None

    atr_d_last = atr_d.dropna().iloc[-1] if atr_d is not None and not atr_d.dropna().empty else None
    atr_1h_last = atr_1h.dropna().iloc[-1] if atr_1h is not None and not atr_1h.dropna().empty else None
    atr_15m_last = atr_15m.dropna().iloc[-1] if atr_15m is not None and not atr_15m.dropna().empty else None
    atr_5m_last = atr_5m.dropna().iloc[-1] if atr_5m is not None and not atr_5m.dropna().empty else None

    if atr_d_last is None or atr_1h_last is None:
        logger.warning(f"Nelze vypocitat ATR pro {symbol}")
        return None

    return {
        "symbol":   symbol,
        "daily":    df_daily,
        "1h":       df_1h,
        "15m":      df_15m,
        "5m":       df_5m,
        "atr_daily": round(atr_d_last, 5),
        "atr_1h":    round(atr_1h_last, 5),
        "atr_15m":   round(atr_15m_last, 5) if atr_15m_last is not None else None,
        "atr_5m":    round(atr_5m_last, 5)  if atr_5m_last is not None else None,
        "last_close": df_1h["close"].iloc[-1],
        "last_high":  df_1h["high"].iloc[-1],
        "last_low":   df_1h["low"].iloc[-1],
        "source":    "binance" if is_crypto(symbol) else "twelvedata",
        "fetched_at": datetime.now()
    }


def _fetch_fast_update(symbol, cached_data):
    """
    Rychla aktualizace pro opakovane analyzy stejneho symbolu.
    Stahne jen 5M a 15M data (minuty, ne hodiny).
    D1 a 1H pouzije z cache (jsou stale platne).
    """
    logger.info(f"Rychla aktualizace: {symbol}")

    if is_crypto(symbol):
        df_15m = get_candles_binance(symbol, "15min", outputsize=20)
        df_5m  = get_candles_binance(symbol, "5min",  outputsize=20)
    else:
        df_15m = get_candles_twelvedata(symbol, "15min", outputsize=20)
        time.sleep(8)
        df_5m  = get_candles_twelvedata(symbol, "5min",  outputsize=20)

    if df_5m is None and df_15m is None:
        return cached_data   # Vrat stara data pokud stazeni selhalo

    # Aktualizuj jen kratke timeframy, zbytek zachovej
    updated = dict(cached_data)
    if df_15m is not None:
        atr_15m = calculate_atr(df_15m)
        updated["15m"] = df_15m
        updated["atr_15m"] = round(atr_15m.iloc[-1], 5) if atr_15m is not None else updated.get("atr_15m")
    if df_5m is not None:
        atr_5m = calculate_atr(df_5m)
        updated["5m"] = df_5m
        updated["atr_5m"] = round(atr_5m.iloc[-1], 5) if atr_5m is not None else updated.get("atr_5m")
        updated["last_close"] = df_5m["close"].iloc[-1]
    updated["fetched_at"] = datetime.now()

    return updated


def get_market_data(symbol, force_refresh=False):
    """
    Hlavni funkce pro ziskani dat.

    Logika cache:
    - 1. analyza: stahne vsechno (D1, 1H, 15M, 5M)
    - Opakovana analyza do 5 min: jen aktualizuje 5M a 15M
    - Po 5 minutach: stahne vse znovu
    - force_refresh=True: vzdycky stahne vse
    """
    global _data_cache

    cache_max_age = timedelta(minutes=config.CACHE_FAST_MINUTES)
    cached = _data_cache.get(symbol)

    if not force_refresh and cached is not None:
        age = datetime.now() - cached.get("fetched_at", datetime.min)
        if age < cache_max_age:
            # Cache je cerstva - jen rychla aktualizace 5M/15M
            logger.info(f"Cache hit {symbol} (vek: {int(age.total_seconds())}s) - rychla aktualizace")
            updated = _fetch_fast_update(symbol, cached)
            _data_cache[symbol] = updated
            return updated
        else:
            logger.info(f"Cache expirovala pro {symbol} - stahuji vse")

    # Plne stazeni
    data = _fetch_all_data(symbol)
    if data:
        _data_cache[symbol] = data

    return data


def clear_cache(symbol=None):
    """Vymaze cache - pro reset nebo debugging"""
    global _data_cache
    if symbol:
        _data_cache.pop(symbol, None)
        logger.info(f"Cache vycistena pro {symbol}")
    else:
        _data_cache.clear()
        logger.info("Cache kompletne vycistena")