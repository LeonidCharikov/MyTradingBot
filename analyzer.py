"""
analyzer.py - Jadro obchodni logiky

Implementuje algoritmus z PDF:
- Detekce urovni (LP, Mirror, Paranormal, Trend Break)
- Obchodni modely (Odboj, Proboj, Lozny proboj 1/2/3+ bary)
- Predpoklady pro kazdy model
- Multi-timeframe potvrzeni (1H, 15M, 5M)
- Udalostni vstup po zavreni BPU2
- Checklist pred vstupem
"""

import config as cfg
from datetime import datetime, timedelta
import pandas as pd

# ============================================================
# CAS UZAVRENI OBCHODU
# Na Binarium zadavas cas UZAVRENI, ne vstup.
# Otevres HNED, Binarium zavre automaticky.
# ============================================================

def calculate_best_entry(now):
    """
    Vypocita optimalni cas uzavreni obchodu.
    Potrebujes min 1 minutu na otevreni pozice.
    """
    seconds = now.second
    if seconds <= 20:
        close_in = 3   # Zacatek minuty - cas na rozmysleni
    elif seconds <= 40:
        close_in = 3   # Stred minuty
    else:
        close_in = 4   # Konec minuty - pribude 1 min rezerva
    close_time = now + timedelta(minutes=close_in)
    close_time = close_time.replace(second=0, microsecond=0)
    return close_time, close_in

# ============================================================
# ATR FILTRY
# Z PDF: pokud instrument prosel 75% ATR - stop obchodovani
# ============================================================

def check_atr_filters(df_daily, atr_daily):
    """
    Kontroluje zda ma instrument jeste prostor k pohybu.
    Pouziva denni ATR jako meritko volatility.
    """
    last = df_daily.iloc[-1]
    daily_range = last["high"] - last["low"]
    open_price = last["open"]
    close_price = last["close"]

    if atr_daily == 0:
        return False, "ATR je nula"

    # Kolik % denniho ATR uz bylo spotrebovano
    atr_used = daily_range / atr_daily
    if atr_used >= cfg.ATR_MAX_USED:
        return False, f"ATR pouzito {round(atr_used*100)}%"

    # Cena se vratila k bodu otevreni = ATR vycerpan
    if abs(close_price - open_price) < atr_daily * cfg.ATR_OPEN_CLOSE_MIN:
        return False, "Cena u bodu otevreni"

    return True, f"ATR OK ({round(atr_used*100)}% pouzito)"

# ============================================================
# TREND
# Pouziva D1 pro smerovy kontext, 1H pro vstup
# ============================================================

def get_trend(df, lookback=5, sensitivity=0.35):
    """
    Urcuje smer trendu na zaklade:
    1. Pozice zavreni v poslednim baru (longova/shortova model)
    2. Smer pohybu poslednich N svicek
    """
    closes = df["close"].tail(lookback).values
    highs = df["high"].tail(lookback).values
    lows = df["low"].tail(lookback).values
    last_range = highs[-1] - lows[-1]

    # Pozice zavreni v poslednim baru
    if last_range > 0 and (closes[-1] - lows[-1]) / last_range < sensitivity:
        bar_signal = "DOWN"   # Shortova model - zavreni dole
    elif last_range > 0 and (closes[-1] - lows[-1]) / last_range > (1 - sensitivity):
        bar_signal = "UP"     # Longova model - zavreni nahore
    else:
        bar_signal = "NEUTRAL"

    # Celkovy smer pohybu
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
# REZIM TRHU
# Z PDF: 2 zdroje energie - Rejnz a Kontrtrendovy pohyb
# ============================================================

def detect_market_mode(df_1h, df_daily, atr_1h):
    """
    Detekuje zda je instrument v:
    - REJNZ: koridoru (nabira pozici)
    - TREND: silnem pohybu jednim smerem

    Longova model: zavreni dne v nejvyssi bode
    Shortova model: zavreni dne v nejnizsi bode
    """
    highs_1h = df_1h["high"].tail(20).values
    lows_1h = df_1h["low"].tail(20).values
    closes_1h = df_1h["close"].tail(20).values

    # Koridor za poslednich 10 svicek
    recent_high = max(highs_1h[-10:])
    recent_low = min(lows_1h[-10:])
    corridor_width = recent_high - recent_low
    last_close = closes_1h[-1]

    # Rejnz = sirka koridoru < 8x ATR
    is_range = corridor_width < atr_1h * 8

    # Pozice v koridoru (0 = dno, 1 = vrchol)
    position_in_corridor = (
        (last_close - recent_low) / corridor_width
        if corridor_width > 0 else 0.5
    )

    # Signal z koridoru (z PDF: zavreni pod vrcholem = short)
    if position_in_corridor > 0.7:
        corridor_signal = "SHORT"
    elif position_in_corridor < 0.3:
        corridor_signal = "LONG"
    else:
        corridor_signal = "NEUTRAL"

    # Denni model (z PDF: longova/shortova model)
    last_daily = df_daily.iloc[-1]
    daily_range = last_daily["high"] - last_daily["low"]
    daily_close_pos = (
        (last_daily["close"] - last_daily["low"]) / daily_range
        if daily_range > 0 else 0.5
    )

    if daily_close_pos > 0.75:
        daily_model = "LONG"    # Zavreni v nejvyssi tretine = pohyb pokracuje
    elif daily_close_pos < 0.25:
        daily_model = "SHORT"   # Zavreni v nejnizsi tretine
    else:
        daily_model = "NEUTRAL"

    # Detekce parabolickych pohybu (pohyb bez boje)
    # Serie velkych svicek jednim smerem bez konsolidace
    closes_5 = df_1h["close"].tail(5).values
    bar_sizes = df_1h.tail(5)["high"].values - df_1h.tail(5)["low"].values
    avg_size = (df_1h["high"] - df_1h["low"]).mean()
    big_bars = sum(1 for s in bar_sizes if s > avg_size * 1.5)
    is_parabolic = big_bars >= 3  # 3+ velke svicky = parabolicky pohyb

    return {
        "is_range": is_range,
        "corridor_width": round(corridor_width, 5),
        "corridor_signal": corridor_signal,
        "position_in_corridor": round(position_in_corridor, 2),
        "daily_model": daily_model,
        "daily_close_pos": round(daily_close_pos, 2),
        "recent_high": round(recent_high, 5),
        "recent_low": round(recent_low, 5),
        "is_parabolic": is_parabolic,   # Pohyb bez boje
    }

