"""
trade_logger.py - Logovani obchodu do CSV

Zaznamenava: datum, cas, symbol, signal, model, sila,
uroven, ATR, podmínky, vysledek.
Umoznuje analyzu winrate podle modelu, symbolu, session.
"""

import csv
import os
from datetime import datetime

LOG_FILE = "trades.csv"

# Pamet posledniho obchodu pro aktualizaci vysledku
_last_trade_row = None
_last_trade_index = None


def init_log():
    """Vytvori CSV soubor pokud neexistuje"""
    if not os.path.exists(LOG_FILE):
        with open(LOG_FILE, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "datum", "cas", "symbol", "signal",
                "model", "sila", "uroven_cena", "uroven_typ",
                "atr_1h", "podminek_splneno", "podminek_celkem",
                "session", "vysledek"
            ])


def log_trade(symbol, signal, checklist):
    """Zaznam noveho obchodu do CSV"""
    global _last_trade_index
    init_log()

    mm = checklist.get("market_mode", {})
    session = checklist.get("session_note", "?")

    row = [
        datetime.now().strftime("%Y-%m-%d"),
        datetime.now().strftime("%H:%M:%S"),
        symbol,
        signal,
        checklist.get("model", "?"),
        checklist.get("signal_strength", "?"),
        checklist.get("level_price", "?"),
        checklist.get("level_kind", "?"),
        checklist.get("atr_1h", "?"),
        checklist.get("splneno", "?"),
        checklist.get("celkem", "?"),
        session,
        "?"   # Vysledek - bude doplnen pozdeji
    ]

    with open(LOG_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(row)

    # Zapamatuj index posledniho radku
    with open(LOG_FILE, "r", encoding="utf-8") as f:
        _last_trade_index = sum(1 for _ in f) - 1

    return _last_trade_index


def update_last_result(vysledek):
    """
    Aktualizuje vysledek posledniho obchodu.
    vysledek = 'win' nebo 'loss'
    """
    global _last_trade_index
    if _last_trade_index is None:
        return False

    # Nacti vsechny radky
    try:
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            rows = list(csv.reader(f))

        # Aktualizuj posledni radek
        if _last_trade_index < len(rows):
            rows[_last_trade_index][-1] = vysledek

        # Zapis zpet
        with open(LOG_FILE, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerows(rows)

        return True
    except Exception as e:
        print(f"Chyba aktualizace vysledku: {e}")
        return False


def get_stats():
    """Vypocita a vrati statistiky jako formatovany text"""
    if not os.path.exists(LOG_FILE):
        return "📊 Zatim zadne obchody v logu."

    rows = []
    try:
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = [r for r in reader]
    except Exception as e:
        return f"Chyba cteni logu: {e}"

    if not rows:
        return "📊 Zatim zadne obchody v logu."

    # Zakladni statistiky
    total = len(rows)
    wins = sum(1 for r in rows if r.get("vysledek") == "win")
    losses = sum(1 for r in rows if r.get("vysledek") == "loss")
    pending = sum(1 for r in rows if r.get("vysledek") == "?")
    evaluated = wins + losses
    winrate = round(wins / evaluated * 100, 1) if evaluated > 0 else 0

    # Statistiky podle modelu
    models = {}
    for r in rows:
        model = r.get("model", "?")
        v = r.get("vysledek", "?")
        if model not in models:
            models[model] = {"win": 0, "loss": 0}
        if v == "win":
            models[model]["win"] += 1
        elif v == "loss":
            models[model]["loss"] += 1

    # Statistiky podle symbolu
    symbols = {}
    for r in rows:
        sym = r.get("symbol", "?")
        v = r.get("vysledek", "?")
        if sym not in symbols:
            symbols[sym] = {"win": 0, "loss": 0}
        if v == "win":
            symbols[sym]["win"] += 1
        elif v == "loss":
            symbols[sym]["loss"] += 1

    # Statistiky podle sily signalu
    strengths = {}
    for r in rows:
        sila = r.get("sila", "?")
        v = r.get("vysledek", "?")
        if sila not in strengths:
            strengths[sila] = {"win": 0, "loss": 0}
        if v == "win":
            strengths[sila]["win"] += 1
        elif v == "loss":
            strengths[sila]["loss"] += 1

    # Sestaveni zpravy
    text = (
        f"📊 <b>Statistiky obchodu</b>\n\n"
        f"Celkem: {total} | ✅ {wins} | ❌ {losses} | ⏳ {pending}\n"
        f"Winrate: <b>{winrate}%</b> ({evaluated} vyhodnocenych)\n\n"
    )

    # Podle modelu
    text += "<b>Podle modelu:</b>\n"
    for model, data in sorted(models.items()):
        t = data["win"] + data["loss"]
        if t == 0:
            continue
        wr = round(data["win"] / t * 100, 1)
        bar = "█" * int(wr / 10) + "░" * (10 - int(wr / 10))
        text += f"{model}: {bar} {wr}% ({t} obchodu)\n"

    # Podle sily
    text += "\n<b>Podle sily signalu:</b>\n"
    strength_order = ["SILNY", "STREDNI", "SLABY", "VELMI SLABY"]
    for sila in strength_order:
        data = strengths.get(sila, {"win": 0, "loss": 0})
        t = data["win"] + data["loss"]
        if t == 0:
            continue
        wr = round(data["win"] / t * 100, 1)
        text += f"{sila}: {wr}% ({t} obchodu)\n"

    # Podle symbolu - jen top 5
    text += "\n<b>Top symboly:</b>\n"
    sym_sorted = sorted(
        symbols.items(),
        key=lambda x: x[1]["win"] + x[1]["loss"],
        reverse=True
    )[:5]
    for sym, data in sym_sorted:
        t = data["win"] + data["loss"]
        if t == 0:
            continue
        wr = round(data["win"] / t * 100, 1)
        text += f"{sym}: {wr}% ({t} obchodu)\n"

    return text