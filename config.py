# config.py
# SCEPTER MOMENTUM BOT v5.0 — CLEAN CONFIG

# ═══════════════════════════════════════════
# GENERAL
# ═══════════════════════════════════════════
SLEEP_SECONDS = 15
TIMEFRAME = "5m"


# ═══════════════════════════════════════════
# RISK MANAGEMENT
# ═══════════════════════════════════════════
MAX_OPEN_TRADES = 2
MAX_RISK_PERCENT = 1.5
RISK_PER_TRADE_PERCENT = 1.0
MAX_SL_PERCENT = 1.5
MAX_MARGIN_PER_TRADE_PERCENT = 50.0
LEVERAGE = 5
CAPITAL_USE_PERCENT = 100
RR_RATIO = 2.0
RISK_REWARD_RATIO = 2
EMERGENCY_DRAWDOWN_PERCENT = 100.0

# ═══════════════════════════════════════════
# INDICATORS
# ═══════════════════════════════════════════
ATR_PERIOD = 14
ATR_EXPANSION_RATIO = 0.80

# ═══════════════════════════════════════════
# VOLUME
# ═══════════════════════════════════════════
VOLUME_LOOKBACK = 10
VOLUME_SPIKE_RATIO = 0.80
VOLUME_BREAKOUT_GT_PULLBACK = True

# ═══════════════════════════════════════════
# BREAKOUT & PULLBACK
# ═══════════════════════════════════════════
BREAKOUT_LOOKBACK = 6
BREAKOUT_RANGE_MIN = 0.50
BREAKOUT_BODY_MIN = 0.40
BREAKOUT_BODY_MAX = 0.50
PULLBACK_MIN = 14.0
PULLBACK_MAX = 54.0
PULLBACK_DEPTH_MIN = 14.0
PULLBACK_DEPTH_MAX = 54.0
PULLBACK_REJECT_ZONE_MAX = 95.0
PULLBACK_MAX_CANDLES_AFTER_BREAKOUT = 9
PULLBACK_TIMING_MAX = 9
CONSOLIDATION_MIN_RANGE_PCT = 0.25
REQUIRE_PURE_BULLISH_SWINGS = True
ADX_PERIOD = 14
ADX_MIN_SLOPE = -1.5

# ═══════════════════════════════════════════
# CANDLE FILTERS
# ═══════════════════════════════════════════
MIN_RANGE_RATIO = 1.0
MIN_BODY_RATIO = 0.40
MAX_UPPER_WICK_RATIO = 0.25
UPPER_WICK_MAX = 0.25

# ═══════════════════════════════════════════
# OVEREXTENSION
# ═══════════════════════════════════════════
OVEREXTENSION_LOOKBACK = 8
OVEREXTENSION_BULLISH_THRESHOLD = 8
CONSECUTIVE_BULLISH_MAX = 8

# ═══════════════════════════════════════════
# ENGULFING
# ═══════════════════════════════════════════
BEARISH_ENGULFING_RATIO = 1.0
BEARISH_ENGULFING_BODY = 0.60
BULLISH_ENGULFING_BODY = 0.60
ENGULFING_MIN_BODY_RATIO = 0.60

# ═══════════════════════════════════════════
# ENTRY & EXIT
# ═══════════════════════════════════════════
ENTRY_BUFFER_PERCENT = 0.10
MAX_SLIPPAGE_PERCENT = 5.0
SLIPPAGE_MAX = 5.0
MAX_SPREAD_PERCENT = 0.27
SPREAD_MAX = 0.27
LONG_EXIT_MIN_R = 1.0

# ═══════════════════════════════════════════
# SELL — FAILED BREAKOUT
# ═══════════════════════════════════════════
FAILED_BREAKOUT_MIN = 65.0
FAILED_BREAKOUT_MAX = 95.0

# ═══════════════════════════════════════════
# SELL — SWING REQUIREMENTS
# ═══════════════════════════════════════════
SWING_LOWS_REQUIRED = 3
SWING_HIGHS_REQUIRED = 3
MIN_SWING_LOWS_SHORT = 3
MIN_SWING_HIGHS_LONG = 2
RECOVERY_CANDLE_MIN_BODY = 0.30
RECOVERY_CANDLE_MAX_WICK = 0.25

# ═══════════════════════════════════════════
# CONFIRMATION SYSTEM
# ═══════════════════════════════════════════
USE_CONFIRMATION = True
REQUIRE_CONFIRMATION = True

# ═══════════════════════════════════════════
# ORDER
# ═══════════════════════════════════════════
ORDER_TYPE = "maker_limit"

# ═══════════════════════════════════════════
# LOGGING
# ═══════════════════════════════════════════
TRADES_LOG_FOLDER = "logs/trades"
REJECTION_LOG_FOLDER = "logs/rejections"
BACKUP_LOG_FOLDER = "logs/backup"