# ============================================================
# LOZNY PROBOJ (LP) - vsechny varianty z PDF
# Z PDF: vsechna silna hnutí zacínají a konci LP
# ============================================================

def check_false_breakout_1bar(df, level_type, level_price, atr):
    """
    LP jednim barem:
    - Bar prorazil uroven ale zavrel zpet
    - Hloubka proboje < 1/3 ATR (z PDF)
    - Po LP neni impuls pro dalsi pohyb
    """
    tolerance = atr * cfg.BOUNCE_TOLERANCE
    max_depth = atr * cfg.LP_MAX_DEPTH   # 1/3 ATR
    bars = df.tail(5)
    if len(bars) < 2:
        return False, None

    prev = bars.iloc[-2]   # Probojny bar
    last = bars.iloc[-1]   # Posledni bar (po LP)

    if level_type == "RESISTANCE":
        breakout = prev["high"] > level_price + tolerance
        closed_back = prev["close"] < level_price
        depth = prev["high"] - level_price
        no_impulse = abs(last["close"] - level_price) < atr * cfg.LP_NO_IMPULSE
        if breakout and closed_back and depth < max_depth and no_impulse:
            return True, "SHORT"

    elif level_type == "SUPPORT":
        breakout = prev["low"] < level_price - tolerance
        closed_back = prev["close"] > level_price
        depth = level_price - prev["low"]
        no_impulse = abs(last["close"] - level_price) < atr * cfg.LP_NO_IMPULSE
        if breakout and closed_back and depth < max_depth and no_impulse:
            return True, "LONG"

    return False, None


def check_false_breakout_2bars(df, level_type, level_price, atr):
    """
    LP dvema bary (z PDF):
    - Zaявka po otevreni 2. baru v probojne rovine
    - Zavreni 2. baru zpet = slom modelu
    - Hloubka max 1/3 ATR - kontrolovana pro oba bary
    """
    tolerance = atr * cfg.BOUNCE_TOLERANCE
    max_depth = atr * cfg.LP_MAX_DEPTH
    bars = df.tail(6)
    if len(bars) < 3:
        return False, None

    bar1 = bars.iloc[-3]   # 1. probojny bar
    bar2 = bars.iloc[-2]   # 2. probojny bar
    last = bars.iloc[-1]   # Posledni bar (signal)

    if level_type == "RESISTANCE":
        bar1_above = bar1["open"] > level_price and bar1["close"] > level_price
        bar2_above = bar2["open"] > level_price
        bar2_closed_back = bar2["close"] < level_price
        # Hloubka = max high obou baru
        depth = max(bar1["high"], bar2["high"]) - level_price
        last_below = last["close"] < level_price

        if bar1_above and bar2_above and bar2_closed_back and depth < max_depth and last_below:
            return True, "SHORT"

    elif level_type == "SUPPORT":
        bar1_below = bar1["open"] < level_price and bar1["close"] < level_price
        bar2_below = bar2["open"] < level_price
        bar2_closed_back = bar2["close"] > level_price
        depth = level_price - min(bar1["low"], bar2["low"])
        last_above = last["close"] > level_price

        if bar1_below and bar2_below and bar2_closed_back and depth < max_depth and last_above:
            return True, "LONG"

    return False, None


def check_false_breakout_complex(df, level_type, level_price, atr):
    """
    Slozity LP (3+ bary) (z PDF):
    - Min 3 bary otevreny a zavreny v probojne rovine
    - Dotyk urovne OK, ale ne proboj
    - Hloubka vsech baru < 1/3 ATR
    - Navrat za uroven = signal
    """
    tolerance = atr * cfg.BOUNCE_TOLERANCE
    max_depth = atr * cfg.LP_MAX_DEPTH
    bars = df.tail(10)
    if len(bars) < 4:
        return False, None

    if level_type == "RESISTANCE":
        # Najdi bary v probojne rovine
        bars_above = [
            i for i in range(len(bars) - 1)
            if bars.iloc[i]["open"] > level_price and bars.iloc[i]["close"] > level_price
        ]
        if len(bars_above) >= 3:
            last = bars.iloc[-1]
            if last["close"] < level_price:
                # Kontrola hloubky vsech probojnych baru
                max_high = max(bars.iloc[i]["high"] for i in bars_above)
                depth = max_high - level_price
                if depth < max_depth:
                    return True, "SHORT"

    elif level_type == "SUPPORT":
        bars_below = [
            i for i in range(len(bars) - 1)
            if bars.iloc[i]["open"] < level_price and bars.iloc[i]["close"] < level_price
        ]
        if len(bars_below) >= 3:
            last = bars.iloc[-1]
            if last["close"] > level_price:
                min_low = min(bars.iloc[i]["low"] for i in bars_below)
                depth = level_price - min_low
                if depth < max_depth:
                    return True, "LONG"

    return False, None


