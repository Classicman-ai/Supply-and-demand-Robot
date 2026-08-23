"""
SUPPLY & DEMAND MT5 SYSTEM
========================================
Central configuration.

Architecture:
    MT5
      ↓
    Market Data
      ↓
    Top-Down Analysis
      ↓
    Supply/Demand Zones
      ↓
    Zone Scoring
      ↓
    M5 Entry
      ↓
    Risk Management
      ↓
    MT5 Execution
"""

# ==============================================================
# SYSTEM
# ==============================================================

SYSTEM_NAME = "SUPPLY_DEMAND_MT5"
SYSTEM_VERSION = "0.1.0"

# Explicitly enabled by the account owner for the currently connected DEMO
# terminal.  The orchestration layer still rejects non-demo accounts.
READ_ONLY = False

# Execution is permitted only after the terminal itself enables AutoTrading.
EXECUTION_ENABLED = True
REQUIRE_DEMO_ACCOUNT = True
# No volume is inferred from account balance.  A controlled demo test must
# provide an explicit, broker-valid volume.
DEMO_TEST_VOLUME = 0.01


# ==============================================================
# MARKET
# ==============================================================

# Logical instrument request.  The connector resolves this against the
# symbols exposed by the connected terminal; it is never sent as an order
# symbol without that resolution step.
INSTRUMENT_REQUEST = "GOLD"

# Top-down analysis timeframes.
HTF_TIMEFRAMES = [
    "D1",
    "H4",
    "H1",
    "M15",
]

# Entry timeframe.
EXECUTION_TIMEFRAME = "M5"

# Complete, canonical analysis hierarchy.
TIMEFRAME_CHAIN = ("D1", "H4", "H1", "M15", "M5")
ANALYSIS_CYCLE_SECONDS = 60

# Number of candles requested per timeframe.
HISTORY_CANDLES = 500


# ==============================================================
# SUPPLY / DEMAND
# ==============================================================

# Minimum candles used to establish a base.
MIN_BASE_CANDLES = 1

# Maximum candles allowed in a base.
MAX_BASE_CANDLES = 6

# Minimum departure strength.
MIN_DEPARTURE_MULTIPLIER = 1.5

# Minimum zone width relative to ATR.
MIN_ZONE_ATR = 0.10

# Maximum zone width relative to ATR.
MAX_ZONE_ATR = 3.00

# Maximum age of a zone in candles.
MAX_ZONE_AGE = 500


# ==============================================================
# ZONE TYPES
# ==============================================================

DEMAND = "DEMAND"
SUPPLY = "SUPPLY"


# ==============================================================
# ZONE QUALITY
# ==============================================================

# Minimum score required for a zone to be tradable.
MIN_ZONE_SCORE = 70

# Scoring components.
SCORE_FRESHNESS = 20
SCORE_DEPARTURE = 25
SCORE_BASE = 15
SCORE_LOCATION = 20
SCORE_REACTION = 20


# ==============================================================
# ENTRY
# ==============================================================

# Entry must occur inside/near the identified zone.
ZONE_ENTRY_TOLERANCE_ATR = 0.25

# Require confirmation before execution.
REQUIRE_ENTRY_CONFIRMATION = True

# M5 confirmation candles.
ENTRY_CONFIRMATION_CANDLES = 2

# Minimum reward/risk.
MIN_RISK_REWARD = 3.0


# ==============================================================
# RISK
# ==============================================================

# Initial development risk.

# Maximum simultaneous positions.
MAX_OPEN_TRADES = 1

# Maximum trades per day.
MAX_TRADES_PER_DAY = 3


# ==============================================================
# STOP LOSS
# ==============================================================

# Buffer beyond the zone.
SL_BUFFER_ATR = 0.20


# ==============================================================
# TAKE PROFIT
# ==============================================================

# Primary target methodology.
# The strategy should prefer opposing supply/demand zones.
TARGET_MODE = "OPPOSING_ZONE"

# Minimum R:R remains enforced even when targeting
# an opposing zone.
ENFORCE_MIN_RR = True


# ==============================================================
# EXECUTION
# ==============================================================

ORDER_DEVIATION = 20

MAGIC_NUMBER = 26081901

ORDER_COMMENT = "SUPPLY_DEMAND_MT5"


# ==============================================================
# DEVELOPMENT
# ==============================================================

DEBUG = True

LOG_LEVEL = "INFO"


