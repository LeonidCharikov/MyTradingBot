import csv
import os
from datetime import datetime

LOG_FILE = "trades.csv"

def init_log():
    """Vytvori CSV soubor pokud neexistuje"""
    if not os.path.exists(LOG_FILE):
        with open(LOG_FILE, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "datum", "cas", "symbol", "signal",
                "model", "sila", "uroven", "level_kind",
                "atr_1h", "stop", "take", "rrr",
                "splneno_podminek", "vysledek"
            ])

def log_trade(symbol, signal, checklist, vysledek="?"):
    """
    Zaznam obchodu do CSV.
    vysledek = 'win', 'loss', 'skip', '?'
    """
    init_log()
    cl = checklist.get("checklist_result", {})
    now = datetime.now()

    row = [
        now.strftime("%Y-%m-%d"),
        now.strftime("%H:%M:%S"),
        symbol,
        signal,
        checklist.get("model", "?"),
        checklist.get("signal_strength", "?"),
        checklist.get("level_price", "?"),
        checklist.get("level_kind", "?"),
        checklist.get("atr_1h", "?"),
        cl.get("stop", "?"),
        cl.get("take", "?"),
        cl.get("rrr", "?"),
        checklist.get("splneno", "?"),
        vysledek
    ]

    with open(LOG_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(row)

def get_stats():
    """Vypocita statistiky z CSV"""
    if not os.path.exists(LOG_FILE):
        return "Zadne obchody v logu."

    wins = 0
    losses = 0
    skips = 0
    models = {}

    with open(LOG_FILE, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            v = row.get("vysledek", "?")
            if v == "win":
                wins += 1
            elif v == "loss":
                losses += 1
            elif v == "skip":
                skips += 1

            model = row.get("model", "?")
            if model not in models:
                models[model] = {"win": 0, "loss": 0}
            if v in ["win", "loss"]:
                models[model][v] += 1

    total = wins + losses
    winrate = round(wins / total * 100, 1) if total > 0 else 0

    stats = (
        f"📊 <b>Statistiky obchodu</b>\n\n"
        f"Celkem: {total} | ✅ {wins} | ❌ {losses}\n"
        f"Winrate: {winrate}%\n\n"
        f"<b>Podle modelu:</b>\n"
    )

    for model, data in models.items():
        t = data["win"] + data["loss"]
        wr = round(data["win"] / t * 100, 1) if t > 0 else 0
        stats += f"{model}: {t} obchodu, {wr}% WR\n"

    return stats