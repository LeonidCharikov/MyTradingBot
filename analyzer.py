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
    + Lozny proboj u urovne = zesiluje (+2)  <- NOVY
    """
    if level_price is None:
        return 0

    strength = 0
    tolerance = atr * 0.1
    highs = df["high"].values
    lows = df["low"].values
    closes = df["close"].values
    opens = df["open"].values

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

    # LP u urovne = zesiluje (z PDF)
    # Hledame bar ktery prorazil uroven ale zavrel zpet
    max_depth = atr / 3  # 1/3 ATR
    lp_found = False
    for i in range(len(highs) - 1):
        if level_type == "RESISTANCE":
            # Bar prorazil nahoru ale zavrel zpet dolu
            prorazil = highs[i] > level_price + tolerance
            zavrel_zpet = closes[i] < level_price
            hloubka_ok = (highs[i] - level_price) < max_depth
            if prorazil and zavrel_zpet and hloubka_ok:
                lp_found = True
                break
        else:
            # Bar prorazil dolu ale zavrel zpet nahoru
            prorazil = lows[i] < level_price - tolerance
            zavrel_zpet = closes[i] > level_price
            hloubka_ok = (level_price - lows[i]) < max_depth
            if prorazil and zavrel_zpet and hloubka_ok:
                lp_found = True
                break

    if lp_found:
        strength += 2

    return strength


def detect_historical_level(df_1h, df_daily, atr):
    """
    Historický level (z PDF):
    - Klíčové body s opakující se cenou
    - Cena se k nim opakovaně vrací
    """
    tolerance = atr * 0.08
    highs_1h = df_1h["high"].tail(50).values
    lows_1h = df_1h["low"].tail(50).values
    closes_1h = df_1h["close"].tail(50).values
    last_close = closes_1h[-1]

    # Hledame cenu kde se cena opakovala vicekrat (min 4x)
    # Resistance - opakujici se highy
    for i in range(len(highs_1h) - 5, 5, -1):
        level = highs_1h[i]
        repeats = sum(abs(highs_1h - level) < tolerance)
        if repeats >= 4:
            if abs(last_close - level) < atr * 0.5:
                return "RESISTANCE", round(level, 5), "HISTORICAL"

    # Support - opakujici se lows
    for i in range(len(lows_1h) - 5, 5, -1):
        level = lows_1h[i]
        repeats = sum(abs(lows_1h - level) < tolerance)
        if repeats >= 4:
            if abs(last_close - level) < atr * 0.5:
                return "SUPPORT", round(level, 5), "HISTORICAL"

    return None, None, None


def detect_consolidation_level(df_1h, atr):
    """
    Úroveň proторговky (z PDF):
    - Podobné historickým levelům
    - Zóna kde se cena zdržovala (konsolidovala)
    - Při návratu do této zóny = pravděpodobný odraz
    """
    tolerance = atr * 0.15
    highs = df_1h["high"].tail(50).values
    lows = df_1h["low"].tail(50).values
    closes = df_1h["close"].tail(50).values
    last_close = closes[-1]

    # Hledame zonu kde bylo hodne baru (konsolidace)
    for i in range(len(closes) - 10, 5, -1):
        zone_center = closes[i]
        # Pocet baru v teto zone
        bars_in_zone = sum(
            abs(closes[max(0, i-15):i] - zone_center) < tolerance
        )
        if bars_in_zone >= 6:
            # Cena se vraci do teto zony
            if abs(last_close - zone_center) < tolerance * 2:
                if last_close > zone_center:
                    return "RESISTANCE", round(zone_center + tolerance, 5), "PROТОРГОВКА"
                else:
                    return "SUPPORT", round(zone_center - tolerance, 5), "PROТОРГОВКА"

    return None, None, None


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

    lt, lp, ltype = detect_historical_level(df_1h, df_daily, atr_1h)
    if lt:
        return lt, lp, ltype, count_level_strength(lt, lp, df_1h, atr_1h)

    lt, lp, ltype = detect_consolidation_level(df_1h, atr_1h)
    if lt:
        return lt, lp, ltype, count_level_strength(lt, lp, df_1h, atr_1h)

    # Nove
    lt, lp, ltype = detect_technical_pullback(df_1h, atr_1h)
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

    # 8. Po LP neni odraz = silny predpoklad proboje
    lp_ok_1, _ = check_false_breakout_1bar(df_1h, level_type, level_price, atr_1h)
    lp_ok_2, _ = check_false_breakout_2bars(df_1h, level_type, level_price, atr_1h)

    if lp_ok_1 or lp_ok_2:
        # Je LP ale cena neklesla zpet = pravděpodobný průraz
        bars = df_1h.tail(5)
        last_close = bars["close"].iloc[-1]
        if level_type == "RESISTANCE" and last_close > level_price * 0.999:
            score += 2
            details.append("✅ Po LP neni odraz - pravdep. proboj")
        elif level_type == "SUPPORT" and last_close < level_price * 1.001:
            score += 2
            details.append("✅ Po LP neni odraz - pravdep. proboj")

    return max(score, 0), details

# ============================================================
# CHECKLIST PRED VSTUPEM
# Z PDF: tejk max 40% zapasu hodu a 60% ATR
# ============================================================

def check_entry_checklist(df_daily, df_1h, atr_daily, atr_1h, level_type, level_price, signal):
    """
    Finalni checklist pred vstupem (z PDF):
    - Stop za ocasem denni svicky (prirodzeny stop)
    - Tejk max 40% zapasu hodu a 60% ATR
    - RRR aspon 1:1
    """
    results = {}
    score = 0

    if level_price is None:
        return {"score": 0, "details": [], "rrr": 0, "stop": 0, "take": 0}

    # Stop za ocasem denni svicky (z PDF) - misto fixniho ATR stopu
    stop_distance, stop_note = calculate_stop_behind_tail(
        df_daily, level_type, atr_daily
    )
    results["stop"] = round(stop_distance, 5)
    results["stop_note"] = stop_note

    # Zapas hodu
    zapas_hodu = atr_daily * 2
    results["zapas_hodu"] = round(zapas_hodu, 5)

    # Tejk = minimum z (40% zapasu) a (60% ATR)
    take_profit = min(
        zapas_hodu * cfg.CHECKLIST_TAKE_MAX_ZAPAS,
        atr_daily * cfg.CHECKLIST_TAKE_MAX_ATR
    )
    results["take"] = round(take_profit, 5)

    # RRR
    results["rrr"] = round(
        take_profit / stop_distance, 2
    ) if stop_distance > 0 else 0

    details = []

    # 1. Smer D1 a 1H souhlasi
    trend_d1 = get_trend_ema(df_daily)
    trend_1h = get_trend_ema(df_1h)
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

    # 6. Stop za ocasem - bonus bod
    if "ocasem" in stop_note:
        score += 1
        details.append(f"✅ {stop_note}")
    else:
        details.append(f"➖ {stop_note}")

    results["score"] = score
    results["max_score"] = 9
    results["details"] = details

    return results


def check_order_cancellation(df_1h, level_type, level_price, atr):
    """
    Zrušení limitního příkazu (z PDF):
    - Příkaz zrušit pokud instrument odešel
      a zavřel se na vzdálenosti 2 stopů od úrovně
    - Stop = 1.5x ATR
    - 2 stopy = 3x ATR

    Vraci True = ZRUSIT příkaz (nevstupovat)
    """
    two_stops = atr * cfg.CHECKLIST_STOP_MULT * 2  # 2x stop = 3x ATR

    last_close = df_1h["close"].iloc[-1]
    dist_from_level = abs(last_close - level_price)

    if dist_from_level > two_stops:
        return True, f"Cena 2 stopy od urovne ({round(dist_from_level, 5)})"

    return False, "Vzdalenost OK"

# ============================================================
# EMA - stabilnejsi trend
# ============================================================

def get_ema(df, period):
    """Exponencialni klouzavy prumer - mene citlivy na sum nez SMA"""
    return df["close"].ewm(span=period, adjust=False).mean()

def get_trend_ema(df):
    """
    Trend podle EMA krizeni (z PDF logika):
    EMA8 > EMA21 = UP trend
    EMA8 < EMA21 = DOWN trend
    Kombinuje s polohou ceny vuci EMA
    """
    if len(df) < cfg.EMA_SLOW + 5:
        return get_trend(df)  # Fallback na puvodni funkci

    ema_fast = get_ema(df, cfg.EMA_FAST)
    ema_slow = get_ema(df, cfg.EMA_SLOW)
    last_close = df["close"].iloc[-1]

    ema_fast_last = ema_fast.iloc[-1]
    ema_slow_last = ema_slow.iloc[-1]

    # Smer EMA krizeni
    if ema_fast_last > ema_slow_last:
        ema_trend = "UP"
    elif ema_fast_last < ema_slow_last:
        ema_trend = "DOWN"
    else:
        ema_trend = "NEUTRAL"

    # Poloha ceny vuci EMA (potvrzeni)
    if last_close > ema_fast_last and ema_trend == "UP":
        return "UP"
    elif last_close < ema_fast_last and ema_trend == "DOWN":
        return "DOWN"
    elif ema_trend != "NEUTRAL":
        return ema_trend
    else:
        return get_trend(df)  # Fallback

# ============================================================
# CASOVE FILTRY - London/NY session
# ============================================================

def check_trading_session():
    """
    Kontroluje zda jsme v aktivni obchodni session.
    Forex ma nejlepsi volatilitu behem London a NY session.
    O vikendu jsou forex trhy zavreny - pouze OTC pary.
    UTC cas.
    """
    if not cfg.SESSION_FILTER_ENABLED:
        return True, "Filter vypnut"

    now_utc = datetime.utcnow()
    hour = now_utc.hour
    weekday = now_utc.weekday()  # 0=Pondeli, 5=Sobota, 6=Nedele

    # Vikend - forex trhy zavreny
    if cfg.WEEKEND_FILTER_ENABLED and weekday >= 5:
        day_name = "Sobota" if weekday == 5 else "Nedele"
        return False, f"{day_name} - forex zavreny, jen OTC"

    # Pondeli rano - trhy se teprve oteviraji (od 00:00 do 07:00 UTC)
    if weekday == 0 and hour < 7:
        return False, "Pondeli rano - male likvidity"

    # Patek vecer - trhy se zaviraji (po 21:00 UTC)
    if weekday == 4 and hour >= 21:
        return False, "Patek vecer - trhy se zaviraji"

    # Aktivni session
    in_london = cfg.SESSION_LONDON_START <= hour < cfg.SESSION_LONDON_END
    in_ny = cfg.SESSION_NY_START <= hour < cfg.SESSION_NY_END

    if in_london and in_ny:
        return True, "London+NY overlap (nejlepsi)"
    elif in_london:
        return True, "London session"
    elif in_ny:
        return True, "NY session"
    else:
        # Asijska session - nizka volatilita pro forex
        return False, f"Mimo session (UTC {hour}:00)"

# ============================================================
# KORELACE PARU
# ============================================================

def check_correlation_warning(symbol):
    """
    Upozorni pokud obchodujes korelujici par.
    Korelujici pary = dvojnasobne riziko.
    """
    warnings = []
    for pair in cfg.CORRELATED_PAIRS:
        if symbol in pair:
            other = [p for p in pair if p != symbol]
            if other:
                warnings.append(other[0])
    if warnings:
        return True, f"Koreluje s: {', '.join(warnings)}"
    return False, ""

# ============================================================
# TECHNICKA ODRAZKA
# ============================================================

def detect_technical_pullback(df_1h, atr_1h):
    """
    Uroven technickeho odskoku (z PDF):
    GT se nemeni ale hrac zastavil trend.
    Cena se odrazila od urovne ale trend pokracuje.
    
    Detekce:
    - Cena delala higher highs/lower lows (trend)
    - Na jednom miste se zastavila a odrazila
    - Pak pokracovala v puvodnim smeru
    """
    bars = df_1h.tail(20)
    highs = bars["high"].values
    lows = bars["low"].values
    closes = bars["close"].values

    tolerance = atr_1h * 0.1

    # Hledame technicky pullback v uptrendu
    # Cena sla nahoru, odrazila se dolu, pak se vratila nahoru
    for i in range(5, len(closes) - 3):
        # Lokalni minimum (pullback v uptrendu)
        is_local_low = (lows[i] < lows[i-1] and
                       lows[i] < lows[i+1] and
                       lows[i] < lows[i-2])
        if is_local_low:
            level = lows[i]
            # Cena se vraci k teto urovni
            if abs(closes[-1] - level) < tolerance * 3:
                # Overeni ze pred tim byl uptrend
                pre_trend = closes[i-3] < closes[i-1]
                if pre_trend:
                    return "SUPPORT", round(level, 5), "TECH_PULLBACK"

    # Technicky pullback v downtrendu
    for i in range(5, len(closes) - 3):
        is_local_high = (highs[i] > highs[i-1] and
                        highs[i] > highs[i+1] and
                        highs[i] > highs[i-2])
        if is_local_high:
            level = highs[i]
            if abs(closes[-1] - level) < tolerance * 3:
                pre_trend = closes[i-3] > closes[i-1]
                if pre_trend:
                    return "RESISTANCE", round(level, 5), "TECH_PULLBACK"

    return None, None, None

# ============================================================
# NEDOBIJEJICI BARY
# ============================================================

def detect_non_hitting_bars(df_1h, level_type, level_price, atr_1h):
    """
    Nedobijejici bary (z PDF):
    Male bary pred limitnim hracem = nabrani pozice
    malymi hraci tesne pred uroven.
    Zesiluje uroven limitniho hrace.
    """
    if level_price is None:
        return False, 0

    tolerance = atr_1h * 0.1
    bars = df_1h.tail(10)
    overall_avg = (df_1h["high"] - df_1h["low"]).mean()

    non_hitting = 0
    for i in range(len(bars)):
        bar = bars.iloc[i]
        bar_size = bar["high"] - bar["low"]
        is_small = bar_size < overall_avg * 0.6  # Male bary

        if level_type == "RESISTANCE":
            # Bar jde k urovni ale nedobiha
            approaches = bar["high"] > level_price - tolerance * 3
            doesnt_hit = bar["high"] < level_price - tolerance * 0.5
            if is_small and approaches and doesnt_hit:
                non_hitting += 1
        else:
            approaches = bar["low"] < level_price + tolerance * 3
            doesnt_hit = bar["low"] > level_price + tolerance * 0.5
            if is_small and approaches and doesnt_hit:
                non_hitting += 1

    return non_hitting >= 2, non_hitting

# ============================================================
# FON V OPACNOU STRANU
# ============================================================

def detect_counter_market_background(df_1h, df_daily, signal):
    """
    Fon v opacnou stranu (z PDF):
    Instrument jde PROTI trhu = silnejsi odboj.
    
    Implementace: porovname smer 1H s smerem D1.
    Pokud 1H jde nahoru ale D1 je dolni trend = fon proti trhu.
    """
    trend_d1 = get_trend_ema(df_daily)
    trend_1h = get_trend_ema(df_1h)

    # Fon: 1H jde opacne nez D1
    if signal == "SHORT":
        # Shortujeme ale D1 je UP = jdeme proti D1 trendu
        counter = trend_d1 == "UP" and trend_1h in ["DOWN", "NEUTRAL"]
        if counter:
            return True, "Fon nahoru (D1 UP, shortujeme)"
    elif signal == "LONG":
        # Longujeme ale D1 je DOWN = jdeme proti D1 trendu
        counter = trend_d1 == "DOWN" and trend_1h in ["UP", "NEUTRAL"]
        if counter:
            return True, "Fon dolu (D1 DOWN, longujeme)"

    return False, ""

# ============================================================
# ZONA ZARAZENOSTI
# ============================================================

def detect_contamination_zone(df_1h, level_type, level_price, atr_1h):
    """
    Zona zarazenosti (z PDF):
    Oblast ZA uroven kde bylo hodne aktivity.
    Zesiluje pravdepodobnost odboje - velky hrac
    ma pozice za uroven a brani ji.
    """
    if level_price is None:
        return False, 0

    tolerance = atr_1h * 0.5  # Sirka zony zarazenosti
    bars = df_1h.tail(50)

    if level_type == "RESISTANCE":
        # Hledame aktivitu NAD uroven (za resistance)
        activity_above = sum(
            1 for _, row in bars.iterrows()
            if row["high"] > level_price and
               row["low"] < level_price + tolerance * 2
        )
        return activity_above >= 5, activity_above

    else:
        # Hledame aktivitu POD uroven (za support)
        activity_below = sum(
            1 for _, row in bars.iterrows()
            if row["low"] < level_price and
               row["high"] > level_price - tolerance * 2
        )
        return activity_below >= 5, activity_below

# ============================================================
# OBCHODOVANI V KANALU
# ============================================================

def detect_channel(df_1h, atr_1h):
    """
    Obchodovani v kanalu (z PDF):
    1. Identifikace hranic (globalni a lokalni)
    2. Sirka min 6-8 stopu
    3. Smer + vzdalenost + ATR
    4. Signal od hranice kanalu
    """
    bars = df_1h.tail(30)
    highs = bars["high"].values
    lows = bars["low"].values
    closes = bars["close"].values

    # Hranice kanalu
    channel_high = max(highs[-20:])
    channel_low = min(lows[-20:])
    channel_width = channel_high - channel_low

    # Min sirka = 6 stopu (stop = 1.5x ATR)
    min_width = atr_1h * cfg.CHECKLIST_STOP_MULT * cfg.CHANNEL_MIN_STOPS
    if channel_width < min_width:
        return None  # Prilis uzky kanal

    last_close = closes[-1]

    # Pozice v kanalu
    if channel_width > 0:
        position = (last_close - channel_low) / channel_width
    else:
        return None

    stop = atr_1h * cfg.CHECKLIST_STOP_MULT
    # Vzdalenost k protejsi strane
    dist_to_top = channel_high - last_close
    dist_to_bottom = last_close - channel_low

    # Signal od hranice (z PDF: min 2 stopy od protejsi strany)
    near_bottom = dist_to_bottom < atr_1h * 1.5
    near_top = dist_to_top < atr_1h * 1.5
    enough_space_up = dist_to_top > stop * 2
    enough_space_down = dist_to_bottom > stop * 2

    if near_bottom and enough_space_up:
        signal = "LONG"
        confidence = min(1.0, channel_width / min_width)
    elif near_top and enough_space_down:
        signal = "SHORT"
        confidence = min(1.0, channel_width / min_width)
    else:
        return None

    return {
        "signal": signal,
        "channel_high": round(channel_high, 5),
        "channel_low": round(channel_low, 5),
        "channel_width": round(channel_width, 5),
        "width_in_stops": round(channel_width / stop, 1),
        "position": round(position, 2),
        "confidence": round(confidence, 2)
    }

# ============================================================
# LP PREDPOKLADY NA 5M
# Kontroluje predpoklady LP přímo na kratkem timeframu
# ============================================================

def check_lp_prerequisites_5m(df_5m, level_type, level_price, atr_5m):
    """
    Predpoklady LP na 5M grafu (z PDF):
    - Pristup na velkych barech (pohyb k urovni byl silny)
    - Bezodrazove hnutí (bez pullbacku)
    - Rychlost pristupu (posledni bary velke)

    Vraci score 0-6 a detaily.
    """
    if df_5m is None or level_price is None or len(df_5m) < 10:
        return 0, []

    score = 0
    details = []
    bars = df_5m.tail(20)
    closes = bars["close"].values
    overall_avg = (df_5m["high"] - df_5m["low"]).mean()

    # 1. Pristup na velkych barech na 5M
    recent_size = (df_5m.tail(5)["high"] - df_5m.tail(5)["low"]).mean()
    if recent_size > overall_avg * 1.3:
        score += 2
        details.append("✅ 5M: Velke bary pri pristupu")
    else:
        details.append("❌ 5M: Male bary pri pristupu")

    # 2. Bezodrazove hnutí na 5M
    total_move = abs(closes[-1] - closes[0])
    if total_move > 0:
        if level_type == "RESISTANCE":
            pullbacks = [
                abs(closes[i] - closes[i-1])
                for i in range(1, len(closes))
                if closes[i] < closes[i-1]
            ]
        else:
            pullbacks = [
                abs(closes[i] - closes[i-1])
                for i in range(1, len(closes))
                if closes[i] > closes[i-1]
            ]
        max_pb = max(pullbacks) if pullbacks else 0
        if max_pb < total_move * 0.35:
            score += 2
            details.append("✅ 5M: Bezodrazove hnutí")
        else:
            details.append("❌ 5M: Hnutí s odskaky")

    # 3. Rychlost pristupu - posledni 3 bary
    last_3_size = (df_5m.tail(3)["high"] - df_5m.tail(3)["low"]).mean()
    if last_3_size > overall_avg * 1.5:
        score += 2
        details.append("✅ 5M: Rychly pristup")
    else:
        details.append("❌ 5M: Pomaly pristup")

    return score, details


# ============================================================
# PODJATI DETEKCE + VYROVNAVACI BAR
# Z PDF: Vozdrzet se pri podjati, po vyrovnavacim baru mozno
# ============================================================

def check_podjati(df, level_type, level_price, atr):
    """
    Podjatí (squeeze) = cena se tiskne k urovni
    malymi bary bez jasneho smeru.

    Z PDF:
    - Vozdrzet se pri podjati
    - Po vyrovnavacim baru (velky bar ktery prerusí konsolidaci)
      lze obchodovat

    Vraci:
    - "PODJATI": cena je v podjati - neobchodovat
    - "VYROVNAVACI": vyrovnavaci bar prave probehl - mozno vstoupit
    - "OK": zadne podjati
    """
    if level_price is None or len(df) < 8:
        return "OK", "Zadne podjati"

    bars = df.tail(10)
    overall_avg = (df["high"] - df["low"]).mean()
    tolerance = atr * 0.2

    # Detekce podjati: min 4 male bary u urovne
    small_bars_near = 0
    for i in range(len(bars) - 1):
        bar = bars.iloc[i]
        bar_size = bar["high"] - bar["low"]
        mid = (bar["high"] + bar["low"]) / 2
        is_small = bar_size < overall_avg * 0.6
        is_near = abs(mid - level_price) < tolerance * 2
        if is_small and is_near:
            small_bars_near += 1

    if small_bars_near < 4:
        return "OK", "Zadne podjati"

    # Je podjati - zkontroluj zda probehl vyrovnavaci bar
    last_bar = bars.iloc[-1]
    last_size = last_bar["high"] - last_bar["low"]
    is_big = last_size > overall_avg * 1.4

    if is_big:
        # Vyrovnavaci bar probehl - smer urcuje zda vstoupit
        if level_type == "RESISTANCE":
            # Vyrovnavaci bar smerem dolu = potvrzeni shortu
            is_bearish = last_bar["close"] < last_bar["open"]
            if is_bearish:
                return "VYROVNAVACI", "Vyrovnavaci bar dolu - mozno SHORT"
            else:
                return "PODJATI", "Vyrovnavaci bar nahoru - cekej"
        else:
            is_bullish = last_bar["close"] > last_bar["open"]
            if is_bullish:
                return "VYROVNAVACI", "Vyrovnavaci bar nahoru - mozno LONG"
            else:
                return "PODJATI", "Vyrovnavaci bar dolu - cekej"

    return "PODJATI", f"Podjati ({small_bars_near} malych baru) - cekej"


# ============================================================
# IMPULS PO PRURAZU
# Z PDF: Bez impulsu po prurazu = pravdepodobne LP
# ============================================================

def check_breakout_impulse(df, level_type, level_price, atr):
    """
    Kontroluje zda po prurazu urovne nasledoval impuls.

    Z PDF: "Pokud pri probiti silne urovne neni impuls
    pro pokracovani pohybu - pravdepodobnost vyssi ze je to LP"

    Impuls = velky bar ve smeru prurazu ihned po prurazu.

    Vraci:
    - True + duvod: impuls existuje = prurazu duveruj
    - False + duvod: bez impulsu = spis LP
    """
    if level_price is None or len(df) < 5:
        return False, "Malo dat"

    bars = df.tail(8)
    overall_avg = (df["high"] - df["low"]).mean()

    # Najdi bar ktery prorazil uroven
    breakout_idx = None
    for i in range(len(bars) - 2, 0, -1):
        bar = bars.iloc[i]
        if level_type == "RESISTANCE":
            if bar["close"] > level_price and bar["open"] < level_price:
                breakout_idx = i
                break
        else:
            if bar["close"] < level_price and bar["open"] > level_price:
                breakout_idx = i
                break

    if breakout_idx is None:
        return False, "Proboj nenalezen"

    # Zkontroluj bary po prurazu
    bars_after = bars.iloc[breakout_idx + 1:]
    if len(bars_after) == 0:
        return False, "Zadne bary po prurazu"

    # Hledame velky bar ve smeru prurazu
    for _, bar in bars_after.iterrows():
        bar_size = bar["high"] - bar["low"]
        is_big = bar_size > overall_avg * 1.2

        if level_type == "RESISTANCE":
            # Po prurazu nahoru - hledame bullish bar
            is_directional = bar["close"] > bar["open"]
            if is_big and is_directional:
                return True, f"Impuls nahoru po prurazu ✅"
        else:
            # Po prurazu dolu - hledame bearish bar
            is_directional = bar["close"] < bar["open"]
            if is_big and is_directional:
                return True, f"Impuls dolu po prurazu ✅"

    return False, "Bez impulsu - spis LP ⚠️"


# ============================================================
# ZAVRENI D1 PRESNE NA HIGH/LOW UROVNE
# Z PDF: "Zavreni D1 pod high/low NA UROVNI" = silny predpoklad
# ============================================================

def check_d1_close_at_level(df_daily, level_type, level_price, atr_daily):
    """
    Z PDF (strana 6): Zavreni D1 pod high/low NA UROVNI
    = silny predpoklad proboje.

    Presne pravidlo:
    - Pro RESISTANCE: D1 zavrel tesne POD high urovne
      (cena dosahla urovne ale nezavrela nad ni)
    - Pro SUPPORT: D1 zavrel tesne NAD low urovne

    Tolerance = 10% ATR
    """
    if level_price is None or len(df_daily) < 2:
        return False, "Malo dat"

    last = df_daily.iloc[-1]
    tolerance = atr_daily * 0.10  # Tesna tolerance - 10% ATR

    if level_type == "RESISTANCE":
        # Zavrel pod high urovne ale dosahl ji (high baru = uroven)
        high_at_level = abs(last["high"] - level_price) < tolerance
        closed_below = last["close"] < level_price
        closed_near = abs(last["close"] - level_price) < atr_daily * 0.3

        if high_at_level and closed_below and closed_near:
            return True, f"D1 high na urovni, zavrel pod ({round(last['close'], 5)})"
        return False, "D1 nezavrel presne na urovni"

    elif level_type == "SUPPORT":
        # Zavrel nad low urovne ale dosahl ji
        low_at_level = abs(last["low"] - level_price) < tolerance
        closed_above = last["close"] > level_price
        closed_near = abs(last["close"] - level_price) < atr_daily * 0.3

        if low_at_level and closed_above and closed_near:
            return True, f"D1 low na urovni, zavrel nad ({round(last['close'], 5)})"
        return False, "D1 nezavrel presne na urovni"

    return False, "Neznamy typ"


# ============================================================
# SILA ZADERGU
# Z PDF: Zaderg = rychle hnutí PROTI smeru pred vstupem
# Silny zaderg = lepsi vstupni signal
# ============================================================

def check_zaderg_strength(df, atr, signal):
    """
    Meri silu finalniho zadergu pred pohybem.

    Z PDF: "Pred finalnim pohybem instrument dela
    finalni zaderg - rezke hnutí PROTI"

    Sila zadergu:
    - SILNY: velky bar (>2x ATR) + rychly navrat
    - STREDNI: stredni bar (1.3-2x ATR) + navrat
    - SLABY nebo ZADNY: bar < 1.3x ATR

    Vraci: (ok, sila, detaily)
    """
    if len(df) < 5 or atr == 0:
        return False, "ZADNY", "Malo dat"

    bars = df.tail(6)
    overall_avg = (df["high"] - df["low"]).mean()

    # Hledame zaderg v poslednich 3 barech (ne posledni - ten je vstupni)
    for i in range(len(bars) - 3, len(bars) - 1):
        bar = bars.iloc[i]
        next_bar = bars.iloc[i + 1] if i + 1 < len(bars) else None
        bar_size = bar["high"] - bar["low"]
        size_ratio = bar_size / overall_avg if overall_avg > 0 else 0

        if signal == "LONG":
            # Zaderg DOLU pred longem
            is_against = bar["close"] < bar["open"]  # Bearish bar
            if is_against:
                # Kontrola ze nasledujici bar se vraci nahoru
                recovery = (
                    next_bar is not None and
                    next_bar["close"] > bar["close"]
                )
                if size_ratio >= 2.0 and recovery:
                    return True, "SILNY", f"Silny zaderg dolu ({round(size_ratio, 1)}x ATR)"
                elif size_ratio >= 1.3 and recovery:
                    return True, "STREDNI", f"Stredni zaderg dolu ({round(size_ratio, 1)}x ATR)"
                elif size_ratio >= 1.0:
                    return True, "SLABY", f"Slaby zaderg dolu ({round(size_ratio, 1)}x ATR)"

        elif signal == "SHORT":
            # Zaderg NAHORU pred shortem
            is_against = bar["close"] > bar["open"]  # Bullish bar
            if is_against:
                recovery = (
                    next_bar is not None and
                    next_bar["close"] < bar["close"]
                )
                if size_ratio >= 2.0 and recovery:
                    return True, "SILNY", f"Silny zaderg nahoru ({round(size_ratio, 1)}x ATR)"
                elif size_ratio >= 1.3 and recovery:
                    return True, "STREDNI", f"Stredni zaderg nahoru ({round(size_ratio, 1)}x ATR)"
                elif size_ratio >= 1.0:
                    return True, "SLABY", f"Slaby zaderg nahoru ({round(size_ratio, 1)}x ATR)"

    return False, "ZADNY", "Zaderg nenalezen"

def calculate_stop_behind_tail(df_daily, level_type, atr_daily):
    """
    STOP za ocasem denni svicky (z PDF):
    "STOP podle denního grafu = dobrá TVX (za ocas)"

    Misto fixniho stopu (1.5x ATR) pouzij ocas
    posledni denni svicky jako prirodzeny stop.

    Pro RESISTANCE: stop = nad high posledni denni svicky
    Pro SUPPORT: stop = pod low posledni denni svicky

    Pokud je ocas prilis maly (< 0.5x ATR) pouzij ATR stop.
    Pokud je ocas prilis velky (> 3x ATR) pouzij ATR stop.
    """
    if df_daily is None or len(df_daily) < 1:
        return atr_daily * cfg.CHECKLIST_STOP_MULT, "ATR stop (malo dat)"

    last = df_daily.iloc[-1]
    last_close = last["close"]

    if level_type == "RESISTANCE":
        # Ocas nahoru = vzdalenost od close do high
        tail = last["high"] - last_close
        stop_level = last["high"]
    else:
        # Ocas dolu = vzdalenost od low do close
        tail = last_close - last["low"]
        stop_level = last["low"]

    # Validace - ocas musi byt rozumny
    min_stop = atr_daily * 0.5
    max_stop = atr_daily * 3.0
    default_stop = atr_daily * cfg.CHECKLIST_STOP_MULT

    if tail < min_stop:
        # Prilis maly ocas - pouzij ATR stop
        return default_stop, f"ATR stop (maly ocas: {round(tail, 5)})"
    elif tail > max_stop:
        # Prilis velky ocas - pouzij ATR stop
        return default_stop, f"ATR stop (velky ocas: {round(tail, 5)})"
    else:
        # Pouzij ocas jako stop
        return tail, f"Stop za ocasem D1: {round(stop_level, 5)}"


def check_momentum_continuation(df_1h, df_daily, atr_daily):
    """
    Momentum model (z PDF):
    "Po silnem pohybu instrument neodrazuje =
    pohyb pravdepodobne pokracuje = vyborny vyber"

    Podmínky:
    1. Silny pohyb (min 3 velke bary jednim smerem)
    2. Bez vyrazneho odskoku po pohybu
    3. ATR ma stale prostor (< 75% pouzito)
    4. Denni model souhlasi (longova/shortova)

    Vraci: (signal, score, details)
    signal = "LONG"/"SHORT"/None
    """
    bars = df_1h.tail(10)
    closes = bars["close"].values
    highs = bars["high"].values
    lows = bars["low"].values
    overall_avg = (df_1h["high"] - df_1h["low"]).mean()

    score = 0
    details = []
    signal = None

    # 1. Silny pohyb - min 3 velke bary jednim smerem
    up_bars = 0
    down_bars = 0
    for i in range(len(bars) - 4, len(bars) - 1):
        bar = bars.iloc[i]
        bar_size = bar["high"] - bar["low"]
        is_big = bar_size > overall_avg * 1.3
        if is_big:
            if bar["close"] > bar["open"]:
                up_bars += 1
            else:
                down_bars += 1

    if up_bars >= 3:
        direction = "UP"
        score += 2
        details.append(f"✅ Silny pohyb nahoru ({up_bars} velkych baru)")
    elif down_bars >= 3:
        direction = "DOWN"
        score += 2
        details.append(f"✅ Silny pohyb dolu ({down_bars} velkych baru)")
    else:
        return None, 0, ["❌ Zadny silny pohyb"]

    # 2. Bez odskoku - posledni bar pokracuje ve smeru
    last = bars.iloc[-1]
    last_size = last["high"] - last["low"]
    if direction == "UP":
        no_pullback = last["close"] > last["open"]
        pullback_size = last["open"] - last["low"]
    else:
        no_pullback = last["close"] < last["open"]
        pullback_size = last["high"] - last["open"]

    if no_pullback:
        score += 2
        details.append("✅ Bez odskoku - pohyb pokracuje")
    else:
        details.append("❌ Odskok detekovan")

    # 3. ATR ma prostor
    daily_range = df_daily.iloc[-1]["high"] - df_daily.iloc[-1]["low"]
    if atr_daily > 0:
        atr_used = daily_range / atr_daily
        if atr_used < 0.75:
            score += 2
            details.append(f"✅ ATR prostor ({round(atr_used*100)}%)")
        else:
            details.append(f"❌ ATR vycerpan ({round(atr_used*100)}%)")
            return None, score, details  # Bez prostoru = neobchoduj

    # 4. Denni model souhlasi
    last_daily = df_daily.iloc[-1]
    daily_range_d = last_daily["high"] - last_daily["low"]
    if daily_range_d > 0:
        close_pos = (last_daily["close"] - last_daily["low"]) / daily_range_d
        if direction == "UP" and close_pos > 0.6:
            score += 1
            details.append("✅ Denni longova model")
        elif direction == "DOWN" and close_pos < 0.4:
            score += 1
            details.append("✅ Denni shortova model")
        else:
            details.append("❌ Denni model nesouhlasi")

    # Signal jen kdyz je score dostatecny
    if score >= 5:
        signal = "LONG" if direction == "UP" else "SHORT"

    return signal, score, details

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
    trend_daily = get_trend_ema(df_daily)
    trend_1h = get_trend_ema(df_1h)
    trends_aligned = trend_daily == trend_1h and trend_daily != "NEUTRAL"

    # --- 1b. Casova session ---
    session_ok, session_note = check_trading_session()

    # --- 1c. Korelace ---
    corr_warning, corr_note = check_correlation_warning(symbol)

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

    # --- 5b. Momentum model ---
    momentum_signal, momentum_score, momentum_details = check_momentum_continuation(
        df_1h, df_daily, atr_daily
    )

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

    # LP uroven existuje ale formace neni potvrzena
    # level_kind = typ urovne (LP, MIRROR, atd.)
    # lp_ok = zda je LP formace dokoncena (proboj + navrat)
    lp_level_exists = level_kind == "LP"
    lp_formation_confirmed = lp_ok

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
    elif momentum_signal:                    # NOVY
        signal = momentum_signal
        model_name = "MOMENTUM"
    elif trend_daily != "NEUTRAL":
        signal = "SHORT" if trend_daily == "DOWN" else "LONG"
        model_name = "TREND"
    elif market_mode["corridor_signal"] != "NEUTRAL":
        signal = market_mode["corridor_signal"]
        model_name = "REJNZ"
    else:
        signal = "SHORT" if trend_1h == "DOWN" else "LONG"
        model_name = "SLABY"

    # --- 6b. Rozsirene kontroly ---

    # LP predpoklady na 5M
    lp_5m_score, lp_5m_details = check_lp_prerequisites_5m(
        df_5m, level_type, level_price, atr_5m
    )

    # Podjati detekce - kontroluj na 5M nebo 1H
    df_check = df_5m if df_5m is not None else df_1h
    atr_check = atr_5m if df_5m is not None else atr_1h
    podjati_status, podjati_note = check_podjati(
        df_check, level_type, level_price, atr_check
    )

    # Impuls po prurazu - kontroluj na 5M ne 1H
    impulse_ok, impulse_note = check_breakout_impulse(
        df_5m if df_5m is not None else df_1h,
        level_type, level_price, atr_5m if df_5m is not None else atr_1h
    )

    # Zavreni D1 presne na high/low
    d1_at_level, d1_note = check_d1_close_at_level(
        df_daily, level_type, level_price, atr_daily
    )

    # Sila zadergu
    zaderg_ok, zaderg_strength, zaderg_note = check_zaderg_strength(
        df_5m if df_5m is not None else df_1h,
        atr_5m if df_5m is not None else atr_1h,
        signal
    )

    # Ostatni kontroly
    cancel_order, cancel_reason = check_order_cancellation(
        df_1h, level_type, level_price or 0, atr_1h
    )
    non_hitting_ok, non_hitting_count = detect_non_hitting_bars(
        df_1h, level_type, level_price, atr_1h
    )
    counter_bg, counter_note = detect_counter_market_background(
        df_1h, df_daily, signal
    )
    contam_ok, contam_count = detect_contamination_zone(
        df_1h, level_type, level_price, atr_1h
    )
    channel_data = detect_channel(df_1h, atr_1h)

    # LP level existuje ale formace neni potvrzena
    lp_level_exists = level_kind == "LP"
    lp_formation_confirmed = lp_ok

    # Pokud je podjati - signal je slabsi
    if podjati_status == "PODJATI":
        # Neblokujeme signal ale snizime silu
        pass  # Reseno pres podmínky nize

    # Kanal signal
    if channel_data and model_name in ["TREND", "REJNZ", "SLABY"]:
        signal = channel_data["signal"]
        model_name = "KANAL"

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
        "zaderg_ok":      zaderg_ok,
        "cancel_ok":      not cancel_order,
        "session_ok":     session_ok,
        "podjati_ok":     podjati_status != "PODJATI",  
        "impulse_ok":     impulse_ok,                   
        "d1_at_level":    d1_at_level,                  
        "lp_5m_ok":       lp_5m_score >= 3,
        "momentum_ok": momentum_score >= 5             
    }

    splneno = sum(conditions.values())
    celkem = len(conditions)

    # Minimalni prah
    if splneno < cfg.SIGNAL_MIN_CONDITIONS:
        signal = None
        signal_strength = "ZADNY"
    elif splneno >= cfg.SIGNAL_STRONG_MIN:
        signal_strength = "SILNY"
    elif splneno >= cfg.SIGNAL_MEDIUM_MIN:
        signal_strength = "STREDNI"
    elif splneno >= cfg.SIGNAL_WEAK_MIN:
        signal_strength = "SLABY"
    else:
        signal_strength = "VELMI SLABY"

    # LP uroven bez potvrzene formace = slabsi
    if lp_level_exists and not lp_formation_confirmed:
        if signal_strength == "SILNY":
            signal_strength = "STREDNI"

    # Podjati = sniz silu (ale ne u LP modelu)
    if podjati_status == "PODJATI" and model_name not in ["LP 1 BAR", "LP 2 BARY", "LP SLOZITY"]:
        if signal_strength in ["SILNY", "STREDNI"]:
            signal_strength = "SLABY"

    # Zruseni prikazu
    if cancel_order and signal is not None:
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
        # Data + session + korelace
        "last_close":       market_data["last_close"],
        "source":           market_data.get("source", "twelvedata"),
        "session_ok":       session_ok,
        "session_note":     session_note,
        "corr_warning":     corr_warning,
        "corr_note":        corr_note,
        # Rozsirene kontroly
        "non_hitting_ok":   non_hitting_ok,
        "non_hitting_count": non_hitting_count,
        "counter_bg":       counter_bg,
        "counter_note":     counter_note,
        "contam_ok":        contam_ok,
        "contam_count":     contam_count,
        "channel_data":     channel_data,
        "cancel_order":     cancel_order,
        "cancel_reason":    cancel_reason,
        # Zaderg
        "zaderg_ok":        zaderg_ok,
        "zaderg_strength":  zaderg_strength,
        "zaderg_note":      zaderg_note,
        # Nove funkce
        "lp_5m_score":      lp_5m_score,
        "lp_5m_details":    lp_5m_details,
        "podjati_status":   podjati_status,
        "podjati_note":     podjati_note,
        "impulse_ok":       impulse_ok,
        "impulse_note":     impulse_note,
        "d1_at_level":      d1_at_level,
        "d1_note":          d1_note,
        # Momentum
        "momentum_signal":  momentum_signal,
        "momentum_score":   momentum_score,
        "momentum_details": momentum_details,
        "stop_note":        checklist_result.get("stop_note", ""),
    }