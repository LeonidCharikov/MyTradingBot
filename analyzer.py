import config
from datetime import datetime, timedelta
import pandas as pd
import config as cfg

# ============================================================
# CAS VSTUPU
# ============================================================

def calculate_best_entry(now):
    seconds = now.second
    if seconds <= 20:
        close_in = 3
    elif seconds <= 40:
        close_in = 3
    else:
        close_in = 4
    close_time = now + timedelta(minutes=close_in)
    close_time = close_time.replace(second=0, microsecond=0)
    return close_time, close_in

# ============================================================
# ATR
# ============================================================

def get_atr(df, period=14):
    high = df["high"]
    low = df["low"]
    close = df["close"]
    tr1 = high - low
    tr2 = abs(high - close.shift(1))
    tr3 = abs(low - close.shift(1))
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.rolling(period).mean().iloc[-1]

def check_atr_filters(df_daily, atr_daily):
    last = df_daily.iloc[-1]
    daily_range = last["high"] - last["low"]
    open_price = last["open"]
    close_price = last["close"]

    if atr_daily == 0:
        return False, "ATR je nula"

    atr_used = daily_range / atr_daily
    if atr_used >= cfg.ATR_MAX_USED:
        return False, f"ATR pouzito {round(atr_used*100)}%"

    if abs(close_price - open_price) < atr_daily * cfg.ATR_OPEN_CLOSE_MIN:
        return False, "Cena u bodu otevreni"

    return True, f"ATR OK ({round(atr_used*100)}% pouzito)"

# ============================================================
# TREND
# ============================================================

def get_trend(df, lookback=5, sensitivity=0.35):
    closes = df["close"].tail(lookback).values
    highs = df["high"].tail(lookback).values
    lows = df["low"].tail(lookback).values
    last_close = closes[-1]
    last_high = highs[-1]
    last_low = lows[-1]
    last_range = last_high - last_low

    if last_range > 0 and (last_close - last_low) / last_range < sensitivity:
        bar_signal = "DOWN"
    elif last_range > 0 and (last_close - last_low) / last_range > (1 - sensitivity):
        bar_signal = "UP"
    else:
        bar_signal = "NEUTRAL"

    higher_highs = highs[-1] > highs[-2] and highs[-2] > highs[-3]
    lower_lows = lows[-1] < lows[-2] and lows[-2] < lows[-3]
    higher_closes = closes[-1] > closes[-2] and closes[-2] > closes[-3]
    lower_closes = closes[-1] < closes[-2] and closes[-2] < closes[-3]
    price_change = (closes[-1] - closes[0]) / closes[0] * 100

    if lower_lows or lower_closes or price_change < -0.05:
        trend = "DOWN"
    elif higher_highs or higher_closes or price_change > 0.05:
        trend = "UP"
    else:
        trend = bar_signal
    return trend

# ============================================================
# SMERY POHYBU - z PDF
# ============================================================

def detect_market_mode(df_1h, df_daily, atr_1h):
    """
    Z PDF - 2 zdroje energie instrumentu:
    1. Rejnz (Range) - instrument stoji v koridoru a nabira pozici
    2. Kontrtrendove hnutí
    
    Longova model: zavreni dne v nejvyssi bode
    Shortova model: zavreni dne v nejnizsi bode
    """
    closes_1h = df_1h["close"].tail(20).values
    highs_1h = df_1h["high"].tail(20).values
    lows_1h = df_1h["low"].tail(20).values

    # Vypocet koridoru
    recent_high = max(highs_1h[-10:])
    recent_low = min(lows_1h[-10:])
    corridor_width = recent_high - recent_low
    last_close = closes_1h[-1]

    # Rejnz - instrument se pohybuje v uzkém koridoru
    avg_atr_range = atr_1h * 8
    is_range = corridor_width < avg_atr_range

    # Pozice v koridoru
    if corridor_width > 0:
        position_in_corridor = (last_close - recent_low) / corridor_width
    else:
        position_in_corridor = 0.5

    # Smer podle pozice v koridoru (z PDF)
    # Zavreni pod hornim uroven kanalu = short
    # Zavreni nad spodnim uroven kanalu = long
    if position_in_corridor > 0.7:
        corridor_signal = "SHORT"  # blizko vrcholu - short
    elif position_in_corridor < 0.3:
        corridor_signal = "LONG"   # blizko dna - long
    else:
        corridor_signal = "NEUTRAL"

    # Longova/Shortova model podle denního zavření
    last_daily = df_daily.iloc[-1]
    daily_range = last_daily["high"] - last_daily["low"]
    daily_close_pos = 0.5
    if daily_range > 0:
        daily_close_pos = (last_daily["close"] - last_daily["low"]) / daily_range

    # Zavreni v nejvyssi tretine = longova model (pohyb pokracuje)
    if daily_close_pos > 0.75:
        daily_model = "LONG"
    # Zavreni v nejnizsi tretine = shortova model
    elif daily_close_pos < 0.25:
        daily_model = "SHORT"
    else:
        daily_model = "NEUTRAL"

    # Kontrtrendove hnutí detekce
    # Pred finalnim pohybem = finalni zaderg proti
    closes_short = df_1h["close"].tail(5).values
    price_velocity = [(closes_short[i] - closes_short[i-1]) for i in range(1, len(closes_short))]
    direction_changes = sum(1 for i in range(1, len(price_velocity))
                           if price_velocity[i] * price_velocity[i-1] < 0)
    is_countertrend = direction_changes >= 3

    return {
        "is_range": is_range,
        "corridor_width": round(corridor_width, 5),
        "corridor_signal": corridor_signal,
        "position_in_corridor": round(position_in_corridor, 2),
        "daily_model": daily_model,
        "daily_close_pos": round(daily_close_pos, 2),
        "is_countertrend": is_countertrend,
        "recent_high": round(recent_high, 5),
        "recent_low": round(recent_low, 5)
    }

