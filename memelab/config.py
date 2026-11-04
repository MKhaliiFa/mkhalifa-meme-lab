"""Every number the lab uses, written down BEFORE any result was seen (2026-11-04). Overridable from config.env."""
from __future__ import annotations

import os


def _f(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except ValueError:
        return float(default)


# ---- entry filter (a coin is "bought" on paper only if ALL pass) -----------------------------------------
MIN_AGE_MIN = _f("MIN_AGE_MIN", 10)          # minutes after graduation before any decision
MAX_WAIT_MIN = _f("MAX_WAIT_MIN", 60)        # dropped if it never qualified by then
MIN_LIQ_USD = _f("MIN_LIQ_USD", 40_000)
MAX_TOP10_PCT = _f("MAX_TOP10_PCT", 25)      # top 10 holders, pools and curve excluded
MAX_DEV_PCT = _f("MAX_DEV_PCT", 5)           # creator's share of supply
MAX_H1_PCT = _f("MAX_H1_PCT", 80)            # no chasing: price change over the last hour
MAX_DANGER_RISKS = _f("MAX_DANGER_RISKS", 0) # RugCheck "danger" risks allowed

# ---- paper position ------------------------------------------------------------------------------------
TICKET_USD = _f("TICKET_USD", 50)            # the size a real $100 account would use
FEE_PCT = _f("FEE_PCT", 1.0)                 # platform fee per side (FOMO / Axiom style apps: 0.5-2 %)
GAS_USD = _f("GAS_USD", 0.01)                # Solana priority fee per side
STOP_PCT = _f("STOP_PCT", 6)                 # exit when price <= entry * (1 - 6 %)
TRAIL_START_PCT = _f("TRAIL_START_PCT", 20)  # trailing starts at +20 %
TRAIL_PCT = _f("TRAIL_PCT", 12)              # then exits 12 % below the peak
TIMEOUT_H = _f("TIMEOUT_H", 3)               # dead money: out after 3 h if under +5 %
TIMEOUT_MIN_GAIN_PCT = _f("TIMEOUT_MIN_GAIN_PCT", 5)
PULLED_LIQ_DROP = _f("PULLED_LIQ_DROP", 0.8) # liquidity down 80 % from entry = rug: out at what is left

# ---- verdict (fixed in advance) ------------------------------------------------------------------------
VERDICT_DAYS = _f("VERDICT_DAYS", 14)
VERDICT_MIN_TRADES = _f("VERDICT_MIN_TRADES", 100)

# ---- polling -------------------------------------------------------------------------------------------
WAIT_POLL_S = _f("WAIT_POLL_S", 60)
OPEN_POLL_S = _f("OPEN_POLL_S", 15)
SUMMARY_S = _f("SUMMARY_S", 300)

PUMPPORTAL_WS = os.getenv("PUMPPORTAL_WS", "wss://pumpportal.fun/api/data")
DEXSCREENER = os.getenv("DEXSCREENER", "https://api.dexscreener.com/tokens/v1/solana/")
RUGCHECK = os.getenv("RUGCHECK", "https://api.rugcheck.xyz/v1/tokens/{mint}/report")
RPC_URL = os.getenv("RPC_URL", "https://api.mainnet-beta.solana.com")   # optional: Helius etc. later

DATA_DIR = os.getenv("DATA_DIR", "data")
SUMMARY_PATH = os.getenv("SUMMARY_PATH", os.path.join(DATA_DIR, "summary.json"))
