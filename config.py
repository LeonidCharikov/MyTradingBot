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
 
# Risk management
MAX_DAILY_LOSSES = 7         # 7 prekyrti = stop (z PDF)
MAX_TRADES_PER_DAY = 7       # Max signalu za den
 
MODE = "demo"                # "demo" nebo "real"
SCAN_INTERVAL = 60           # Interval skenovani v sekundach
INTERACTIVE_MODE = True
 
# ============================================================
# ANALYZA - parametry (zmenovat zde, ne v kodu)
# ============================================================
 
# ATR filtry
ATR_MAX_USED = 0.90          # Max % ATR pouziteho za den (90% = stop)
ATR_OPEN_CLOSE_MIN = 0.02    # Min rozdil open/close pro platny den
 
# Trend - pocet svicek pro vypocet
TREND_LOOKBACK_D1 = 5        # D1: staci 5 svicek pro smerovy kontext
TREND_LOOKBACK_1H = 8        # 1H: posledních 8 hodin
 
# Urovne - detekce
LEVEL_LP_TOLERANCE = 0.05    # Tolerance pro limitniho hrace (5% ATR)
LEVEL_MIRROR_TOLERANCE = 0.1 # Tolerance pro zrcadlovy level (10% ATR)
LEVEL_PARANORMAL_MULT = 2.0  # Paranormalni bar = > 2x ATR
LEVEL_MIN_TOUCHES = 3        # Min dotyku pro limitniho hrace
 
# Odboj - predpoklady (check_bounce_prerequisites)
BOUNCE_PULLBACK_MAX = 0.4        # Max pullback = 40% celkoveho pohybu
BOUNCE_BAR_SIZE_MIN = 1.3        # Pristup na velkych barech = 130% prumeru
BOUNCE_ATR_TO_LEVEL_MIN = 0.5    # Min ATR vzdalenost do urovne
BOUNCE_EXTREME_TOLERANCE = 0.002 # Tolerance pro lokalni extrem (0.2%)
BOUNCE_APPROACH_SPEED_MIN = 1.5  # Rychlost pristupu = 150% prumeru
BOUNCE_D1_DIST_MIN = 0.3         # D1 zavreni min 30% ATR od urovne
BOUNCE_MAX_BARS_NEAR = 2         # Max baru u urovne (konsolidace = spatne)
BOUNCE_LOOKBACK_EXTREME = 72     # Lokalni extrem za 3 dny (72h)
 
# Proboj - predpoklady (check_breakout_prerequisites)
BREAKOUT_BAR_SIZE_MAX = 0.7      # Male bary = max 70% prumeru
BREAKOUT_BARS_NEAR_MIN = 5       # Min 5 baru u urovne (konsolidace)
BREAKOUT_BARS_NEAR_WEAK = 3      # Slaba konsolidace = 3 bary
BREAKOUT_VOLATILITY_DROP = 0.8   # Zatuchani = druha polovina < 80% prvni
BREAKOUT_D1_CLOSE_MAX = 0.5      # D1 zavreni max 50% ATR od urovne
BREAKOUT_EXTREME_TOLERANCE = 0.002
BREAKOUT_LOOKBACK_EXTREME = 120  # Lokalni extrem za 5 dni (120h)
BREAKOUT_MAX_OBSTACLES = 2       # Max prekazek pred uroven
BREAKOUT_OBSTACLE_MULT = 3.0     # Zona prekazek = 3x ATR
 
# Odboj model - BPU parametry
BOUNCE_TOLERANCE = 0.1       # Tolerance pro BPU hit (10% ATR)
BOUNCE_LUFT = 0.2            # Luft = 20% stopu (z PDF)
 
# LP model - lozny proboj
LP_MAX_DEPTH = 0.33          # Max hloubka proboje = 1/3 ATR (z PDF)
LP_NO_IMPULSE = 1.0          # Max vzdalenost od zaявky po LP
 
# Proboj model
BREAKOUT_SMALL_BAR = 0.4     # Male bary = max 40% ATR
BREAKOUT_PRESS_MULT = 2.0    # Pressing = 2x tolerance od urovne
 
# Checklist - tejk a stop
CHECKLIST_TAKE_MAX_ZAPAS = 0.40  # Tejk max 40% zapasu hodu (z PDF)
CHECKLIST_TAKE_MAX_ATR = 0.60    # Tejk max 60% ATR (z PDF)
CHECKLIST_STOP_MULT = 1.5        # Stop = 1.5x ATR za uroven
CHECKLIST_MIN_RRR = 1.0          # Min RRR 1:1
 
# Sila signalu - pocet splnenych podminek
SIGNAL_STRONG_MIN = 7        # SILNY = 7+ podminek
SIGNAL_MEDIUM_MIN = 5        # STREDNI = 5-6 podminek
SIGNAL_WEAK_MIN = 3          # SLABY = 3-4 podminky
 
# Cache - opakovana analyza stejneho symbolu
CACHE_FAST_MINUTES = 5       # Pri opakovani pouzij data starsi max 5 min