# ============================================================
# LOZNY PROBOJ - vsechny varianty z PDF
# ============================================================

def check_false_breakout_1bar(df_1h, level_type, level_price, atr):
    """
    LP jednim barem - z PDF:
    - Bar prorazil uroven ale zavrel zpet
    - Hloubka proboje < 1/3 ATR
    - Pokud cena odejde od zaявky o 1 ATR = zrusit
    """
    tolerance = atr * 0.1
    max_depth = atr / 3
    bars = df_1h.tail(5)
    if len(bars) < 2:
        return False, None

    prev = bars.iloc[-2]
    last = bars.iloc[-1]

    if level_type == "RESISTANCE":
        breakout = prev["high"] > level_price + tolerance
        closed_back = prev["close"] < level_price
        depth = prev["high"] - level_price
        no_impulse = abs(last["close"] - level_price) < atr
        if breakout and closed_back and depth < max_depth and no_impulse:
            return True, "SHORT"

    elif level_type == "SUPPORT":
        breakout = prev["low"] < level_price - tolerance
        closed_back = prev["close"] > level_price
        depth = level_price - prev["low"]
        no_impulse = abs(last["close"] - level_price) < atr
        if breakout and closed_back and depth < max_depth and no_impulse:
            return True, "LONG"

    return False, None

def check_false_breakout_2bars(df_1h, level_type, level_price, atr):
    """
    LP dvema bary - z PDF:
    - Zaявка se vystavuje po otevreni druheho baru v probojne rovine
    - Zavreni druheho baru v probojne rovine = zlom modelu
    - Stop preferovane technicky
    """
    tolerance = atr * 0.1
    bars = df_1h.tail(6)
    if len(bars) < 3:
        return False, None

    bar1 = bars.iloc[-3]  # prvni probojny bar
    bar2 = bars.iloc[-2]  # druhy probojny bar
    last = bars.iloc[-1]  # posledni bar (signal)

    if level_type == "RESISTANCE":
        # Oba bary v probojne rovine (nad uroven)
        bar1_above = bar1["open"] > level_price and bar1["close"] > level_price
        bar2_above = bar2["open"] > level_price
        # Druhy bar se zavrel zpet pod uroven = LP potvrzeno
        bar2_closed_back = bar2["close"] < level_price
        # Posledni bar pod uroven
        last_below = last["close"] < level_price

        if bar1_above and bar2_above and bar2_closed_back and last_below:
            return True, "SHORT"

    elif level_type == "SUPPORT":
        bar1_below = bar1["open"] < level_price and bar1["close"] < level_price
        bar2_below = bar2["open"] < level_price
        bar2_closed_back = bar2["close"] > level_price
        last_above = last["close"] > level_price

        if bar1_below and bar2_below and bar2_closed_back and last_above:
            return True, "LONG"

    return False, None

