import time
import config
import requests
from data_fetcher import get_market_data
from analyzer import analyze_symbol as analyze_old
from analyzer_new import analyze_new_logic as analyze_new 
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


def scan_best_pairs(pairs):
    """
    Projde seznam paru a vrati nejlepsi signaly serazene podle sily.
    """
    send_message(f"🔍 Skenuji {len(pairs)} paru... chvili strpeni")
    
    results = []
    
    for symbol in pairs:
        try:
            market_data = get_market_data(symbol)
            if market_data is None:
                continue
            
            signal, checklist = analyze_symbol(market_data)
            
            if signal is not None:
                results.append({
                    "symbol": symbol,
                    "signal": signal,
                    "model": checklist.get("model", "?"),
                    "strength": checklist.get("signal_strength", "?"),
                    "splneno": checklist.get("splneno", 0),
                    "celkem": checklist.get("celkem", 10),
                    "entry_time": checklist.get("entry_time", "?"),
                    "checklist": checklist
                })
        except Exception as e:
            logger.warning(f"Chyba skenu {symbol}: {e}")
            continue
    
    if not results:
        send_message(
            "⚪ Zadny signal nenalezen\n\n"
            "Zkus pozdeji nebo jiny seznam paru."
        )
        send_main_menu()
        return
    
    # Serad podle sily
    strength_order = {"SILNY": 4, "STREDNI": 3, "SLABY": 2, "VELMI SLABY": 1}
    results.sort(
        key=lambda x: (
            strength_order.get(x["strength"], 0),
            x["splneno"]
        ),
        reverse=True
    )
    
    # Zobraz top 5
    top = results[:5]
    
    message = f"📊 <b>Top signaly ({len(results)}/{len(pairs)} paru)</b>\n\n"
    
    for i, r in enumerate(top, 1):
        emoji = "📉" if r["signal"] == "SHORT" else "📈"
        strength_emoji = {
            "SILNY": "💪", "STREDNI": "👍",
            "SLABY": "⚠️", "VELMI SLABY": "🔴"
        }.get(r["strength"], "➖")
        
        message += (
            f"{i}. {emoji} <b>{r['symbol']} — {r['signal']}</b>\n"
            f"   {strength_emoji} {r['strength']} | {r['model']} | "
            f"{r['splneno']}/{r['celkem']} | ⏰ {r['entry_time']}\n\n"
        )
    
    # Tlacitka pro top 3
    keyboard = {
        "inline_keyboard": [
            [
                {"text": f"▶️ {r['symbol']} {r['signal']}",
                 "callback_data": f"analyze_{r['symbol']}"}
            ]
            for r in top[:3]
        ] + [[{"text": "🏠 Menu", "callback_data": "back_main"}]]
    }
    
    send_message(message, keyboard)



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
            
            elif data == "scan_forex":
                forex_pairs = [
                    "EUR/USD", "GBP/USD", "USD/JPY",
                    "EUR/JPY", "AUD/JPY", "USD/CHF",
                    "EUR/GBP", "CAD/JPY", "AUD/NZD"
                ]
                scan_best_pairs(forex_pairs)

            elif data == "scan_crypto":
                crypto_pairs = [
                    "BTC/USD", "ETH/USD", "BNB/USD",
                    "SOL/USD", "XRP/USD"
                ]
                scan_best_pairs(crypto_pairs)

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
            elif text == "/logic_new":
                config.ANALYSIS_METHOD = "new"
                send_message("✅ Nastavena <b>NOVÁ</b> logika (SMC/Liquidity)")
            elif text == "/logic_old":
                config.ANALYSIS_METHOD = "old"
                send_message("✅ Nastavena <b>STARÁ</b> logika (BPU/PDF modely)")
            

# Globalni pamet poslednich signalu
last_signals = {}  # { symbol: { "signal": "SHORT", "time": datetime, "conditions": 10 } }

def analyze_and_send(symbol):
    global daily_trades, last_signals
    reset_daily_if_needed()

    if paused or daily_trades >= config.MAX_TRADES_PER_DAY or daily_losses >= config.MAX_DAILY_LOSSES:
        send_message("⏸️ Bot je zastaven nebo dosáhl limitů.")
        return

    send_message(f"🔍 Analyzuji <b>{symbol}</b>...")
    market_data = get_market_data(symbol)
    if market_data is None: return

    # --- OPRAVENÁ ČÁST: Voláme jen jednu funkci přes selector ---
    from logic_selector import get_signal
    signal, checklist = get_signal(market_data, logic_type=config.ANALYSIS_METHOD)
    # -----------------------------------------------------------

    if signal is None:
        # Získání dat pro zprávu (pokud chybí, dáme '?' nebo 'OK')
        note = checklist.get('note', 'Neznámý důvod')
        atr_reason = checklist.get('atr_reason', 'OK')
        session_note = checklist.get('session_note', 'Probíhá')
        
        # Oprava: Pokud nová logika nenašla signál, ale víme, že úrovně existují
        level_found = checklist.get('level_found', False)
        duvod = f"⚪ {note}" if level_found else "📍 Zadna uroven nenalezena"

        send_message(
            f"⚪ <b>{symbol}</b> — zadny signal\n\n"
            f"{duvod}\n\n"
            f"D1: {checklist.get('trend_daily', '?')} | "
            f"1H: {checklist.get('trend_1h', '?')} | "
            f"ATR: {atr_reason}\n"
            f"Session: {session_note}"
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
            from analyzer import calculate_best_entry
            entry_time, minutes_ahead = calculate_best_entry(datetime.now())

            send_message(
                f"{'📉' if signal == 'SHORT' else '📈'} "
                f"<b>{symbol} — {signal}</b>\n"
                f"⏰ Zavre se v <b>{entry_time.strftime('%H:%M')}</b> "
                f"({minutes_ahead} min)\n\n"
                f"♻️ Stejny signal jako pred {int(time_diff/60)} min\n"
                f"Podmínky nezmeneny — vstup na vlastni riziko.",
                keyboard
            )

            # Zapis i duplikatni signal do CSV
            from trade_logger import log_trade, init_log
            init_log()
            log_trade(symbol, signal, checklist)
            daily_trades += 1

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