def check_all_false_breakouts(df, level_type, level_price, atr):
    """Zkontroluje vsechny varianty LP, vrati nejsilnejsi"""
    if level_type is None or level_price is None:
        return False, None, None

    ok, direction = check_false_breakout_1bar(df, level_type, level_price, atr)
    if ok:
        return True, direction, "LP 1 BAR"

    ok, direction = check_false_breakout_2bars(df, level_type, level_price, atr)
    if ok:
        return True, direction, "LP 2 BARY"

    ok, direction = check_false_breakout_complex(df, level_type, level_price, atr)
    if ok:
        return True, direction, "LP SLOZITY"

    return False, None, None

# ============================================================
# UDALOSTNI VSTUP - ceka na zavreni BPU2
# Z PDF: vstup az po zavreni potvrzujiciho baru
# ============================================================

def check_bpu2_closed(df, level_type, level_price, atr):
    """
    Kontroluje zda BPU2 uz zavrel.
    DULEZITE: kontrolujeme iloc[-2] (predposledni bar = uz zavrely),
    ne iloc[-1] (posledni bar = aktualne otevreny!).
    """
    if df is None or level_type is None or level_price is None:
        return False, None

    tolerance = atr * cfg.BOUNCE_TOLERANCE
    stop_distance = atr * cfg.CHECKLIST_STOP_MULT
    luft = stop_distance * 0.20   # 20% stopu (z PDF)

    # Potrebujeme aspon 3 bary (BPU1, BPU2, aktualni)
    if len(df) < 3:
        return False, None

    bpu2 = df.iloc[-2]   # Predposledni = uz zavrely bar (BPU2)
    bpu1 = df.iloc[-3]   # Bar pred BPU2 (BPU1)

    if level_type == "RESISTANCE":
        bpu1_ok = abs(bpu1["high"] - level_price) < tolerance
        bpu2_ok = (level_price - luft <= bpu2["high"] <= level_price + tolerance)
        closed_below = bpu2["close"] < level_price  # Zavrel zpet pod uroven

        if bpu1_ok and bpu2_ok and closed_below:
            return True, bpu2["datetime"]

    elif level_type == "SUPPORT":
        bpu1_ok = abs(bpu1["low"] - level_price) < tolerance
        bpu2_ok = (level_price - tolerance <= bpu2["low"] <= level_price + luft)
        closed_above = bpu2["close"] > level_price

        if bpu1_ok and bpu2_ok and closed_above:
            return True, bpu2["datetime"]

    return False, None

# ============================================================
# ODBOJ OD UROVNE
# Z PDF: BSU + BPU1 + BPU2 model
# ============================================================

def check_bounce_model(df, level_type, level_price, atr):
    """
    Odboj od urovne (z PDF):
    1. BPU1 bije kopejka v kopejku
    2. BPU2 ve stejne rovine jako BPU1 (v luftu)
    3. Mezi BPU1 a BPU2 nesmi byt jiny bar
    4. Uroven nesmi byt probita
    Luft = 20% stopu (z PDF)
    """
    tolerance = atr * cfg.BOUNCE_TOLERANCE
    stop_distance = atr * cfg.CHECKLIST_STOP_MULT
    luft = stop_distance * 0.20   # 20% stopu = luft

    bars = df.tail(5)
    if len(bars) < 3:
        return False, "Malo baru"

    last = bars.iloc[-1]   # BPU2 (aktualne otevreny nebo posledni zavrely)
    prev = bars.iloc[-2]   # BPU1

    if level_type == "RESISTANCE":
        bpu1_hit = abs(prev["high"] - level_price) < tolerance
        # BPU2 v luftu: high mezi (uroven - luft) a (uroven + tolerance)
        bpu2_in_luft = (level_price - luft <= last["high"] <= level_price + tolerance)
        not_broken = prev["close"] < level_price and last["close"] < level_price

        # Kontrola ze mezi BPU1 a BPU2 neni dalsi bar u urovne
        consecutive = True
        if len(bars) >= 4:
            between = bars.iloc[-3]
            if abs(between["high"] - level_price) < tolerance:
                consecutive = False

        if bpu1_hit and bpu2_in_luft and not_broken and consecutive:
            return True, "BPU resistance OK"
        else:
            reasons = []
            if not bpu1_hit: reasons.append("BPU1 nehraje")
            if not bpu2_in_luft: reasons.append("BPU2 mimo luft")
            if not not_broken: reasons.append("Uroven probita")
            if not consecutive: reasons.append("Bary nejdou podrad")
            return False, " | ".join(reasons)

    elif level_type == "SUPPORT":
        bpu1_hit = abs(prev["low"] - level_price) < tolerance
        bpu2_in_luft = (level_price - tolerance <= last["low"] <= level_price + luft)
        not_broken = prev["close"] > level_price and last["close"] > level_price

        consecutive = True
        if len(bars) >= 4:
            between = bars.iloc[-3]
            if abs(between["low"] - level_price) < tolerance:
                consecutive = False

        if bpu1_hit and bpu2_in_luft and not_broken and consecutive:
            return True, "BPU support OK"
        else:
            reasons = []
            if not bpu1_hit: reasons.append("BPU1 nehraje")
            if not bpu2_in_luft: reasons.append("BPU2 mimo luft")
            if not not_broken: reasons.append("Uroven probita")
            if not consecutive: reasons.append("Bary nejdou podrad")
            return False, " | ".join(reasons)

    return False, "Neznamy typ"