def check_false_breakout_complex(df_1h, level_type, level_price, atr):
    """
    Slozity LP (3+ bary) - z PDF:
    - Min 3 bary s otevřením a zavřením v probojné rovině
    - Dotyk urovne OK, ale ne proboj
    - Pokud cena pokracuje ve smeru proboje = zlom modelu
    """
    tolerance = atr * 0.1
    bars = df_1h.tail(10)
    if len(bars) < 4:
        return False, None

    if level_type == "RESISTANCE":
        # Hledame 3+ bary s otevrenim a zavrenim nad uroven
        bars_above = []
        for i in range(len(bars) - 1):
            bar = bars.iloc[i]
            if bar["open"] > level_price and bar["close"] > level_price:
                bars_above.append(i)

        if len(bars_above) >= 3:
            # Posledni bar se zavrel zpet pod uroven
            last = bars.iloc[-1]
            if last["close"] < level_price:
                # Zadny bar neprebil uroven o vice nez tolerance
                max_above = max(bars.iloc[i]["high"] for i in bars_above)
                if max_above < level_price + atr * 0.5:
                    return True, "SHORT"

    elif level_type == "SUPPORT":
        bars_below = []
        for i in range(len(bars) - 1):
            bar = bars.iloc[i]
            if bar["open"] < level_price and bar["close"] < level_price:
                bars_below.append(i)

        if len(bars_below) >= 3:
            last = bars.iloc[-1]
            if last["close"] > level_price:
                min_below = min(bars.iloc[i]["low"] for i in bars_below)
                if min_below > level_price - atr * 0.5:
                    return True, "LONG"

    return False, None

def check_all_false_breakouts(df_1h, level_type, level_price, atr):
    """Zkontroluje vsechny varianty LP a vrati nejsilnejsi"""
    if level_type is None or level_price is None:
        return False, None, None

    # LP 1 barem
    ok, direction = check_false_breakout_1bar(df_1h, level_type, level_price, atr)
    if ok:
        return True, direction, "LP 1 BAR"

    # LP 2 bary
    ok, direction = check_false_breakout_2bars(df_1h, level_type, level_price, atr)
    if ok:
        return True, direction, "LP 2 BARY"

    # Slozity LP
    ok, direction = check_false_breakout_complex(df_1h, level_type, level_price, atr)
    if ok:
        return True, direction, "LP SLOZITY"

    return False, None, None

# ============================================================
# CHECKLIST - zapas hodu + tejk (z PDF)
# ============================================================

def check_entry_checklist(df_daily, df_1h, atr_daily, atr_1h,
                           level_type, level_price, signal):
    """
    Checklist z PDF pred vstupem:
    - Denni graf: uroven, smer, trend, zapas hodu, ATR
    - Hodinovy: smer, stop, tejk
    - Tejk max 40% zapasu hodu a 60% ATR
    """
    results = {}
    score = 0

    if level_price is None:
        return {"score": 0, "details": [], "stop": 0, "take": 0, "zapas_hodu": 0}

    last_daily = df_daily.iloc[-1]
    last_1h = df_1h.iloc[-1]

    # Stop loss - technicky (za uroven)
    stop_distance = atr_1h * 1.5
    if level_type == "RESISTANCE":
        stop_loss = level_price + stop_distance
    else:
        stop_loss = level_price - stop_distance
    results["stop"] = round(stop_distance, 5)

    # Zapas hodu - vzdalenost k dalsi urovni
    # Odhadneme jako 2x ATR denni (zjednoduseni)
    zapas_hodu = atr_daily * 2
    results["zapas_hodu"] = round(zapas_hodu, 5)

    # Tejk profit - max 40% zapasu hodu a 60% ATR
    max_take_from_zapas = zapas_hodu * 0.40
    max_take_from_atr = atr_daily * 0.60
    take_profit = min(max_take_from_zapas, max_take_from_atr)
    results["take"] = round(take_profit, 5)

    # RRR (risk/reward ratio)
    if stop_distance > 0:
        rrr = take_profit / stop_distance
        results["rrr"] = round(rrr, 2)
    else:
        results["rrr"] = 0

    # Checklist body
    details = []

    # 1. Smer D1 a 1H souhlasi
    trend_d1 = get_trend(df_daily, lookback=5)
    trend_1h = get_trend(df_1h, lookback=10)
    if trend_d1 == trend_1h and trend_d1 != "NEUTRAL":
        score += 2
        details.append(f"✅ D1+1H smer souhlasi ({trend_d1})")
    else:
        details.append(f"❌ D1={trend_d1} 1H={trend_1h} nesouhlasi")

    # 2. Tejk se vejde do zapasu hodu
    if take_profit <= zapas_hodu * 0.4:
        score += 2
        details.append(f"✅ Tejk OK ({round(take_profit,5)} ≤ 40% zapasu)")
    else:
        details.append(f"❌ Tejk prilis velky")

    # 3. Tejk < 60% ATR
    if take_profit <= atr_daily * 0.6:
        score += 1
        details.append(f"✅ Tejk < 60% ATR")
    else:
        details.append(f"❌ Tejk > 60% ATR")

    # 4. RRR aspon 1:1
    if results["rrr"] >= 1.0:
        score += 2
        details.append(f"✅ RRR: 1:{round(results['rrr'],1)}")
    else:
        details.append(f"❌ RRR slaby: 1:{round(results['rrr'],1)}")

    # 5. ATR ma prostor (< 75% pouzito)
    daily_range = last_daily["high"] - last_daily["low"]
    if atr_daily > 0:
        atr_used = daily_range / atr_daily
        if atr_used < 0.75:
            score += 1
            details.append(f"✅ ATR prostor ({round(atr_used*100)}% pouzito)")
        else:
            details.append(f"❌ ATR bez prostoru ({round(atr_used*100)}%)")

    results["score"] = score
    results["details"] = details
    results["max_score"] = 8

    return results

