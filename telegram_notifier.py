"""
telegram_notifier.py - Komunikace s Telegramem

Posila signaly, menu a notifikace.
Zprava je zjednodusena - jen co potrebujes k rozhodnuti.
"""

import requests
import config
from datetime import datetime


def send_message(text, reply_markup=None):
    """Posle textovou zpravu na Telegram"""
    url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": config.TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML"
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    try:
        response = requests.post(url, json=payload, timeout=10)
        return response.json()
    except Exception as e:
        print(f"Telegram chyba: {e}")
        return {}


def answer_callback(callback_query_id, text="OK"):
    """Odpovi na stisk tlacitka (zastaveni "loading" animace)"""
    url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/answerCallbackQuery"
    requests.post(url, json={"callback_query_id": callback_query_id, "text": text})


# ============================================================
# MENU
# ============================================================

def send_main_menu():
    keyboard = {
        "inline_keyboard": [
            [
                {"text": "🌍 Forex", "callback_data": "menu_forex"},
                {"text": "🪙 Krypto", "callback_data": "menu_crypto"}
            ],
            [
                {"text": "🥇 Komodity", "callback_data": "menu_commodities"},
                {"text": "📈 Indexy", "callback_data": "menu_indices"}
            ],
            [
                {"text": "📊 Statistiky", "callback_data": "stats"},
                {"text": "📋 Status", "callback_data": "status"}
            ],
            [
                {"text": "⛔ Stop", "callback_data": "stop"}
            ]
        ]
    }
    send_message("🤖 <b>Trading Bot</b>\n\nVyber co chces analyzovat:", keyboard)


def send_forex_menu():
    keyboard = {
        "inline_keyboard": [
            [
                {"text": "EUR/USD", "callback_data": "analyze_EUR/USD"},
                {"text": "GBP/USD", "callback_data": "analyze_GBP/USD"}
            ],
            [
                {"text": "EUR/JPY", "callback_data": "analyze_EUR/JPY"},
                {"text": "AUD/JPY", "callback_data": "analyze_AUD/JPY"}
            ],
            [
                {"text": "EUR/GBP", "callback_data": "analyze_EUR/GBP"},
                {"text": "GBP/JPY", "callback_data": "analyze_GBP/JPY"}
            ],
            [
                {"text": "USD/CHF", "callback_data": "analyze_USD/CHF"},
                {"text": "EUR/CAD", "callback_data": "analyze_EUR/CAD"}
            ],
            [
                {"text": "AUD/NZD", "callback_data": "analyze_AUD/NZD"},
                {"text": "USD/CNH", "callback_data": "analyze_USD/CNH"}
            ],
            [{"text": "⬅️ Zpět", "callback_data": "back_main"}]
        ]
    }
    send_message("🌍 <b>Forex</b>\n\nVyber par:", keyboard)


def send_crypto_menu():
    keyboard = {
        "inline_keyboard": [
            [
                {"text": "₿ BTC/USD", "callback_data": "analyze_BTC/USD"},
                {"text": "Ξ ETH/USD", "callback_data": "analyze_ETH/USD"}
            ],
            [
                {"text": "BNB/USD", "callback_data": "analyze_BNB/USD"},
                {"text": "SOL/USD", "callback_data": "analyze_SOL/USD"}
            ],
            [
                {"text": "XRP/USD", "callback_data": "analyze_XRP/USD"},
                {"text": "ADA/USD", "callback_data": "analyze_ADA/USD"}
            ],
            [
                {"text": "DOGE/USD", "callback_data": "analyze_DOGE/USD"},
                {"text": "DOT/USD", "callback_data": "analyze_DOT/USD"}
            ],
            [{"text": "⬅️ Zpět", "callback_data": "back_main"}]
        ]
    }
    send_message("🪙 <b>Krypto</b> (Binance)\n\nVyber symbol:", keyboard)


def send_commodities_menu():
    keyboard = {
        "inline_keyboard": [
            [
                {"text": "🥇 Zlato XAU/USD", "callback_data": "analyze_XAU/USD"},
                {"text": "🥈 Stribro XAG/USD", "callback_data": "analyze_XAG/USD"}
            ],
            [
                {"text": "🛢️ Ropa WTI", "callback_data": "analyze_WTI/USD"},
                {"text": "🛢️ Ropa Brent", "callback_data": "analyze_BRENT"}
            ],
            [{"text": "⬅️ Zpět", "callback_data": "back_main"}]
        ]
    }
    send_message("🥇 <b>Komodity</b>\n\nVyber:", keyboard)


