# Sem vlož své klíče
TWELVEDATA_API_KEY = "73d64e27147645fe860fd03b3baf0290"
TELEGRAM_BOT_TOKEN = "8685236865:AAEf9sChGMJeNZq5SXOyXhuRuOpD33or_vo"
TELEGRAM_CHAT_ID = "1105239097"  

SYMBOLS = {
    "forex": [
        "EUR/USD", "AUD/NZD", "EUR/JPY", "AUD/JPY",
        "EUR/GBP", "GBP/JPY", "USD/CHF", "EUR/CAD"
    ],
    "indices": [],
    "crypto": [],
    "commodities": []
}

MAX_DAILY_LOSS = 5
MAX_TRADES_PER_DAY = 7
MODE = "demo"
SCAN_INTERVAL = 300
INTERACTIVE_MODE = True

# ============================================================
# ANALYZA - parametry
# ============================================================

# ATR filtry
ATR_MAX_USED = 0.90          # Max % ATR pouziteho za den
ATR_OPEN_CLOSE_MIN = 0.02    # Min rozdil open/close

# Trend
TREND_SENSITIVITY = 0.35     # Citlivost detekce trendu
TREND_LOOKBACK_D1 = 5        # Pocet D1 svicek pro trend
TREND_LOOKBACK_1H = 8        # Pocet 1H svicek pro trend

# Urovne
LEVEL_LP_TOLERANCE = 0.05    # Tolerance pro limitniho hrace (% ATR)
LEVEL_MIRROR_TOLERANCE = 0.1 # Tolerance pro zrcadlovy level
LEVEL_PARANORMAL_MULT = 2.0  # Nasobek ATR pro paranormalni bar
LEVEL_MIN_TOUCHES = 3        # Min pocet doteku pro LP

# Odboj predpoklady
BOUNCE_PULLBACK_MAX = 0.4        # Max pullback pri bezodrazovem hnutí
BOUNCE_BAR_SIZE_MIN = 1.3        # Min velikost baru pri pristupu
BOUNCE_ATR_TO_LEVEL_MIN = 0.5    # Min ATR do urovne
BOUNCE_EXTREME_TOLERANCE = 0.002 # Tolerance pro lokalni extrem
BOUNCE_APPROACH_SPEED_MIN = 1.5  # Min rychlost pristupu
BOUNCE_D1_DIST_MIN = 0.3         # Min vzdalenost D1 zavreni od urovne
BOUNCE_MAX_BARS_NEAR = 2         # Max baru u urovne (bez konsolidace)
BOUNCE_LOOKBACK_EXTREME = 72     # Hodin zpet pro lokalni extrem (3 dny)

# Proboj predpoklady
BREAKOUT_BAR_SIZE_MAX = 0.7      # Max velikost baru pri pristupu
BREAKOUT_BARS_NEAR_MIN = 5       # Min baru u urovne (konsolidace)
BREAKOUT_BARS_NEAR_WEAK = 3      # Slaba konsolidace
BREAKOUT_VOLATILITY_DROP = 0.8   # Zatuchani volatility (%)
BREAKOUT_D1_CLOSE_MAX = 0.5      # Max vzdalenost D1 zavreni od urovne
BREAKOUT_EXTREME_TOLERANCE = 0.002
BREAKOUT_LOOKBACK_EXTREME = 120  # Hodin zpet pro lokalni extrem (5 dni)
BREAKOUT_MAX_OBSTACLES = 2       # Max prekazek pred uroven
BREAKOUT_OBSTACLE_MULT = 3.0     # Nasobek ATR pro zonu prekazek

# Odboj model (BPU)
BOUNCE_TOLERANCE = 0.1       # Tolerance pro BPU hit (% ATR)
BOUNCE_LUFT = 0.2            # Luft pro BPU2 (% ATR)

# LP model
LP_MAX_DEPTH = 0.33          # Max hloubka proboje (1/3 ATR)
LP_NO_IMPULSE = 1.0          # Max vzdalenost po LP

# Proboj model
BREAKOUT_SMALL_BAR = 0.4     # Max velikost baru pro proboj
BREAKOUT_PRESS_MULT = 2.0    # Nasobek tolerance pro pressing

# Checklist
CHECKLIST_TAKE_MAX_ZAPAS = 0.40  # Max tejk ze zapasu hodu
CHECKLIST_TAKE_MAX_ATR = 0.60    # Max tejk z ATR
CHECKLIST_STOP_MULT = 1.5        # Nasobek ATR pro stop
CHECKLIST_MIN_RRR = 1.0          # Min RRR

# Sila signalu
SIGNAL_STRONG_MIN = 8        # Min podminek pro SILNY signal
SIGNAL_MEDIUM_MIN = 6        # Min podminek pro STREDNI
SIGNAL_WEAK_MIN = 4          # Min podminek pro SLABY