# ============================================================
# ODBOJ OD UROVNE
# ============================================================

def check_bounce_model(df_1h, level_type, level_price, atr):
    tolerance = atr * 0.1
    luft = atr * 0.2
    bars = df_1h.tail(5)
    if len(bars) < 3:
        return False, "Malo baru"
    last = bars.iloc[-1]
    prev = bars.iloc[-2]

    if level_type == "RESISTANCE":
        bpu1_hit = abs(prev["high"] - level_price) < tolerance
        bpu2_hit = abs(last["high"] - level_price) < tolerance + luft
        not_broken = prev["close"] < level_price and last["close"] < level_price
        if bpu1_hit and bpu2_hit and not_broken:
            return True, "BPU odboj resistance"

    elif level_type == "SUPPORT":
        bpu1_hit = abs(prev["low"] - level_price) < tolerance
        bpu2_hit = abs(last["low"] - level_price) < tolerance + luft
        not_broken = prev["close"] > level_price and last["close"] > level_price
        if bpu1_hit and bpu2_hit and not_broken:
            return True, "BPU odboj support"

    return False, "BPU nesplnen"

# ============================================================
# PROBOJ UROVNE
# ============================================================

def check_breakout_model(df_1h, level_type, level_price, atr, trend):
    tolerance = atr * 0.1
    bars = df_1h.tail(10)
    if len(bars) < 5:
        return False, "Malo baru"

    recent_bars = bars.tail(5)
    avg_bar_size = (recent_bars["high"] - recent_bars["low"]).mean()
    small_bars = avg_bar_size < atr * 0.4

    if level_type == "RESISTANCE":
        pressing = bars["high"].tail(3).mean() > level_price - tolerance * 2
        closed_above = bars["close"].iloc[-1] > level_price
        if small_bars and pressing and closed_above and trend == "UP":
            return True, "Proboj resistance"

    elif level_type == "SUPPORT":
        pressing = bars["low"].tail(3).mean() < level_price + tolerance * 2
        closed_below = bars["close"].iloc[-1] < level_price
        if small_bars and pressing and closed_below and trend == "DOWN":
            return True, "Proboj support"

    return False, "Proboj nesplnen"

# ============================================================
# UROVNE
# ============================================================

def detect_limit_player(df, atr):
    tolerance = atr * 0.05
    highs = df["high"].tail(30).values
    lows = df["low"].tail(30).values
    closes = df["close"].tail(30).values

    for i in range(len(highs) - 3, 2, -1):
        level = highs[i]
        count = sum(abs(highs[max(0,i-10):i+1] - level) < tolerance)
        if count >= 3:
            if all(closes[max(0,i-10):i+1] < level + tolerance):
                return "RESISTANCE", round(level, 5), "LP"

    for i in range(len(lows) - 3, 2, -1):
        level = lows[i]
        count = sum(abs(lows[max(0,i-10):i+1] - level) < tolerance)
        if count >= 3:
            if all(closes[max(0,i-10):i+1] > level - tolerance):
                return "SUPPORT", round(level, 5), "LP"

    return None, None, None

