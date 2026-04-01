import requests
import config
from datetime import datetime

def send_message(text, reply_markup=None):
    url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": config.TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML"
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    response = requests.post(url, json=payload)
    return response.json()

def send_main_menu():
    keyboard = {
        "inline_keyboard": [
            [
                {"text": "🌍 Forex", "callback_data": "menu_forex"},
                {"text": "📈 Indexy", "callback_data": "menu_indices"}
            ],
            [
                {"text": "🥇 Komodity", "callback_data": "menu_commodities"},
                {"text": "🪙 Krypto", "callback_data": "menu_crypto"}
            ],
            [
                {"text": "📊 Status bota", "callback_data": "status"},
                {"text": "⛔ Stop", "callback_data": "stop"}
            ]
        ]
    }
    send_message("🤖 <b>Trading Bot Menu</b>\n\nVyber kategorii:", keyboard)

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
            [
                {"text": "⬅️ Zpět", "callback_data": "back_main"}
            ]
        ]
    }
    send_message("🌍 <b>Forex páry</b>\n\nVyber pár:", keyboard)

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
            [
                {"text": "IMX", "callback_data": "analyze_IMX"},
                {"text": "ASIA", "callback_data": "analyze_ASIA"}
            ],
            [
                {"text": "⬅️ Zpět", "callback_data": "back_main"}
            ]
        ]
    }
    send_message("📈 <b>Indexy</b>\n\nVyber index:", keyboard)

def send_commodities_menu():
    keyboard = {
        "inline_keyboard": [
            [
                {"text": "🥇 Zlato XAU/USD", "callback_data": "analyze_XAU/USD"},
                {"text": "🥈 Stříbro XAG/USD", "callback_data": "analyze_XAG/USD"}
            ],
            [
                {"text": "🛢️ Ropa WTI", "callback_data": "analyze_WTI/USD"},
                {"text": "🛢️ Ropa Brent", "callback_data": "analyze_BRENT"}
            ],
            [
                {"text": "⬅️ Zpět", "callback_data": "back_main"}
            ]
        ]
    }
    send_message("🥇 <b>Komodity</b>\n\nVyber komoditu:", keyboard)

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
            [
                {"text": "⬅️ Zpět", "callback_data": "back_main"}
            ]
        ]
    }
    send_message("🪙 <b>Krypto</b> (via Binance - zdarma)\n\nVyber symbol:", keyboard)

def send_signal(symbol, signal, checklist):
    direction_emoji = "📉" if signal == "SHORT" else "📈"
    strength = checklist.get('signal_strength', '')
    if strength == "SILNY":
        strength_emoji = "💪"
    elif strength == "STREDNI":
        strength_emoji = "👍"
    elif strength == "SLABY":
        strength_emoji = "⚠️"
    else:
        strength_emoji = "🔴"

    source = "Binance" if checklist.get('source') == "binance" else "TwelveData"
    cond = checklist.get('conditions', {})
    def c(key):
        return "✅" if cond.get(key) else "❌"

    splneno = checklist.get('splneno', 0)
    celkem = checklist.get('celkem', 10)
    filled = int((splneno / celkem) * 10)
    progress = "█" * filled + "░" * (10 - filled)

    # Predpoklady - prvni 3
    pre_details = checklist.get('pre_details', [])
    pre_text = "\n".join(pre_details[:3]) if pre_details else "N/A"

    # Checklist vysledky
    cl = checklist.get('checklist_result', {})
    stop = cl.get('stop', 'N/A')
    take = cl.get('take', 'N/A')
    rrr = cl.get('rrr', 'N/A')

    # Market mode
    mm = checklist.get('market_mode', {})
    mode_text = "REJNZ" if mm.get('is_range') else "TREND"
    daily_model = mm.get('daily_model', 'N/A')

    keyboard = {
        "inline_keyboard": [
            [
                {
                    "text": f"🔄 Opakovat {symbol}",
                    "callback_data": f"analyze_{symbol}"
                }
            ],
            [
                {
                    "text": "✅ Dalsi signal",
                    "callback_data": "ready_next"
                },
                {
                    "text": "⏸️ Pauza",
                    "callback_data": "pause"
                }
            ],
            [
                {
                    "text": "🏠 Menu",
                    "callback_data": "back_main"
                }
            ]
        ]
    }

    message = (
        f"{direction_emoji} <b>{symbol} — {signal}</b>\n"
        f"{strength_emoji} Sila: <b>{strength}</b> "
        f"| Model: <b>{checklist.get('model')}</b>\n\n"
        f"⏰ <b>Otevri HNED — zavre se v {checklist['entry_time']}</b>\n"
        f"⏱ Doba: {checklist['minutes_ahead']} min "
        f"| Stop: {stop} | Tejk: {take}\n"
        f"📊 RRR: 1:{rrr} "
        f"| Rezim: {mode_text} | D1 model: {daily_model}\n\n"
        f"<b>Podminky ({splneno}/{celkem}):</b>\n"
        f"{progress}\n"
        f"{c('trend_d1')} D1: {checklist['trend_daily']} "
        f"{c('trend_1h')} 1H: {checklist['trend_1h']} "
        f"{c('trendy_souhlasi')} Souhlasi\n"
        f"{c('atr_ok')} {checklist['atr_reason']}\n"
        f"{c('uroven_nalezena')} Uroven: "
        f"{checklist.get('level_kind','N/A')} "
        f"@ {checklist.get('level_price','N/A')} "
        f"(sila:{checklist.get('level_strength',0)})\n"
        f"{c('model_nalezen')} Model potvrzen\n"
        f"{c('predpoklady_ok')} Predpoklady: {checklist.get('pre_score',0)}b\n"
        f"{c('checklist_ok')} Checklist: {cl.get('score',0)}/8\n"
        f"{c('rrr_ok')} RRR ok\n\n"
        f"<b>Top predpoklady:</b>\n"
        f"{pre_text}\n\n"
        f"🕐 {checklist['signal_generated_at']} "
        f"| 📡 {source} "
        f"| ⚠️ {config.MODE.upper()}"
    )
    send_message(message, keyboard)
  
def answer_callback(callback_query_id, text="OK"):
    url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/answerCallbackQuery"
    requests.post(url, json={"callback_query_id": callback_query_id, "text": text})