# ============================================================
# PROBOJ UROVNE
# Z PDF: konsolidace + pritiskani + mala bary + prolomení
# ============================================================

def check_breakout_model(df, level_type, level_price, atr, trend):
    """
    Proboj urovne (z PDF):
    - Pristup na malych barech (male bary = akumulace)
    - Uzka protorvoka / prilepeni (min 3/5 baru tesne u urovne)
    - Pressing (cena se tiskne k urovni)
    - Zavreni za uroven = potvrzeni
    """
    tolerance = atr * cfg.BOUNCE_TOLERANCE
    tight_tol = atr * 0.15   # Tesna tolerance pro prilepeni
    bars = df.tail(10)
    if len(bars) < 5:
        return False, "Malo baru"

    recent = bars.tail(5)
    avg_bar_size = (recent["high"] - recent["low"]).mean()
    small_bars = avg_bar_size < atr * cfg.BREAKOUT_SMALL_BAR

    # Prilepeni: stredy baru musi byt tesne u urovne
    mid_prices = (recent["high"] + recent["low"]) / 2
    if level_type == "RESISTANCE":
        # Bary tesne pod uroven (prilepaji se)
        sticking = (
            (mid_prices > level_price - tight_tol * 2) &
            (mid_prices < level_price + tolerance)
        ).sum()
        pressing = (bars["high"].tail(3) > level_price - tolerance * cfg.BREAKOUT_PRESS_MULT).all()
        closed_side = bars["close"].iloc[-1] > level_price
        trend_ok = trend in ["UP", "NEUTRAL"]

    elif level_type == "SUPPORT":
        sticking = (
            (mid_prices < level_price + tight_tol * 2) &
            (mid_prices > level_price - tolerance)
        ).sum()
        pressing = (bars["low"].tail(3) < level_price + tolerance * cfg.BREAKOUT_PRESS_MULT).all()
        closed_side = bars["close"].iloc[-1] < level_price
        trend_ok = trend in ["DOWN", "NEUTRAL"]
    else:
        return False, "Neznamy typ"

    sticking_ok = sticking >= 3   # Min 3 z 5 baru prilepeny

    if small_bars and sticking_ok and pressing and closed_side and trend_ok:
        return True, f"Proboj OK (prilepeni {sticking}/5)"
    else:
        reasons = []
        if not small_bars: reasons.append("Velke bary")
        if not sticking_ok: reasons.append(f"Malo prilepeni ({sticking}/5)")
        if not pressing: reasons.append("Neni pressing")
        if not closed_side: reasons.append("Nezavrel za uroven")
        return False, " | ".join(reasons)

# ============================================================
# DETEKCE UROVNI
# Priorita: LP > Paranormal > Mirror > Trend Break
# ============================================================

def detect_limit_player(df, atr):
    """
    Uroven limitniho hrace (z PDF):
    - Min 3 bary bijici na stejnou cenu
    - Uroven nesmi byt probita
    """
    tolerance = atr * cfg.LEVEL_LP_TOLERANCE
    highs = df["high"].tail(30).values
    lows = df["low"].tail(30).values
    closes = df["close"].tail(30).values

    for i in range(len(highs) - 3, 2, -1):
        level = highs[i]
        count = sum(abs(highs[max(0, i-10):i+1] - level) < tolerance)
        if count >= cfg.LEVEL_MIN_TOUCHES:
            if all(closes[max(0, i-10):i+1] < level + tolerance):
                return "RESISTANCE", round(level, 5), "LP"

    for i in range(len(lows) - 3, 2, -1):
        level = lows[i]
        count = sum(abs(lows[max(0, i-10):i+1] - level) < tolerance)
        if count >= cfg.LEVEL_MIN_TOUCHES:
            if all(closes[max(0, i-10):i+1] > level - tolerance):
                return "SUPPORT", round(level, 5), "LP"

    return None, None, None


def detect_mirror_level(df_daily, atr):
    """
    Zrcadlovy uroven (z PDF):
    - Byl resistance, stal se supportem nebo naopak
    """
    tolerance = atr * cfg.LEVEL_MIRROR_TOLERANCE
    highs = df_daily["high"].tail(60).values
    lows = df_daily["low"].tail(60).values
    closes = df_daily["close"].tail(60).values
    last_close = closes[-1]

    for i in range(20, len(highs) - 5):
        level = highs[i]
        was_resistance = sum(abs(highs[i-5:i+5] - level) < tolerance) >= 2
        is_now_support = (
            abs(last_close - level) < tolerance * 2 and
            last_close > level - tolerance
        )
        if was_resistance and is_now_support:
            return "SUPPORT", round(level, 5), "MIRROR"

    for i in range(20, len(lows) - 5):
        level = lows[i]
        was_support = sum(abs(lows[i-5:i+5] - level) < tolerance) >= 2
        is_now_resistance = (
            abs(last_close - level) < tolerance * 2 and
            last_close < level + tolerance
        )
        if was_support and is_now_resistance:
            return "RESISTANCE", round(level, 5), "MIRROR"

    return None, None, None