def detect_mirror_level(df_daily, atr):
    tolerance = atr * 0.1
    highs = df_daily["high"].tail(60).values
    lows = df_daily["low"].tail(60).values
    closes = df_daily["close"].tail(60).values
    last_close = closes[-1]

    for i in range(20, len(highs) - 5):
        level = highs[i]
        was_resistance = sum(abs(highs[i-5:i+5] - level) < tolerance) >= 2
        is_now_support = (abs(last_close - level) < tolerance * 2
                         and last_close > level - tolerance)
        if was_resistance and is_now_support:
            return "SUPPORT", round(level, 5), "MIRROR"

    for i in range(20, len(lows) - 5):
        level = lows[i]
        was_support = sum(abs(lows[i-5:i+5] - level) < tolerance) >= 2
        is_now_resistance = (abs(last_close - level) < tolerance * 2
                            and last_close < level + tolerance)
        if was_support and is_now_resistance:
            return "RESISTANCE", round(level, 5), "MIRROR"

    return None, None, None

def detect_paranormal_bar(df, atr):
    bars = df.tail(20)
    for i in range(len(bars) - 1, 0, -1):
        bar = bars.iloc[i]
        bar_size = bar["high"] - bar["low"]
        if bar_size > 2 * atr:
            last_close = df["close"].iloc[-1]
            if abs(last_close - bar["high"]) < atr * 0.1:
                return "RESISTANCE", round(bar["high"], 5), "PARANORMAL"
            elif abs(last_close - bar["low"]) < atr * 0.1:
                return "SUPPORT", round(bar["low"], 5), "PARANORMAL"
    return None, None, None

def detect_trend_break(df, atr):
    highs = df["high"].tail(30).values
    lows = df["low"].tail(30).values
    closes = df["close"].tail(30).values

    for i in range(10, len(highs) - 2):
        if highs[i] > max(highs[i-5:i]) and closes[i] > closes[i-3]:
            level = highs[i]
            if abs(closes[-1] - level) < atr * 0.15:
                return "RESISTANCE", round(level, 5), "TREND_BREAK"

    for i in range(10, len(lows) - 2):
        if lows[i] < min(lows[i-5:i]) and closes[i] < closes[i-3]:
            level = lows[i]
            if abs(closes[-1] - level) < atr * 0.15:
                return "SUPPORT", round(level, 5), "TREND_BREAK"

    return None, None, None

def count_level_strength(level_type, level_price, df, atr):
    if level_price is None:
        return 0
    strength = 0
    tolerance = atr * 0.1
    highs = df["high"].values
    lows = df["low"].values
    closes = df["close"].values

    if level_type == "RESISTANCE":
        touches = sum(abs(highs - level_price) < tolerance)
    else:
        touches = sum(abs(lows - level_price) < tolerance)
    strength += min(touches, 5)

    price_str = str(round(level_price, 4))
    if price_str.endswith("00") or price_str.endswith("50"):
        strength += 2

    if level_type == "RESISTANCE":
        long_wicks = sum((highs - closes) > atr * 0.3)
    else:
        long_wicks = sum((closes - lows) > atr * 0.3)
    if long_wicks >= 2:
        strength += 2

    return strength

def find_best_level(df_1h, df_daily, atr_1h, atr_daily):
    lt, lp, ltype = detect_limit_player(df_1h, atr_1h)
    if lt:
        return lt, lp, ltype, count_level_strength(lt, lp, df_1h, atr_1h)

    lt, lp, ltype = detect_paranormal_bar(df_1h, atr_1h)
    if lt:
        return lt, lp, ltype, count_level_strength(lt, lp, df_1h, atr_1h)

    lt, lp, ltype = detect_mirror_level(df_daily, atr_daily)
    if lt:
        return lt, lp, ltype, count_level_strength(lt, lp, df_daily, atr_daily)

    lt, lp, ltype = detect_trend_break(df_1h, atr_1h)
    if lt:
        return lt, lp, ltype, count_level_strength(lt, lp, df_1h, atr_1h)

    return None, None, None, 0

# ============================================================
# PREDPOKLADY
# ============================================================

