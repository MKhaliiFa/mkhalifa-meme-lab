import os
import tempfile
import unittest

from memelab import config as C
from memelab import fields as F
from memelab.main import Lab
from memelab.report import build
from memelab.rules import Position, gate, impact
from memelab.stats import stats, verdict
from memelab.store import Store

MINT = "7GCihgDB8fe6KNjn2MYtkzZcRjQy3t9GHdC8uHYmW2hr"
POOL = "PoolAcct1111111111111111111111111111111111"


def pair(price=0.001, liq=60_000, h1=10.0, mint=MINT):
    return {"chainId": "solana", "dexId": "pumpswap", "pairAddress": "P1", "priceUsd": str(price),
            "liquidity": {"usd": liq}, "priceChange": {"h1": h1, "m5": 1}, "volume": {"h1": 30000},
            "txns": {"h1": {"buys": 200, "sells": 150}}, "baseToken": {"address": mint, "name": "Cat", "symbol": "CAT"}}


def rug(top=(3, 2, 2), dev_pct=1.0, mint_auth=None, danger=0):
    holders = [{"address": POOL, "owner": POOL, "pct": 40.0}]          # the pool: must be excluded
    holders += [{"address": f"H{i}", "owner": f"O{i}", "pct": p} for i, p in enumerate(top)]
    holders.append({"address": "DEVACC", "owner": "DEV", "pct": dev_pct})
    return {"mintAuthority": mint_auth, "freezeAuthority": None, "creator": "DEV", "topHolders": holders,
            "markets": [{"pubkey": POOL, "liquidityA": POOL}], "risks": [{"name": "x", "level": "danger"}] * danger,
            "totalHolders": 900}


class Fields(unittest.TestCase):
    def test_migration_and_pair(self):
        self.assertEqual(F.migration_mint({"mint": MINT, "txType": "migrate"}), MINT)
        self.assertIsNone(F.migration_mint({"message": "Successfully subscribed"}))
        mk = F.market(F.best_pair([pair(liq=10), pair(liq=60_000)], MINT))
        self.assertEqual(mk["liq"], 60_000)

    def test_safety_excludes_pools(self):
        sf = F.safety(rug())
        self.assertAlmostEqual(sf["top10"], 3 + 2 + 2 + 1.0)            # pool's 40 % left out, dev counted
        self.assertEqual(sf["dev"], 1.0)
        self.assertEqual(F.safety(None), {})


class Gate(unittest.TestCase):
    def test_rules_in_order(self):
        mk, sf = F.market(pair()), F.safety(rug())
        self.assertEqual(gate(11, mk, sf), (True, ""))
        self.assertEqual(gate(5, mk, sf)[1], "too young")
        self.assertIn("liquidity", gate(11, F.market(pair(liq=30_000)), sf)[1])
        self.assertIn("chasing", gate(11, F.market(pair(h1=120)), sf)[1])
        self.assertEqual(gate(11, mk, F.safety(rug(mint_auth="X")))[1], "mint not revoked")
        self.assertIn("top 10", gate(11, mk, F.safety(rug(top=(10, 10, 10))))[1])
        self.assertIn("dev holds", gate(11, mk, F.safety(rug(dev_pct=8)))[1])
        self.assertIn("danger", gate(11, mk, F.safety(rug(danger=1)))[1])
        self.assertEqual(gate(11, mk, {})[1], "no data: safety")


class Paper(unittest.TestCase):
    def test_costs_are_charged(self):
        p = Position.open(MINT, 0, 1.0, 1e12)                             # no impact
        self.assertEqual(p.check(60, 1.0, 1e12), None)
        p._close(60, 1.0, 1e12, "flat")
        self.assertLess(p.pnl, -0.9)                                      # 2 x 1 % of $50 + gas
        self.assertGreater(impact(50, 60_000), 0.0015)

    def test_stop_trail_timeout_rug(self):
        p = Position.open(MINT, 0, 1.0, 1e12)
        self.assertEqual(p.check(10, 0.93, 1e12), "stop")
        p = Position.open(MINT, 0, 1.0, 1e12)
        p.check(10, 1.25, 1e12)
        self.assertTrue(p.trail)
        self.assertIsNone(p.check(20, 1.15, 1e12))
        self.assertEqual(p.check(30, 1.09, 1e12), "trail")                # 12 % under the 1.25 peak
        self.assertGreater(p.pnl, 0)
        p = Position.open(MINT, 0, 1.0, 1e12)
        self.assertEqual(p.check(3 * 3600 + 1, 1.02, 1e12), "timeout")
        p = Position.open(MINT, 0, 1.0, 100_000)
        self.assertEqual(p.check(10, 0.5, 10_000), "liquidity pulled")
        self.assertLess(p.pct, -40)


class Flow(unittest.TestCase):
    def test_one_decision_control_and_summary(self):
        d = tempfile.mkdtemp()
        now = [1_000_000.0]
        st = Store(os.path.join(d, "lab.sqlite"))
        lab = Lab(st, clock=lambda: now[0])
        st.add_coin(MINT, now[0])
        self.assertEqual(lab.decide([pair()], lambda m: rug()), 0)        # too young: still waiting
        now[0] += 11 * 60
        self.assertEqual(lab.decide([pair()], lambda m: rug()), 1)
        self.assertEqual(len(lab.open), 2)                                 # the filter trade + the control
        self.assertEqual(lab.decide([pair()], lambda m: rug()), 0)        # one decision per coin
        now[0] += 60
        done = lab.manage([pair(price=0.0009)])                            # -10 %: both stopped
        self.assertEqual(len(done), 2)
        s = build(st, {"err": {}}, now[0], len(lab.open))
        self.assertEqual(s["filter"]["n"], 1)
        self.assertTrue(any("Meme Lab" in x for x in s["report_lines"]))
        lab2 = Lab(st, clock=lambda: now[0])                               # restart: nothing left open
        self.assertEqual(lab2.open, {})

    def test_verdict_rules(self):
        rows = [{"pnl": 1.0, "pct": 2.0}] * 60 + [{"pnl": -0.5, "pct": -1.0}] * 50
        f = stats(rows)
        self.assertTrue(verdict(f, stats([]), 3).startswith("measuring"))
        self.assertEqual(verdict(f, stats([{"pnl": -1, "pct": -2}] * 10), 15), "PASS")
        self.assertIn("no better", verdict(f, stats([{"pnl": 2, "pct": 4}] * 10), 15))


if __name__ == "__main__":
    unittest.main()
