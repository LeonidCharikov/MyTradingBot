"""
telegram_notifier.py - Komunikace s Telegramem

Posila signaly, menu a notifikace.
Zprava je zjednodusena - jen co potrebujes k rozhodnuti.
"""

import requests
import config
from datetime import datetime


def send_message(text, reply_markup=None):
    """Posle zpravu vsem povolenym uzivatelem"""
    # Podporuje jak jeden string tak seznam ID
    chat_ids = config.TELEGRAM_CHAT_ID
    if isinstance(chat_ids, str):
        chat_ids = [chat_ids]

    url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage"
    for chat_id in chat_ids:
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML"
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup
        try:
            requests.post(url, json=payload, timeout=10)
        except Exception as e:
            print(f"Telegram chyba pro {chat_id}: {e}")


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
            # EUR pary
            [
                {"text": "🇪🇺 EUR/USD 🇺🇸", "callback_data": "analyze_EUR/USD"},
                {"text": "🇪🇺 EUR/GBP 🇬🇧", "callback_data": "analyze_EUR/GBP"}
            ],
            [
                {"text": "🇪🇺 EUR/JPY 🇯🇵", "callback_data": "analyze_EUR/JPY"},
                {"text": "🇪🇺 EUR/CAD 🇨🇦", "callback_data": "analyze_EUR/CAD"}
            ],
            [
                {"text": "🇪🇺 EUR/AUD 🇦🇺", "callback_data": "analyze_EUR/AUD"},
                {"text": "🇪🇺 EUR/NZD 🇳🇿", "callback_data": "analyze_EUR/NZD"}
            ],
            # GBP pary
            [
                {"text": "🇬🇧 GBP/USD 🇺🇸", "callback_data": "analyze_GBP/USD"},
                {"text": "🇬🇧 GBP/JPY 🇯🇵", "callback_data": "analyze_GBP/JPY"}
            ],
            # AUD pary
            [
                {"text": "🇦🇺 AUD/JPY 🇯🇵", "callback_data": "analyze_AUD/JPY"},
                {"text": "🇦🇺 AUD/NZD 🇳🇿", "callback_data": "analyze_AUD/NZD"}
            ],
            [
                {"text": "🇦🇺 AUD/CHF 🇨🇭", "callback_data": "analyze_AUD/CHF"},
                {"text": "🇦🇺 AUD/USD 🇺🇸", "callback_data": "analyze_AUD/USD"}
            ],
            # USD pary
            [
                {"text": "🇺🇸 USD/JPY 🇯🇵", "callback_data": "analyze_USD/JPY"},
                {"text": "🇺🇸 USD/CHF 🇨🇭", "callback_data": "analyze_USD/CHF"}
            ],
            [
                {"text": "🇺🇸 USD/CNH 🇨🇳", "callback_data": "analyze_USD/CNH"},
                {"text": "🇺🇸 USD/CAD 🇨🇦", "callback_data": "analyze_USD/CAD"}
            ],
            # CAD + NZD pary
            [
                {"text": "🇨🇦 CAD/JPY 🇯🇵", "callback_data": "analyze_CAD/JPY"},
                {"text": "🇳🇿 NZD/JPY 🇯🇵", "callback_data": "analyze_NZD/JPY"}
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
    direction_emoji = "📉" if signal == "SHORT" else "📈"

    # Sila signalu
    strength = checklist.get("signal_strength", "")
    strength_map = {
        "SILNY":       "💪 SILNY",
        "STREDNI":     "👍 STREDNI",
        "SLABY":       "⚠️ SLABY",
        "VELMI SLABY": "🔴 VELMI SLABY"
    }
    strength_text = strength_map.get(strength, strength)

    # Podmínky
    cond = checklist.get("conditions", {})
    def c(key): return "✅" if cond.get(key) else "❌"
    splneno = checklist.get("splneno", 0)
    celkem = checklist.get("celkem", 0)

    # Rezim trhu
    mm = checklist.get("market_mode", {})
    mode = "REJNZ" if mm.get("is_range") else "TREND"
    parabolic = " ⚡PARABOLA" if mm.get("is_parabolic") else ""

    # BPU2 + MTF
    bpu2_emoji = "✅" if checklist.get("bpu2_closed") else "⏳"
    mtf_emoji = "✅" if checklist.get("mtf_confirmation") else "❌"

    # Doplnkove podmínky
    contam_emoji = "✅" if checklist.get("contam_ok") else "➖"
    non_hit_emoji = "✅" if checklist.get("non_hitting_ok") else "➖"

    # Nove emojis
    podjati = checklist.get("podjati_status", "OK")
    if podjati == "PODJATI":
        podjati_emoji = "🚫"
    elif podjati == "VYROVNAVACI":
        podjati_emoji = "✅"
    else:
        podjati_emoji = "➖"

    zaderg_strength = checklist.get("zaderg_strength", "ZADNY")
    zaderg_map = {
        "SILNY":   "💪",
        "STREDNI": "👍",
        "SLABY":   "⚠️",
        "ZADNY":   "➖"
    }
    zaderg_emoji = zaderg_map.get(zaderg_strength, "➖")

    impulse_emoji = "✅" if checklist.get("impulse_ok") else "➖"
    d1_emoji = "✅" if checklist.get("d1_at_level") else "➖"
    lp_5m_ok = checklist.get("lp_5m_score", 0) >= 3
    lp_5m_emoji = "✅" if lp_5m_ok else "➖"

    # Predpoklady - max 2
    pre_details = checklist.get("pre_details", [])
    pre_text = "\n".join(pre_details[:2]) if pre_details else ""

    # LP 5M detaily
    lp_5m_details = checklist.get("lp_5m_details", [])
    lp_5m_text = "\n".join(lp_5m_details[:2]) if lp_5m_details and lp_5m_ok else ""

    # Varovani - definuj PRED pouzitim
    warnings = []

    # Extremni den
    atr_reason = checklist.get("atr_reason", "")
    if "%" in atr_reason:
        try:
            atr_pct = int(atr_reason.split("(")[1].split("%")[0])
            if atr_pct > 70:
                warnings.append(f"⚡ Extremni den ({atr_pct}% ATR)")
        except:
            pass

    if checklist.get("corr_warning"):
        warnings.append(f"⚠️ Koreluje s: {checklist.get('corr_note','')}")
    if not checklist.get("session_ok", True):
        warnings.append(f"🕐 {checklist.get('session_note','Mimo session')}")
    if checklist.get("cancel_order"):
        warnings.append(f"🚫 ZRUS PRIKAZ: {checklist.get('cancel_reason','')}")
    if mm.get("is_parabolic"):
        warnings.append("⚡ Parabolicky pohyb - riziko odboje")
    if podjati == "PODJATI":
        warnings.append(f"🚫 PODJATI - {checklist.get('podjati_note','')} - NEobchoduj!")
    elif podjati == "VYROVNAVACI":
        warnings.append(f"✅ {checklist.get('podjati_note','')}")

    warning_text = "\n".join(warnings)

    # Kanal
    channel_data = checklist.get("channel_data")
    channel_text = ""
    if channel_data:
        channel_text = (
            f"📊 Kanal: {channel_data['channel_low']} — "
            f"{channel_data['channel_high']} "
            f"({channel_data['width_in_stops']} stopu)\n"
        )

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

    message = (
        f"{direction_emoji} <b>{symbol} — {signal}</b>\n"
        f"⏰ Zavre se v <b>{checklist['entry_time']}</b> "
        f"({checklist['minutes_ahead']} min)\n"
    )

    if warning_text:
        message += f"{warning_text}\n"

    message += (
        f"\n"
        f"{strength_text} | {checklist.get('model')}{parabolic} | "
        f"{splneno}/{celkem}\n"
        f"\n"
        f"{c('trend_d1')} D1:{checklist['trend_daily']}  "
        f"{c('trend_1h')} 1H:{checklist['trend_1h']}  "
        f"{c('atr_ok')} ATR:{checklist.get('atr_reason','?')}\n"
        f"{c('uroven')} {checklist.get('level_kind','?')} "
        f"🛡️ {checklist.get('stop_note', '')}\n"
        f"@ {checklist.get('level_price','?')} "
        f"(sila:{checklist.get('level_strength',0)})\n"
        f"{mtf_emoji} MTF  "
        f"{bpu2_emoji} BPU2  "
        f"{podjati_emoji} Podjati  "
        f"{zaderg_emoji} Zaderg({zaderg_strength})\n"
        f"{impulse_emoji} Impuls  "
        f"{d1_emoji} D1@uroven  "
        f"{lp_5m_emoji} LP5M  "
        f"{contam_emoji} Zona  "
        f"{non_hit_emoji} Nedobij\n"
    )

    if channel_text:
        message += channel_text

    if pre_text:
        message += f"\n<i>{pre_text}</i>\n"

    if lp_5m_text:
        message += f"<i>{lp_5m_text}</i>\n"

    # Momentum detaily - jen kdyz je model MOMENTUM
    if checklist.get("model") == "MOMENTUM":
        momentum_details = checklist.get("momentum_details", [])
        if momentum_details:
            m_text = "\n".join(momentum_details[:2])
            message += f"\n<i>{m_text}</i>\n"

    message += f"\n🕐 {checklist['signal_generated_at']}"

    send_message(message, keyboard)