def check_bounce_prerequisites(df_1h, df_daily, atr_1h,
                                atr_daily, level_price, level_type):
    score = 0
    details = []
    if level_price is None:
        return 0, []

    bars_1h = df_1h.tail(20)
    closes_1h = bars_1h["close"].values
    highs_1h = bars_1h["high"].values
    lows_1h = bars_1h["low"].values
    overall_size = (df_1h["high"] - df_1h["low"]).mean()

    # 1. Bezodrazove hnutí
    if level_type == "RESISTANCE":
        move_ok = closes_1h[-1] > closes_1h[0]
        total_move = abs(closes_1h[-1] - closes_1h[0])
        if total_move > 0:
            pullbacks = [abs(closes_1h[i] - closes_1h[i-1])
                        for i in range(1, len(closes_1h))
                        if closes_1h[i] < closes_1h[i-1]]
            max_pb = max(pullbacks) if pullbacks else 0
            if move_ok and max_pb < total_move * cfg.BOUNCE_PULLBACK_MAX:
                score += 2
                details.append("✅ Bezodrazove hnutí")
            else:
                details.append("❌ Hnutí s odskaky")
    else:
        move_ok = closes_1h[-1] < closes_1h[0]
        total_move = abs(closes_1h[-1] - closes_1h[0])
        if total_move > 0:
            pullbacks = [abs(closes_1h[i] - closes_1h[i-1])
                        for i in range(1, len(closes_1h))
                        if closes_1h[i] > closes_1h[i-1]]
            max_pb = max(pullbacks) if pullbacks else 0
            if move_ok and max_pb < total_move * cfg.BOUNCE_PULLBACK_MAX:
                score += 2
                details.append("✅ Bezodrazove hnutí")
            else:
                details.append("❌ Hnutí s odskaky")

    # 2. Pristup na velkych barech
    recent_size = (df_1h.tail(5)["high"] - df_1h.tail(5)["low"]).mean()
    if recent_size > overall_size * cfg.BOUNCE_BAR_SIZE_MIN:
        score += 2
        details.append("✅ Pristup na velkych barech")
    else:
        details.append("❌ Male bary")

    # 3. ATR > 50% do urovne
    last_daily = df_daily.iloc[-1]
    if atr_daily > 0:
        dist = abs(last_daily["open"] - level_price)
        if dist > atr_daily * cfg.BOUNCE_ATR_TO_LEVEL_MIN:
            score += 1
            details.append("✅ ATR > 50% do urovne")
        else:
            details.append("❌ ATR < 50% do urovne")

    # 4. Lokalni extrem - VECTORIZACE
    lookback = min(cfg.BOUNCE_LOOKBACK_EXTREME, len(df_1h))
    df_extreme = df_1h.tail(lookback)
    tol = cfg.BOUNCE_EXTREME_TOLERANCE
    if level_type == "RESISTANCE":
        is_extreme = level_price >= df_extreme["high"].max() * (1 - tol)
        label = "max"
    else:
        is_extreme = level_price <= df_extreme["low"].min() * (1 + tol)
        label = "min"
    if is_extreme:
        score += 2
        details.append(f"✅ Lokalni {label} ({lookback}h)")
    else:
        details.append(f"❌ Neni lokalni {label}")

    # 5. Rychlost pristupu
    last_3_size = (df_1h.tail(3)["high"] - df_1h.tail(3)["low"]).mean()
    if last_3_size > overall_size * cfg.BOUNCE_APPROACH_SPEED_MIN:
        score += 1
        details.append("✅ Rychly pristup")
    else:
        details.append("❌ Pomaly pristup")

    # 6. D1 daleko od urovne
    dist_d1 = abs(last_daily["close"] - level_price)
    if atr_daily > 0 and dist_d1 > atr_daily * cfg.BOUNCE_D1_DIST_MIN:
        score += 1
        details.append("✅ D1 zavreni daleko")
    else:
        details.append("❌ D1 blizko urovne")

    # 7. Zadna konsolidace - VECTORIZACE
    tolerance = atr_1h * 0.15
    mid_prices = (df_1h.tail(10)["high"] + df_1h.tail(10)["low"]) / 2
    bars_near = (abs(mid_prices - level_price) < tolerance).sum()
    if bars_near <= cfg.BOUNCE_MAX_BARS_NEAR:
        score += 1
        details.append("✅ Zadna konsolidace")
    else:
        details.append(f"⚠️ Konsolidace ({bars_near} baru)")

    return max(score, 0), details


