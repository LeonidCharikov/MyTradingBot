"""
analyzer_new.py - Nová logika založená na likviditě a S/R (SMC approach)
Zaměřeno na M1-M5 exspirace.
"""
import pandas as pd
import numpy as np
from datetime import datetime

def detect_levels(df, window=10):
    """Najde lokální maxima a minima (S/R úrovně)"""
    df = df.copy()
    df['high_level'] = df['high'].rolling(window=window, center=True).max()
    df['low_level'] = df['low'].rolling(window=window, center=True).min()
    
    levels = {
        "resistance": df['high_level'].unique()[-5:].tolist(),
        "support": df['low_level'].unique()[-5:].tolist()
    }
    return levels

def detect_liquidity_zones(df_15m):
    """
    Identifikuje oblasti, kde se hromadí likvidita 
    (významná High a Low, nad kterými jsou stop-lossy)
    """
    highs = df_15m['high'].tail(20)
    lows = df_15m['low'].tail(20)
    
    return {
        "buy_side_liquidity": highs.max(), # Nad tímto high jsou Short SL
        "sell_side_liquidity": lows.min()   # Pod tímto low jsou Long SL
    }

def check_liquidity_sweep(df_5m, liquidity_zones):
    """
    Hledá 'Liquidity Sweep' - cena píchne nad/pod zónu a vrátí se.
    To je nejsilnější signál pro 5min obrat.
    """
    last_candle = df_5m.iloc[-1]
    prev_candle = df_5m.iloc[-2]
    
    bsl = liquidity_zones["buy_side_liquidity"]
    ssl = liquidity_zones["sell_side_liquidity"]
    
    # Bearish Sweep (Vymetení likvidity nahoře -> SHORT)
    if prev_candle['high'] > bsl and last_candle['close'] < bsl:
        return "SHORT", "Liquidity Sweep High (BULL TRAP)"
    
    # Bullish Sweep (Vymetení likvidity dole -> LONG)
    if prev_candle['low'] < ssl and last_candle['close'] > ssl:
        return "LONG", "Liquidity Sweep Low (BEAR TRAP)"
    
    return None, None

def analyze_new_logic(market_data):
    df_h1 = market_data['1h']
    df_15m = market_data['15m']
    df_5m = market_data['5m']
    
    h1_trend = "UP" if df_h1['close'].iloc[-1] > df_h1['close'].iloc[-10] else "DOWN"
    levels_15m = detect_levels(df_15m)
    liq_zones = detect_liquidity_zones(df_15m)
    
    # Detekce signálu
    signal, reason = check_liquidity_sweep(df_5m, liq_zones)
    
    # Základní data, která posíláme VŽDY (i když není signál)
    common_data = {
        "trend_daily": h1_trend,
        "trend_1h": h1_trend,
        "session_note": "SMC Logic",
        "atr_reason": "OK",
        "level_found": True, # SMC vždy najde nějakou likviditu
        "source": market_data.get("source", "twelvedata")
    }

    if not signal:
        # Tady zkusíme ještě odraz od S/R
        last_close = df_5m['close'].iloc[-1]
        for res in levels_15m["resistance"]:
            if 0 < (res - last_close) < (market_data['atr_5m'] * 0.5):
                signal, reason = "SHORT", "Odraz od Resistance"
        for sup in levels_15m["support"]:
            if 0 < (last_close - sup) < (market_data['atr_5m'] * 0.5):
                signal, reason = "LONG", "Odraz od Support"

    # Pokud ani po S/R není signál, vrátíme vysvětlení
    if not signal:
        res_data = common_data.copy()
        res_data.update({"note": "Cena je uprostřed pásma (mimo likviditu)"})
        return None, res_data

    # Pokud signál JE, sestavíme plný checklist
    entry_time = datetime.now()
    splneno = 3 if "Sweep" in reason else 2
    
    res_data = common_data.copy()
    res_data.update({
        "model": f"SMC_{reason}",
        "signal_strength": "SILNY" if splneno >= 3 else "STREDNI",
        "level_price": liq_zones["buy_side_liquidity"] if signal == "SHORT" else liq_zones["sell_side_liquidity"],
        "level_kind": "Liquidity Pool",
        "splneno": splneno,
        "celkem": 5,
        "entry_time": (entry_time + pd.Timedelta(minutes=5)).strftime("%H:%M"),
        "minutes_ahead": 5,
        "signal_generated_at": entry_time.strftime("%H:%M:%S"),
        "stop_note": "Likvidita vymetena"
    })
    
    return signal, res_data