# MKhaliFa Meme Lab

**Paper only. It never trades, holds no wallet, no key and no money.**

A question asked with data instead of videos: *does a strict safety filter on pump.fun graduates make money
after real costs?* For two weeks the lab watches every coin that graduates from the pump.fun curve, decides
once (10 minutes after graduation) whether the filter would buy it, and follows that paper trade with the
real prices until it would have been sold.

## How it works

1. **Stream**: PumpPortal (free websocket) sends every graduation.
2. **Waiting room**: the coin waits 10 minutes (half of new coins die in the first minutes).
3. **One decision**, with DexScreener (price, liquidity, last hour) and RugCheck (authorities, holders,
   creator, risks), all free and public. Missing data is a **no**, never a guess.
4. **Paper position**: a $50 ticket, the real price impact of the pool, 1 % fee each way, gas.
5. **Exits** every 15 s on real prices.
6. **Control**: every graduate that reached 10 minutes is also "bought" with **no rules at all**, so the
   filter has to beat plain buying to count.

## The rules (written 2026-11-04, before any result)

| Entry, ALL must pass | |
|---|---|
| age | 10 min after graduation (dropped after 60 min without data) |
| liquidity | at least $40,000 |
| no chasing | not up more than 80 % in the last hour |
| mint and freeze authority | both revoked |
| top 10 holders | 25 % of supply or less (pools and the curve excluded) |
| creator | holds 5 % or less |
| RugCheck | no "danger" risk |

| Exit | |
|---|---|
| stop | −6 % from the signal price |
| trailing | starts at +20 %, sells 12 % under the peak |
| dead money | after 3 h, if under +5 % |
| rug | liquidity down 80 % from entry: sold into what is left |

Costs per trade: 1 % fee in, 1 % fee out, the pool's price impact both ways, $0.01 gas each way.

## The verdict (fixed in advance)

After **14 days and at least 100 filter trades**, PASS needs all of:
- net profit after costs > 0
- still > 0 without the single best trade (not one lucky coin)
- t-stat of the per-trade result > 2
- the filter beats the control (buying every graduate) per trade

Anything else is FAIL, and nothing with real money follows. A PASS only opens the discussion.

## Where to see it

One block in the trading bot's 09:00 daily report on Telegram (no separate messages), and
`/opt/mkhalifa-meme-lab/data/summary.json` on the server (copied every 5 minutes to the bot's
`/opt/mkhalifa/data/meme/`, with a status note). Raw samples of every source are kept in
`data/raw/` so the field mapping can be checked by a human.

## Server

`install.sh` (one time, root): own user `memelab`, its own Python venv, systemd service capped at 300 MB and
40 % CPU, and a 5-minute timer that installs a new commit only after the tests pass. The live trading bot
is never touched.

```bash
python -m unittest discover -s tests -t .     # tests
python -m memelab.main --check                # one call to every source
```