def check_breakout_prerequisites(df_1h, df_daily, atr_1h,
                                  atr_daily, level_price, level_type):
    score = 0
    details = []
    if level_price is None:
        return 0, []

    tolerance = atr_1h * 0.15
    overall_size = (df_1h["high"] - df_1h["low"]).mean()

    # 1. Pristup na malych barech
    recent_size = (df_1h.tail(5)["high"] - df_1h.tail(5)["low"]).mean()
    if recent_size < overall_size * cfg.BREAKOUT_BAR_SIZE_MAX:
        score += 2
        details.append("✅ Pristup na malych barech")
    else:
        details.append("❌ Velke bary")

    # 2. Uzka proторговka - VECTORIZACE
    mid_prices = (df_1h.tail(15)["high"] + df_1h.tail(15)["low"]) / 2
    bars_near = (abs(mid_prices - level_price) < tolerance).sum()
    if bars_near >= cfg.BREAKOUT_BARS_NEAR_MIN:
        score += 2
        details.append(f"✅ Uzka proторговka ({bars_near} baru)")
    elif bars_near >= cfg.BREAKOUT_BARS_NEAR_WEAK:
        score += 1
        details.append(f"⚠️ Slaba proторговка ({bars_near})")
    else:
        details.append("❌ Zadna proторговka")

    # 3. Zatuchani volatility - VECTORIZACE
    sizes = df_1h.tail(10)["high"] - df_1h.tail(10)["low"]
    if len(sizes) >= 6:
        if sizes.iloc[5:].mean() < sizes.iloc[:5].mean() * cfg.BREAKOUT_VOLATILITY_DROP:
            score += 2
            details.append("✅ Zatuchani volatility")
        else:
            details.append("❌ Bez konsolidace")

    # 4. D1 zavreni tesne u urovne
    last_daily = df_daily.iloc[-1]
    dist_d1 = abs(last_daily["close"] - level_price)
    if atr_daily > 0 and dist_d1 < atr_daily * cfg.BREAKOUT_D1_CLOSE_MAX:
        score += 2
        details.append("✅ D1 zavreni tesne u urovne")
    else:
        details.append("❌ D1 daleko od urovne")

    # 5. Lokalni extrem - VECTORIZACE
    lookback = min(cfg.BREAKOUT_LOOKBACK_EXTREME, len(df_1h))
    df_extreme = df_1h.tail(lookback)
    tol = cfg.BREAKOUT_EXTREME_TOLERANCE
    if level_type == "RESISTANCE":
        is_extreme = level_price >= df_extreme["high"].max() * (1 - tol)
        label = "max"
    else:
        is_extreme = level_price <= df_extreme["low"].min() * (1 + tol)
        label = "min"
    if is_extreme:
        score += 1
        details.append(f"✅ Lokalni {label} ({lookback}h)")
    else:
        details.append(f"❌ Neni lokalni {label}")

    # 6. 1H trend souhlasi s probojnem
    trend_1h = get_trend(df_1h, lookback=cfg.TREND_LOOKBACK_1H)
    if level_type == "RESISTANCE" and trend_1h == "UP":
        score += 2
        details.append("✅ 1H trend souhlasi")
    elif level_type == "SUPPORT" and trend_1h == "DOWN":
        score += 2
        details.append("✅ 1H trend souhlasi")
    else:
        details.append(f"❌ 1H trend nesouhlasi ({trend_1h})")

    # 7. Cista zona - VECTORIZACE
    if level_type == "RESISTANCE":
        obstacles = ((df_1h.tail(20)["high"] > level_price) &
                    (df_1h.tail(20)["high"] < level_price +
                     atr_1h * cfg.BREAKOUT_OBSTACLE_MULT)).sum()
    else:
        obstacles = ((df_1h.tail(20)["low"] < level_price) &
                    (df_1h.tail(20)["low"] > level_price -
                     atr_1h * cfg.BREAKOUT_OBSTACLE_MULT)).sum()

    if obstacles <= cfg.BREAKOUT_MAX_OBSTACLES:
        score += 1
        details.append("✅ Cista zona vpred")
    else:
        details.append(f"❌ Prekazky ({obstacles})")

    return max(score, 0), details

# ============================================================
# HLAVNI ANALYZA
# ============================================================

