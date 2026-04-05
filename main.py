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
from datetime import datetime, date
import logging

logger = logging.getLogger(__name__)

daily_trades = 0
daily_losses = 0
paused = False
last_update_id = None
last_trade_date = date.today()

def reset_daily_if_needed():
    """Reset pocitadel o pulnoci"""
    global daily_trades, daily_losses, last_trade_date
    if date.today() != last_trade_date:
        logger.info("Novy den - resetuji pocitadla")
        daily_trades = 0
        daily_losses = 0
        last_trade_date = date.today()
        send_message(
            f"🌅 <b>Novy obchodni den</b>\n"
            f"Pocitadla resetovana.\n"
            f"Max signalu: {config.MAX_TRADES_PER_DAY}\n"
            f"Max ztrat: {config.MAX_DAILY_LOSSES}"
        )

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

def record_result(result):
    """
    Zaznam vysledku obchodu pro pocitani prekyrti.
    result = 'win' nebo 'loss'
    """
    global daily_losses, paused
    if result == "loss":
        daily_losses += 1
        logger.info(f"Ztrata #{daily_losses}/{config.MAX_DAILY_LOSSES}")

        if daily_losses >= config.MAX_DAILY_LOSSES:
            paused = True
            send_message(
                f"🛑 <b>STOP OBCHODOVANI!</b>\n\n"
                f"Dosahl jsi {config.MAX_DAILY_LOSSES} ztrat za den.\n"
                f"Podle algoritmu: analyzuj chyby!\n\n"
                f"Pro obnoveni zitra posli /start"
            )
        else:
            remaining = config.MAX_DAILY_LOSSES - daily_losses
            send_message(
                f"❌ Ztrata zaznamenana ({daily_losses}/{config.MAX_DAILY_LOSSES})\n"
                f"Zbyvajicich ztrat: {remaining}"
            )

def handle_updates():
    global daily_trades, paused

    reset_daily_if_needed()
    updates = get_updates()

    for update in updates:
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
                    f"Ztraty dnes: {daily_losses}/{config.MAX_DAILY_LOSSES}\n"
                    f"Rezim: {config.MODE.upper()}\n"
                    f"Pauza: {'ANO' if paused else 'NE'}\n"
                    f"Datum: {date.today()}"
                )
            elif data == "stop":
                paused = True
                send_message("⏸️ Bot pozastaven. /start pro obnoveni.")
            elif data == "ready_next":
                paused = False
                send_main_menu()
            elif data == "pause":
                paused = True
                send_message("⏸️ Pauza. /start pro obnoveni.")

            elif data == "result_win":
                from trade_logger import update_last_result
                update_last_result("win")
                send_message("✅ Vyhra zaznamenana!")
                send_main_menu()

            elif data == "result_loss":
                from trade_logger import update_last_result
                update_last_result("loss")
                record_result("loss")
                if not paused:
                    send_main_menu()

            elif data == "result_skip":
                send_message("⏭️ Signal preskocen.")
                send_main_menu()

            elif data.startswith("analyze_"):
                symbol = data.replace("analyze_", "")
                analyze_and_send(symbol)

            elif data == "stats":
                from trade_logger import get_stats
                send_message(get_stats())

        elif "message" in update:
            text = update["message"].get("text", "").strip()
            if text == "/start":
                paused = False
                reset_daily_if_needed()
                send_main_menu()
            elif text == "/menu":
                send_main_menu()
            elif text == "/status":
                send_message(
                    f"📊 <b>Status bota</b>\n\n"
                    f"Signaly dnes: {daily_trades}/{config.MAX_TRADES_PER_DAY}\n"
                    f"Ztraty dnes: {daily_losses}/{config.MAX_DAILY_LOSSES}\n"
                    f"Rezim: {config.MODE.upper()}\n"
                    f"Pauza: {'ANO' if paused else 'NE'}"
                )
            elif text == "/reset":
                daily_trades = 0
                daily_losses = 0
                send_message("🔄 Pocitadla manualne resetovana.")

# Globalni pamet poslednich signalu
last_signals = {}  # { symbol: { "signal": "SHORT", "time": datetime, "conditions": 10 } }

def analyze_and_send(symbol):
    global daily_trades, last_signals

    reset_daily_if_needed()

    if paused:
        send_message("⏸️ Bot je na pauze. /start pro obnoveni.")
        return

    if daily_trades >= config.MAX_TRADES_PER_DAY:
        send_message(f"⛔ Denni limit dosazen!")
        return

    if daily_losses >= config.MAX_DAILY_LOSSES:
        send_message(f"🛑 Denni limit ztrat dosazen!")
        return

    send_message(f"🔍 Analyzuji <b>{symbol}</b>...")

    market_data = get_market_data(symbol)
    if market_data is None:
        send_message(f"❌ <b>{symbol}</b> neni dostupny.")
        send_main_menu()
        return

    signal, checklist = analyze_symbol(market_data)

    # Zadny signal - pod minimem podminek
    if signal is None:
        splneno = checklist.get("splneno", 0)
        celkem = checklist.get("celkem", 0)
        send_message(
            f"⚪ <b>{symbol}</b> — zadny signal\n\n"
            f"Podmínky: {splneno}/{celkem}\n"
            f"Trend D1: {checklist.get('trend_daily')}\n"
            f"Trend 1H: {checklist.get('trend_1h')}\n"
            f"ATR: {checklist.get('atr_reason')}\n"
            f"Uroven: {'Nalezena' if checklist.get('level_found') else 'Nenalezena'}"
        )
        send_main_menu()
        return

    # Kontrola duplikatu - stejny signal jako pred max 10 minutami
    now = datetime.now()
    last = last_signals.get(symbol)
    if last:
        same_signal = last["signal"] == signal
        same_conditions = last["conditions"] == checklist.get("splneno", 0)
        time_diff = (now - last["time"]).total_seconds()

        if same_signal and same_conditions and time_diff < 600:
            send_message(
                f"⏭️ <b>{symbol}</b> — stejny signal jako pred "
                f"{int(time_diff/60)} min\n\n"
                f"Signal: {signal}\n"
                f"Zmen symbol nebo pockej na nova data."
            )
            send_main_menu()
            return

    # Uloz posledni signal
    last_signals[symbol] = {
        "signal": signal,
        "time": now,
        "conditions": checklist.get("splneno", 0)
    }

    send_signal(symbol, signal, checklist)
    from trade_logger import log_trade, init_log
    init_log()
    log_trade(symbol, signal, checklist)
    daily_trades += 1

def main():
    global last_update_id

    print("Bot startuje...")
    logger.info("Bot startuje")

    url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/getUpdates"
    r = requests.get(url, params={"offset": -1}).json()
    if r.get("result"):
        last_update_id = r["result"][-1]["update_id"] + 1

    send_message(
        f"🤖 <b>Trading bot spusten!</b>\n"
        f"Rezim: <b>{config.MODE.upper()}</b>\n\n"
        f"Prikazy:\n"
        f"/menu - hlavni menu\n"
        f"/status - stav bota\n"
        f"/reset - reset pocitadel"
    )
    send_main_menu()

    print("Bot bezi! (Ctrl+C pro zastaveni)")

    while True:
        try:
            handle_updates()
            time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Bot zastaven")
            print("Bot zastaven.")
            break
        except Exception as e:
            logger.error(f"Neocekavana chyba: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()