def send_indices_menu():
    keyboard = {
        "inline_keyboard": [
            [
                {"text": "PMX", "callback_data": "analyze_PMX"},
                {"text": "LATAM", "callback_data": "analyze_LATAM"}
            ],
            [
                {"text": "IDX", "callback_data": "analyze_IDX"},
                {"text": "GSMI", "callback_data": "analyze_GSMI"}
            ],
            [{"text": "⬅️ Zpět", "callback_data": "back_main"}]
        ]
    }
    send_message("📈 <b>Indexy</b>\n\nVyber:", keyboard)


# ============================================================
# SIGNAL - zjednodusena zprava
# Jen co potrebujes k rozhodnuti - bez zbytecnych detailu
# ============================================================

def send_signal(symbol, signal, checklist):
    """
    Zprava signalu - citelna a strucna.
    Struktura:
    1. Symbol + smer (nejdulezitejsi)
    2. Cas uzavreni
    3. Sila + model
    4. Klicove podmínky (progress bar)
    5. Varování pokud je signal slaby
    """
    direction_emoji = "📉" if signal == "SHORT" else "📈"

    # Sila signalu
    strength = checklist.get("signal_strength", "")
    strength_map = {
        "SILNY":      "💪 SILNY",
        "STREDNI":    "👍 STREDNI",
        "SLABY":      "⚠️ SLABY",
        "VELMI SLABY": "🔴 VELMI SLABY"
    }
    strength_text = strength_map.get(strength, strength)

    # Progress bar podminek
    splneno = checklist.get("splneno", 0)
    celkem = checklist.get("celkem", 10)
    filled = int((splneno / celkem) * 8)
    progress = "█" * filled + "░" * (8 - filled)

    # Podmínky - jen ikony
    cond = checklist.get("conditions", {})
    def c(key): return "✅" if cond.get(key) else "❌"

    # BPU2 stav
    bpu2_emoji = "✅" if checklist.get("bpu2_closed") else "⏳"
    entry_note = checklist.get("entry_note", "")

    # MTF
    mtf_emoji = "✅" if checklist.get("mtf_confirmation") else "❌"

    # Rezim trhu
    mm = checklist.get("market_mode", {})
    mode = "REJNZ" if mm.get("is_range") else "TREND"
    parabolic = " ⚡PARABOLICKY" if mm.get("is_parabolic") else ""

    # Varovani
    warning = ""
    if strength in ["SLABY", "VELMI SLABY"]:
        warning = f"\n⚠️ <i>Slaby signal - obchoduj opatrne!</i>"
    if mm.get("is_parabolic") and signal == checklist.get("trend_daily"):
        warning += f"\n⚡ <i>Parabolicky pohyb - riziko odboje!</i>"

    # Predpoklady - max 2 radky
    pre_details = checklist.get("pre_details", [])
    pre_text = "\n".join(pre_details[:2]) if pre_details else ""

    keyboard = {
        "inline_keyboard": [
            [
                {"text": f"🔄 Znovu {symbol}", "callback_data": f"analyze_{symbol}"},
                {"text": "🏠 Menu", "callback_data": "back_main"}
            ],
            [
                {"text": "✅ Vyhral jsem", "callback_data": "result_win"},
                {"text": "❌ Prohrál jsem", "callback_data": "result_loss"}
            ]
        ]
    }

    basic_conditions = [
        f"{c('trend_d1')} D1:{checklist['trend_daily']}",
        f"{c('trend_1h')} 1H:{checklist['trend_1h']}",
        f"{c('atr_ok')} {checklist['atr_reason']}",
        f"{c('uroven')} Uroven:{checklist.get('level_kind', '?')} @ {checklist.get('level_price', '?')}",
        f"{mtf_emoji} MTF / {bpu2_emoji} BPU2:{entry_note}",
    ]

    message = (
        # Hlavicka - nejdulezitejsi info
        f"{direction_emoji} <b>{symbol} — {signal}</b>\n"
        f"⏰ Otevri HNED, zavre se v <b>{checklist['entry_time']}</b> "
        f"({checklist['minutes_ahead']} min)\n"
        f"{warning}\n\n"
        # Sila a model
        f"{strength_text} | {checklist.get('model')} | {mode}{parabolic}\n"
        f"Zakladni podminky:\n"
        f"{chr(10).join(basic_conditions)}\n"
    )

    # Predpoklady jen pokud jsou relevantni
    if pre_text:
        message += f"\n<i>{pre_text}</i>\n"

    message += (
        f"\n🕐 {checklist['signal_generated_at']} "
        f"|📡 {checklist.get('source','?').upper()} "
        f"|⚠️ {config.MODE.upper()}"
    )

    send_message(message, keyboard)