def detect_paranormal_bar(df, atr):
    """
    Paranormalni bar (z PDF):
    - Velikost baru > 2x ATR
    - Musi byt potvrzen dotkem (cena se vraci k high/low)
    """
    bars = df.tail(20)
    for i in range(len(bars) - 1, 0, -1):
        bar = bars.iloc[i]
        bar_size = bar["high"] - bar["low"]
        if bar_size > cfg.LEVEL_PARANORMAL_MULT * atr:
            last_close = df["close"].iloc[-1]
            if abs(last_close - bar["high"]) < atr * 0.1:
                return "RESISTANCE", round(bar["high"], 5), "PARANORMAL"
            elif abs(last_close - bar["low"]) < atr * 0.1:
                return "SUPPORT", round(bar["low"], 5), "PARANORMAL"
    return None, None, None


def detect_trend_break(df, atr):
    """
    Zlom trendu (z PDF):
    - Velky hrac nabira pozici
    - Vznika nove high/low (perехай/перелоу)
    """
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
    """
    Sila urovne (z PDF):
    + Mnoho doteku (+1 za kazdy, max 5)
    + Okrouhle cislo (+2)
    + Dlouhe chvosty = sbery stopu (+2)
    """
    if level_price is None:
        return 0
    strength = 0
    tolerance = atr * 0.1
    highs = df["high"].values
    lows = df["low"].values
    closes = df["close"].values

    # Pocet doteku urovne
    if level_type == "RESISTANCE":
        touches = sum(abs(highs - level_price) < tolerance)
    else:
        touches = sum(abs(lows - level_price) < tolerance)
    strength += min(touches, 5)

    # Okrouhle cislo (psychologicka uroven)
    price_str = str(round(level_price, 4))
    if price_str.endswith("00") or price_str.endswith("50"):
        strength += 2

    # Dlouhe chvosty (sbery stopu)
    if level_type == "RESISTANCE":
        long_wicks = sum((highs - closes) > atr * 0.3)
    else:
        long_wicks = sum((closes - lows) > atr * 0.3)
    if long_wicks >= 2:
        strength += 2

    return strength


def find_best_level(df_1h, df_daily, atr_1h, atr_daily):
    """
    Najde nejsilnejsi uroven podle priority z PDF:
    1. Limitni hrac (nejsilnejsi)
    2. Paranormalni bar
    3. Zrcadlovy uroven
    4. Zlom trendu
    """
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
# PREDPOKLADY PRO ODBOJ
# Lokalni kontext (hodiny/dny) - pro 5min obchodovani
# ============================================================

def check_bounce_prerequisites(df_1h, df_daily, atr_1h, atr_daily, level_price, level_type):
    """
    Predpoklady pro odboj od urovne (lokalni kontext):
    1. Bezodrazove hnutí k urovni
    2. Pristup na velkych barech
    3. ATR > 50% do urovne
    4. Lokalni extrem (3 dny = 72h)
    5. Rychlost pristupu
    6. D1 zavreni daleko od urovne
    7. Zadna konsolidace u urovne
    """
    score = 0
    details = []
    if level_price is None:
        return 0, []

    bars_1h = df_1h.tail(20)
    closes_1h = bars_1h["close"].values
    overall_size = (df_1h["high"] - df_1h["low"]).mean()

    # 1. Bezodrazove hnutí (parabolicky pohyb k urovni)
    total_move = abs(closes_1h[-1] - closes_1h[0])
    if total_move > 0:
        if level_type == "RESISTANCE":
            pullbacks = [
                abs(closes_1h[i] - closes_1h[i-1])
                for i in range(1, len(closes_1h))
                if closes_1h[i] < closes_1h[i-1]
            ]
        else:
            pullbacks = [
                abs(closes_1h[i] - closes_1h[i-1])
                for i in range(1, len(closes_1h))
                if closes_1h[i] > closes_1h[i-1]
            ]
        max_pb = max(pullbacks) if pullbacks else 0
        if max_pb < total_move * cfg.BOUNCE_PULLBACK_MAX:
            score += 2
            details.append("✅ Bezodrazove hnutí")
        else:
            details.append("❌ Hnutí s odskaky")

    # 2. Pristup na velkych barech
    recent_size = (df_1h.tail(5)["high"] - df_1h.tail(5)["low"]).mean()
    if recent_size > overall_size * cfg.BOUNCE_BAR_SIZE_MIN:
        score += 2
        details.append("✅ Velke bary pri pristupu")
    else:
        details.append("❌ Male bary pri pristupu")

    # 3. ATR > 50% do urovne
    last_daily = df_daily.iloc[-1]
    if atr_daily > 0:
        dist = abs(last_daily["open"] - level_price)
        if dist > atr_daily * cfg.BOUNCE_ATR_TO_LEVEL_MIN:
            score += 1
            details.append("✅ ATR > 50% do urovne")
        else:
            details.append("❌ Mala vzdalenost k urovni")

    # 4. Lokalni extrem (3 dny)
    lookback = min(cfg.BOUNCE_LOOKBACK_EXTREME, len(df_1h))
    df_ext = df_1h.tail(lookback)
    tol = cfg.BOUNCE_EXTREME_TOLERANCE
    if level_type == "RESISTANCE":
        is_extreme = level_price >= df_ext["high"].max() * (1 - tol)
    else:
        is_extreme = level_price <= df_ext["low"].min() * (1 + tol)
    if is_extreme:
        score += 2
        details.append(f"✅ Lokalni extrem (72h)")
    else:
        details.append("❌ Neni lokalni extrem")

    # 5. Rychlost pristupu (posledni 3 bary velke)
    last_3_size = (df_1h.tail(3)["high"] - df_1h.tail(3)["low"]).mean()
    if last_3_size > overall_size * cfg.BOUNCE_APPROACH_SPEED_MIN:
        score += 1
        details.append("✅ Rychly pristup")
    else:
        details.append("❌ Pomaly pristup")

    # 6. D1 zavreni daleko od urovne (prostor pro odboj)
    dist_d1 = abs(last_daily["close"] - level_price)
    if atr_daily > 0 and dist_d1 > atr_daily * cfg.BOUNCE_D1_DIST_MIN:
        score += 1
        details.append("✅ D1 zavreni daleko")
    else:
        details.append("❌ D1 blizko urovne")

    # 7. Zadna konsolidace u urovne (konsolidace = spis proboj)
    mid_prices = (df_1h.tail(10)["high"] + df_1h.tail(10)["low"]) / 2
    bars_near = (abs(mid_prices - level_price) < atr_1h * 0.15).sum()
    if bars_near <= cfg.BOUNCE_MAX_BARS_NEAR:
        score += 1
        details.append("✅ Zadna konsolidace")
    else:
        details.append(f"⚠️ Konsolidace ({bars_near} baru)")

    return max(score, 0), details

