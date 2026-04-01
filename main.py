import time
import config
import requests
from data_fetcher import get_market_data
from analyzer import analyze_symbol
from telegram_notifier import (
    send_message, send_main_menu, send_forex_menu,
    send_indices_menu, send_commodities_menu, send_crypto_menu,
    send_signal, answer_callback
)
from datetime import datetime

daily_trades = 0
paused = False
last_update_id = None

def get_updates():
    global last_update_id
    url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/getUpdates"
    params = {"timeout": 3, "offset": last_update_id}
    try:
        response = requests.get(url, params=params, timeout=5).json()
        updates = response.get("result", [])
        if updates:
            last_update_id = updates[-1]["update_id"] + 1
        return updates
    except:
        return []

def handle_updates():
    global daily_trades, paused

    updates = get_updates()

    for update in updates:
        # Tlacitka (callback)
        if "callback_query" in update:
            cb = update["callback_query"]
            data = cb["data"]
            cb_id = cb["id"]
            answer_callback(cb_id)

            if data == "menu_forex":
                send_forex_menu()
            elif data == "menu_indices":
                send_indices_menu()
            elif data == "menu_commodities":
                send_commodities_menu()
            elif data == "menu_crypto":
                send_crypto_menu()
            elif data == "back_main":
                send_main_menu()
            elif data == "status":
                send_message(
                    f"📊 <b>Status bota</b>\n\n"
                    f"Signaly dnes: {daily_trades}/{config.MAX_TRADES_PER_DAY}\n"
                    f"Rezim: {config.MODE.upper()}\n"
                    f"Pauza: {'ANO' if paused else 'NE'}"
                )
            elif data == "stop":
                paused = True
                send_message("⏸️ Bot pozastaven.\n\nPro obnoveni posli /start nebo otevri menu.")
            elif data == "ready_next":
                paused = False
                send_message("✅ Super! Vyber co chces analyzovat:", )
                send_main_menu()
            elif data == "pause":
                paused = True
                send_message("⏸️ Pauza. Az budes pripraveny, posli /start")
            elif data.startswith("analyze_"):
                symbol = data.replace("analyze_", "")
                analyze_and_send(symbol)

        # Textove prikazy
        elif "message" in update:
            text = update["message"].get("text", "").strip()
            if text == "/start":
                paused = False
                send_main_menu()
            elif text == "/menu":
                send_main_menu()
            elif text == "/status":
                send_message(
                    f"📊 <b>Status bota</b>\n\n"
                    f"Signaly dnes: {daily_trades}/{config.MAX_TRADES_PER_DAY}\n"
                    f"Rezim: {config.MODE.upper()}\n"
                    f"Pauza: {'ANO' if paused else 'NE'}"
                )

def analyze_and_send(symbol):
    global daily_trades

    if daily_trades >= config.MAX_TRADES_PER_DAY:
        send_message(f"⛔ Denni limit {config.MAX_TRADES_PER_DAY} signalu dosazen!")
        return

    send_message(f"🔍 Analyzuji <b>{symbol}</b>... chvili strpeni")

    market_data = get_market_data(symbol)

    if market_data is None:
        send_message(
            f"❌ Symbol <b>{symbol}</b> neni dostupny na TwelveData.\n"
            f"Zkus jiny symbol."
        )
        send_main_menu()
        return

    signal, checklist = analyze_symbol(market_data)

    if signal:
        send_signal(symbol, signal, checklist)
        daily_trades += 1
    else:
        send_message(
            f"⚠️ <b>{symbol}</b> — zadny signal\n\n"
            f"Trend D1: {checklist['trend_daily']}\n"
            f"Trend 1H: {checklist['trend_1h']}\n"
            f"ATR ok: {'ANO' if checklist['atr_ok'] else 'NE'}\n"
            f"Uroven: {'Nalezena' if checklist['level_found'] else 'Nenalezena'}"
        )
        send_main_menu()

def main():
    global last_update_id

    print("Bot startuje...")

    # Vycisti stare updates
    url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/getUpdates"
    r = requests.get(url, params={"offset": -1}).json()
    if r.get("result"):
        last_update_id = r["result"][-1]["update_id"] + 1

    send_main_menu()
    print("Bot bezi! Ovladej pres Telegram. (Ctrl+C pro zastaveni)")

    while True:
        handle_updates()
        time.sleep(1)

if __name__ == "__main__":
    main()