def analyze_symbol(market_data):
    symbol = market_data["symbol"]
    df_daily = market_data["daily"]
    df_1h = market_data["1h"]
    atr_daily = market_data["atr_daily"]
    atr_1h = market_data["atr_1h"]

    now = datetime.now()
    entry_time, minutes_ahead = calculate_best_entry(now)

    # 1. Trendy
    trend_daily = get_trend(df_daily, lookback=5)
    trend_1h = get_trend(df_1h, lookback=10)
    trends_aligned = trend_daily == trend_1h and trend_daily != "NEUTRAL"

    # 2. ATR
    atr_ok, atr_reason = check_atr_filters(df_daily, atr_daily)

    # 3. Rezim trhu
    market_mode = detect_market_mode(df_1h, df_daily, atr_1h)

    # 4. Uroven
    level_type, level_price, level_kind, level_strength = find_best_level(
        df_1h, df_daily, atr_1h, atr_daily
    )

    # 5. Predpoklady
    bounce_score, bounce_details = check_bounce_prerequisites(
        df_1h, df_daily, atr_1h, atr_daily, level_price, level_type
    )
    breakout_score, breakout_details = check_breakout_prerequisites(
        df_1h, df_daily, atr_1h, atr_daily, level_price, level_type
    )

    if bounce_score >= breakout_score:
        recommended_model = "ODBOJ"
        pre_score = bounce_score
        pre_details = bounce_details
    else:
        recommended_model = "PROBOJ"
        pre_score = breakout_score
        pre_details = breakout_details

    # 6. Obchodni modely
    lp_ok, lp_direction, lp_type = check_all_false_breakouts(
        df_1h, level_type, level_price, atr_1h
    )
    bounce_ok, _ = check_bounce_model(
        df_1h, level_type or "RESISTANCE", level_price or 0, atr_1h
    )
    breakout_ok, _ = check_breakout_model(
        df_1h, level_type or "RESISTANCE", level_price or 0, atr_1h, trend_daily
    )

    # 7. Signal
    signal = None
    model_name = "ZADNY"

    if lp_ok and lp_direction:
        signal = lp_direction
        model_name = lp_type or "LOZNY PROBOJ"
    elif bounce_ok:
        signal = "SHORT" if level_type == "RESISTANCE" else "LONG"
        model_name = "ODBOJ"
    elif breakout_ok:
        signal = "LONG" if level_type == "RESISTANCE" else "SHORT"
        model_name = "PROBOJ"
    elif trend_daily != "NEUTRAL":
        signal = "SHORT" if trend_daily == "DOWN" else "LONG"
        model_name = "TREND+UROVEN"
    elif trend_1h != "NEUTRAL":
        signal = "SHORT" if trend_1h == "DOWN" else "LONG"
        model_name = "POUZE 1H"
    elif market_mode["corridor_signal"] != "NEUTRAL":
        signal = market_mode["corridor_signal"]
        model_name = "REJNZ"
    elif market_mode["daily_model"] != "NEUTRAL":
        signal = market_mode["daily_model"]
        model_name = "DENNI MODEL"
    else:
        signal = "SHORT"
        model_name = "SLABY"

    # 8. Checklist
    checklist_result = check_entry_checklist(
        df_daily, df_1h, atr_daily, atr_1h,
        level_type, level_price, signal
    )

    # 9. Podmínky
    conditions = {
        "trend_d1": trend_daily != "NEUTRAL",
        "trend_1h": trend_1h != "NEUTRAL",
        "trendy_souhlasi": trends_aligned,
        "atr_ok": atr_ok,
        "uroven_nalezena": level_type is not None,
        "model_nalezen": model_name not in [
            "ZADNY", "TREND+UROVEN", "POUZE 1H",
            "REJNZ", "DENNI MODEL", "SLABY"
        ],
        "sila_urovne": (level_strength or 0) >= 2,
        "predpoklady_ok": pre_score >= 4,
        "checklist_ok": checklist_result.get("score", 0) >= 4,
        "rrr_ok": checklist_result.get("rrr", 0) >= 1.0
    }

    splneno = sum(conditions.values())
    celkem = len(conditions)

    if splneno >= 8:
        signal_strength = "SILNY"
    elif splneno >= 6:
        signal_strength = "STREDNI"
    elif splneno >= 4:
        signal_strength = "SLABY"
    else:
        signal_strength = "VELMI SLABY"

    return signal, {
        "trend_daily": trend_daily,
        "trend_1h": trend_1h,
        "trends_aligned": trends_aligned,
        "atr_ok": atr_ok,
        "atr_warning": not atr_ok,
        "atr_reason": atr_reason,
        "level_found": level_type is not None,
        "level_type": level_type,
        "level_price": level_price,
        "level_kind": level_kind,
        "level_strength": level_strength or 0,
        "model": model_name,
        "recommended_model": recommended_model,
        "pre_score": pre_score,
        "pre_details": pre_details,
        "market_mode": market_mode,
        "checklist_result": checklist_result,
        "conditions": conditions,
        "splneno": splneno,
        "celkem": celkem,
        "atr_daily": round(atr_daily, 5),
        "atr_1h": round(atr_1h, 5),
        "last_close": market_data["last_close"],
        "entry_time": entry_time.strftime("%H:%M"),
        "minutes_ahead": minutes_ahead,
        "signal_generated_at": now.strftime("%H:%M:%S"),
        "signal_strength": signal_strength,
        "source": market_data.get("source", "twelvedata")
    }