# ============================================================
# PREDPOKLADY PRO PROBOJ
# ============================================================

def check_breakout_prerequisites(df_1h, df_daily, atr_1h, atr_daily, level_price, level_type):
    """
    Predpoklady pro proboj urovne (lokalni kontext):
    1. Male bary pri pristupu
    2. Uzka proторговka (prilepani)
    3. Konsolidace - zatuchani volatility
    4. D1 zavreni tesne u urovne
    5. Lokalni extrem (5 dni)
    6. 1H trend souhlasi s probojnem
    7. Cista zona pred uroven
    """
    score = 0
    details = []
    if level_price is None:
        return 0, []

    tolerance = atr_1h * 0.15
    overall_size = (df_1h["high"] - df_1h["low"]).mean()

    # 1. Male bary pri pristupu
    recent_size = (df_1h.tail(5)["high"] - df_1h.tail(5)["low"]).mean()
    if recent_size < overall_size * cfg.BREAKOUT_BAR_SIZE_MAX:
        score += 2
        details.append("✅ Male bary pri pristupu")
    else:
        details.append("❌ Velke bary")

    # 2. Uzka proторговka (prilepani k urovni)
    mid_prices = (df_1h.tail(15)["high"] + df_1h.tail(15)["low"]) / 2
    bars_near = (abs(mid_prices - level_price) < tolerance).sum()
    if bars_near >= cfg.BREAKOUT_BARS_NEAR_MIN:
        score += 2
        details.append(f"✅ Prilepani ({bars_near} baru)")
    elif bars_near >= cfg.BREAKOUT_BARS_NEAR_WEAK:
        score += 1
        details.append(f"⚠️ Slabe prilepani ({bars_near})")
    else:
        details.append("❌ Zadne prilepani")

    # 3. Zatuchani volatility (konsolidace)
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

    # 5. Lokalni extrem (5 dni)
    lookback = min(cfg.BREAKOUT_LOOKBACK_EXTREME, len(df_1h))
    df_ext = df_1h.tail(lookback)
    tol = cfg.BREAKOUT_EXTREME_TOLERANCE
    if level_type == "RESISTANCE":
        is_extreme = level_price >= df_ext["high"].max() * (1 - tol)
    else:
        is_extreme = level_price <= df_ext["low"].min() * (1 + tol)
    if is_extreme:
        score += 1
        details.append(f"✅ Lokalni extrem (120h)")
    else:
        details.append("❌ Neni lokalni extrem")

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

    # 7. Cista zona pred uroven
    if level_type == "RESISTANCE":
        obstacles = (
            (df_1h.tail(20)["high"] > level_price) &
            (df_1h.tail(20)["high"] < level_price + atr_1h * cfg.BREAKOUT_OBSTACLE_MULT)
        ).sum()
    else:
        obstacles = (
            (df_1h.tail(20)["low"] < level_price) &
            (df_1h.tail(20)["low"] > level_price - atr_1h * cfg.BREAKOUT_OBSTACLE_MULT)
        ).sum()
    if obstacles <= cfg.BREAKOUT_MAX_OBSTACLES:
        score += 1
        details.append("✅ Cista zona vpred")
    else:
        details.append(f"❌ Prekazky ({obstacles})")

    return max(score, 0), details

# ============================================================
# CHECKLIST PRED VSTUPEM
# Z PDF: tejk max 40% zapasu hodu a 60% ATR
# ============================================================

