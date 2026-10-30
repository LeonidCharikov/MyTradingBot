# MyTradingBot

Experimentální Python projekt pro sledování finančních trhů, technickou analýzu a
zasílání obchodních signálů přes Telegram. Projekt neslouží jako obchodní
platforma a neprovádí automatické zadávání příkazů u brokera.

> **DŮLEŽITÝ DISCLAIMER**
>
> Tento projekt je **experimentální a vzdělávací**. Výstupy algoritmů nejsou
> investičním doporučením, finanční radou ani zárukou zisku. Kód může obsahovat
> chyby, neúplné modely a nesprávné předpoklady. Nepoužívejte jej k rozhodování
> o skutečných penězích ani k live tradingu bez vlastního důkladného auditu,
> testování a řízení rizik. Autor nenese odpovědnost za jakékoli ztráty nebo
> škody způsobené použitím tohoto projektu.

## Co projekt dělá

Bot běží jako jednoduchá smyčka, která:

1. přijímá příkazy a callbacky z Telegramu,
2. stáhne tržní data pro vybraný symbol,
3. připraví data pro časové rámce D1, 1H, 15M a 5M,
4. vypočítá ATR a další pomocné hodnoty,
5. vybere jednu ze dvou analytických logik,
6. vyhodnotí podmínky pro LONG nebo SHORT signál,
7. odešle výsledek do Telegramu,
8. uloží signál a jeho pozdější výsledek do `trades.csv`.

Projekt pouze generuje a eviduje signály. Neobsahuje napojení na brokera,
exekuci objednávek, správu účtu ani garanci výsledku.

## Hlavní funkce

- **Dva analytické režimy**
  - `new`: novější logika založená na SMC, likviditě, úrovních a krátkých
    časových rámcích.
  - `old`: původní logika s detekcí trendu, úrovní, odrazů, průrazů a
    checklistů.
- **Více zdrojů dat**
  - TwelveData pro forex, komodity a indexy.
  - Binance API pro podporované kryptoměny bez API klíče.
- **Více časových rámců**: denní data, 1H, 15M a 5M.
- **ATR filtry** pro odhad volatility a kontrolu vzdáleností.
- **Trendové a časové filtry** včetně londýnské a newyorské seance.
- **Kontrola korelovaných párů**, kanálů, historických úrovní a překážek.
- **Ochranné limity** na počet denních signálů a denní ztráty.
- **Cache tržních dat**: při opakované analýze se krátké časové rámce
  aktualizují rychleji a starší data se znovu nestahují zbytečně.
- **Telegram menu** pro výběr forexu, kryptoměn, komodit a indexů.
- **CSV evidence** signálů, modelu, síly signálu, úrovně, stopu, take-profitu,
  RRR, seance a výsledku.
- **Prevence duplicitních signálů** pro stejný symbol v krátkém časovém okně.

## Struktura projektu

```text
MyTradingBot/
├── main.py                 # Spuštění bota, Telegram smyčka a limity
├── config.py               # Konfigurace API, režimu a analytických parametrů
├── data_fetcher.py         # Stahování, normalizace, ATR a cache dat
├── analyzer.py             # Původní analytická logika
├── analyzer_new.py         # Novější SMC/liquidity analytická logika
├── logic_selector.py       # Výběr aktivní analytické logiky
├── telegram_notifier.py    # Telegram zprávy, menu a formátování signálů
├── trade_logger.py         # Zápis signálů a statistik do CSV
├── trades.csv              # Lokální evidence signálů a výsledků
├── bot.log                 # Lokální provozní log
└── README.md               # Dokumentace
```

## Požadavky

- Python 3.10 nebo novější
- Přístup k internetu
- Telegram bot pro interaktivní ovládání
- TwelveData API klíč pro forex, komodity a indexy
- Binance účet není pro veřejná tržní data potřeba

Knihovny použité projektem:

```powershell
python -m pip install requests pandas numpy
```

## Konfigurace

Údaje nastavte lokálně v [config.py](./config.py). Do Git repozitáře
neukládejte skutečné tokeny, API klíče ani Telegram ID.

```python
TWELVEDATA_API_KEY = ""
TELEGRAM_BOT_TOKEN = ""
TELEGRAM_CHAT_ID = [""]

MODE = "demo"
ANALYSIS_METHOD = "new"
SCAN_INTERVAL = 60
INTERACTIVE_MODE = True
```

Nejdůležitější konfigurační oblasti:

- `MODE`, `ANALYSIS_METHOD` a `SCAN_INTERVAL` řídí provoz botu.
- `MAX_DAILY_LOSSES` a `MAX_TRADES_PER_DAY` omezují denní aktivitu.
- `SESSION_*` nastavuje časová okna a jejich zapnutí.
- `EMA_*`, `ATR_*` a `TREND_LOOKBACK_*` řídí trendové a volatilní filtry.
- `BOUNCE_*`, `BREAKOUT_*` a `LEVEL_*` řídí detekci odrazů, průrazů a úrovní.
- `CHECKLIST_*` nastavuje stop-loss, take-profit a minimální RRR.

Hodnota `MODE = "demo"` je doporučená pro vývoj a testování. Ani případná
hodnota `"real"` sama o sobě nezapíná obchodování u brokera, protože projekt
žádný broker konektor neobsahuje.

## Spuštění

Po doplnění konfigurace spusťte:

```powershell
python main.py
```

Bot následně čeká na Telegram příkazy. Dostupné základní příkazy zahrnují:

- `/menu` - zobrazí hlavní menu,
- `/status` - zobrazí stav botu,
- `/reset` - resetuje denní počítadla,
- `/logic_new` - přepne na novější analytickou logiku,
- `/logic_old` - přepne na původní analytickou logiku.

## Data a limity

Forex, komodity a indexy se načítají přes TwelveData, kde může být aktivní
rate limit. Krypto symboly se načítají přes veřejné endpointy Binance.
Při chybě nebo nedostatku dat se signál nevytvoří; podrobnosti se zapisují do
`bot.log`.

`trades.csv` je lokální provozní soubor. Obsahuje historii signálů a může
obsahovat vlastní poznámky nebo výsledky, proto jej před sdílením zkontrolujte.
`bot.log` může obsahovat diagnostická data a neměl by se zveřejňovat bez kontroly.

## Stav projektu

Projekt je ve fázi experimentování a průběžného vývoje. Analytické modely,
prahové hodnoty i datové zdroje je nutné validovat na vlastních datech,
backtestech a paper-tradingu. Nejde o hotový produkční systém.

## Licence a odpovědnost

Projekt je poskytován bez záruk. Před použitím si ověřte licenční podmínky
externích datových služeb a dodržujte jejich limity. Použití kódu je na vlastní
nebezpečí.