def check_entry_checklist(df_daily, df_1h, atr_daily, atr_1h, level_type, level_price, signal):
    """
    Finalni checklist pred vstupem (z PDF):
    - Smer D1 a 1H souhlasi
    - Tejk se vejde do zapasu hodu (max 40%)
    - Tejk < 60% ATR
    - RRR aspon 1:1
    - ATR ma prostor
    """
    results = {}
    score = 0

    if level_price is None:
        return {"score": 0, "details": [], "rrr": 0}

    # Stop vzdalenost (za uroven)
    stop_distance = atr_1h * cfg.CHECKLIST_STOP_MULT
    results["stop"] = round(stop_distance, 5)

    # Zapas hodu (odhadneme jako 2x denni ATR)
    zapas_hodu = atr_daily * 2
    results["zapas_hodu"] = round(zapas_hodu, 5)

    # Tejk = minimum z (40% zapasu) a (60% ATR)
    take_profit = min(
        zapas_hodu * cfg.CHECKLIST_TAKE_MAX_ZAPAS,
        atr_daily * cfg.CHECKLIST_TAKE_MAX_ATR
    )
    results["take"] = round(take_profit, 5)

    # RRR
    results["rrr"] = round(take_profit / stop_distance, 2) if stop_distance > 0 else 0

    details = []

    # 1. Smer D1 a 1H souhlasi
    trend_d1 = get_trend(df_daily, lookback=cfg.TREND_LOOKBACK_D1)
    trend_1h = get_trend(df_1h, lookback=cfg.TREND_LOOKBACK_1H)
    if trend_d1 == trend_1h and trend_d1 != "NEUTRAL":
        score += 2
        details.append(f"✅ D1+1H souhlasi ({trend_d1})")
    else:
        details.append(f"❌ D1={trend_d1} 1H={trend_1h}")

    # 2. Tejk v zapasu hodu
    if take_profit <= zapas_hodu * 0.4:
        score += 2
        details.append("✅ Tejk OK v zapasu hodu")
    else:
        details.append("❌ Tejk velky")

    # 3. Tejk < 60% ATR
    if take_profit <= atr_daily * 0.6:
        score += 1
        details.append("✅ Tejk < 60% ATR")
    else:
        details.append("❌ Tejk > 60% ATR")

    # 4. RRR aspon 1:1
    if results["rrr"] >= cfg.CHECKLIST_MIN_RRR:
        score += 2
        details.append(f"✅ RRR 1:{results['rrr']}")
    else:
        details.append(f"❌ RRR slaby 1:{results['rrr']}")

    # 5. ATR ma prostor
    daily_range = df_daily.iloc[-1]["high"] - df_daily.iloc[-1]["low"]
    if atr_daily > 0:
        atr_used = daily_range / atr_daily
        if atr_used < 0.75:
            score += 1
            details.append(f"✅ ATR prostor ({round(atr_used*100)}%)")
        else:
            details.append(f"❌ ATR bez prostoru ({round(atr_used*100)}%)")

    results["score"] = score
    results["max_score"] = 8
    results["details"] = details

    return results

# ============================================================
# HLAVNI FUNKCE ANALYZY
# ============================================================

def analyze_symbol(market_data):
    """
    Hlavni funkce - orchestruje celou analyzu:
    1. Trend (D1 pro kontext, 1H pro vstup)
    2. ATR filtry
    3. Rezim trhu (Rejnz vs Trend)
    4. Detekce nejsilnejsi urovne
    5. Predpoklady pro odboj/proboj
    6. Obchodni model (LP > Odboj > Proboj > Trend)
    7. Multi-timeframe potvrzeni (15M, 5M)
    8. Udalostni vstup po zavreni BPU2
    9. Finalni checklist
    """
    symbol = market_data["symbol"]
    df_daily = market_data["daily"]
    df_1h = market_data["1h"]
    df_15m = market_data.get("15m")
    df_5m = market_data.get("5m")
    atr_daily = market_data["atr_daily"]
    atr_1h = market_data["atr_1h"]
    atr_15m = market_data.get("atr_15m") or atr_1h
    atr_5m = market_data.get("atr_5m") or atr_1h

    now = datetime.now()

    # --- 1. Trend ---
    trend_daily = get_trend(df_daily, lookback=cfg.TREND_LOOKBACK_D1)
    trend_1h = get_trend(df_1h, lookback=cfg.TREND_LOOKBACK_1H)
    trends_aligned = trend_daily == trend_1h and trend_daily != "NEUTRAL"

    # --- 2. ATR filtry ---
    atr_ok, atr_reason = check_atr_filters(df_daily, atr_daily)

    # --- 3. Rezim trhu ---
    market_mode = detect_market_mode(df_1h, df_daily, atr_1h)

    # --- 4. Detekce urovne ---
    level_type, level_price, level_kind, level_strength = find_best_level(
        df_1h, df_daily, atr_1h, atr_daily
    )

    # --- 5. Predpoklady ---
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

    # --- 6. Obchodni model ---
    lp_ok, lp_direction, lp_type = check_all_false_breakouts(
        df_1h, level_type, level_price, atr_1h
    )
    bounce_ok, _ = check_bounce_model(
        df_1h, level_type or "RESISTANCE", level_price or 0, atr_1h
    )
    breakout_ok, _ = check_breakout_model(
        df_1h, level_type or "RESISTANCE", level_price or 0, atr_1h, trend_daily
    )

    # Signal podle priority
    if lp_ok and lp_direction:
        signal = lp_direction
        model_name = lp_type or "LP"
    elif bounce_ok:
        signal = "SHORT" if level_type == "RESISTANCE" else "LONG"
        model_name = "ODBOJ"
    elif breakout_ok:
        signal = "LONG" if level_type == "RESISTANCE" else "SHORT"
        model_name = "PROBOJ"
    elif trend_daily != "NEUTRAL":
        signal = "SHORT" if trend_daily == "DOWN" else "LONG"
        model_name = "TREND"
    elif market_mode["corridor_signal"] != "NEUTRAL":
        signal = market_mode["corridor_signal"]
        model_name = "REJNZ"
    else:
        signal = "SHORT" if trend_1h == "DOWN" else "LONG"
        model_name = "SLABY"

    # --- 7. Multi-timeframe potvrzeni ---
    mtf_confirmation = False
    mtf_details = []
    if level_type and level_price:
        for tf_name, df_tf, atr_tf in [
            ("15M", df_15m, atr_15m),
            ("5M", df_5m, atr_5m)
        ]:
            if df_tf is not None:
                ok, _ = check_bounce_model(df_tf, level_type, level_price, atr_tf)
                if ok:
                    mtf_confirmation = True
                    mtf_details.append(f"✅ BPU na {tf_name}")
                else:
                    mtf_details.append(f"❌ {tf_name}: BPU neni")

    # --- 8. Udalostni vstup (ceka na zavreni BPU2) ---
    bpu2_closed = False
    bpu2_tf = "N/A"
    for tf_name, df_tf, atr_tf in [
        ("5M", df_5m, atr_5m),
        ("15M", df_15m, atr_15m),
        ("1H", df_1h, atr_1h)
    ]:
        if df_tf is not None:
            closed, _ = check_bpu2_closed(df_tf, level_type, level_price, atr_tf)
            if closed:
                bpu2_closed = True
                bpu2_tf = tf_name
                break

    # Cas uzavreni obchodu
    if bpu2_closed:
        entry_time = now + timedelta(minutes=2)
        entry_time = entry_time.replace(second=0, microsecond=0)
        entry_note = f"BPU2 zavrel na {bpu2_tf} ✅"
    else:
        entry_time, _ = calculate_best_entry(now)
        entry_note = "Cekej na zavreni BPU2 ⏳"

    minutes_ahead = max(1, int((entry_time - now).total_seconds() / 60))

    # --- 9. Checklist ---
    checklist_result = check_entry_checklist(
        df_daily, df_1h, atr_daily, atr_1h, level_type, level_price, signal
    )

    # --- Podmínky a sila signalu ---
    conditions = {
        "trend_d1":       trend_daily != "NEUTRAL",
        "trend_1h":       trend_1h != "NEUTRAL",
        "trends_aligned": trends_aligned,
        "atr_ok":         atr_ok,
        "uroven":         level_type is not None,
        "sila_urovne":    (level_strength or 0) >= 2,
        "predpoklady":    pre_score >= 4,
        "model_ok":       model_name not in ["TREND", "REJNZ", "SLABY"],
        "checklist_ok":   checklist_result.get("score", 0) >= 4,
        "mtf_ok":         mtf_confirmation,
    }
    splneno = sum(conditions.values())
    celkem = len(conditions)

    if splneno >= cfg.SIGNAL_STRONG_MIN:
        signal_strength = "SILNY"
    elif splneno >= cfg.SIGNAL_MEDIUM_MIN:
        signal_strength = "STREDNI"
    elif splneno >= cfg.SIGNAL_WEAK_MIN:
        signal_strength = "SLABY"
    else:
        signal_strength = "VELMI SLABY"

    return signal, {
        # Zakladni info
        "symbol":           symbol,
        "signal_strength":  signal_strength,
        "model":            model_name,
        "recommended_model": recommended_model,
        # Trend
        "trend_daily":      trend_daily,
        "trend_1h":         trend_1h,
        "trends_aligned":   trends_aligned,
        # ATR
        "atr_ok":           atr_ok,
        "atr_reason":       atr_reason,
        "atr_daily":        round(atr_daily, 5),
        "atr_1h":           round(atr_1h, 5),
        # Uroven
        "level_found":      level_type is not None,
        "level_type":       level_type,
        "level_price":      level_price,
        "level_kind":       level_kind,
        "level_strength":   level_strength or 0,
        # Predpoklady
        "pre_score":        pre_score,
        "pre_details":      pre_details,
        # Rezim trhu
        "market_mode":      market_mode,
        # Checklist
        "checklist_result": checklist_result,
        # Podmínky
        "conditions":       conditions,
        "splneno":          splneno,
        "celkem":           celkem,
        # Cas
        "entry_time":       entry_time.strftime("%H:%M"),
        "minutes_ahead":    minutes_ahead,
        "signal_generated_at": now.strftime("%H:%M:%S"),
        # MTF
        "mtf_confirmation": mtf_confirmation,
        "mtf_details":      mtf_details,
        # BPU2
        "bpu2_closed":      bpu2_closed,
        "bpu2_tf":          bpu2_tf,
        "entry_note":       entry_note,
        # Data
        "last_close":       market_data["last_close"],
        "source":           market_data.get("source", "twelvedata"),
    }