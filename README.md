# BTC Race Bot — Mean-Cross Trend Rider

[![make.fun · btc-race-24h-20261118-1444](https://make.fun/badge/btc-race-24h-20261118-1444.svg)](https://make.fun/bounty/btc-race-24h-20261118-1444?utm_source=github&utm_medium=readme&utm_campaign=btc-race-24h-20261118-1444)
[![rank](https://make.fun/badge/btc-race-24h-20261118-1444/xJPtea/btc-race-24h-20261118-1444/rank.svg)](https://make.fun/bounty/btc-race-24h-20261118-1444/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=btc-race-24h-20261118-1444)
[![reward](https://make.fun/badge/btc-race-24h-20261118-1444/xJPtea/btc-race-24h-20261118-1444/reward.svg)](https://make.fun/bounty/btc-race-24h-20261118-1444?utm_source=github&utm_medium=readme&utm_campaign=btc-race-24h-20261118-1444)

Entry for the make.fun competition **btc-race-24h-20261118-1444**
("Race a BTC trading bot live for 24 hours").

## What it does

A long-only BTC trading bot for the `agent-fun/bars-replay/v1` protocol.
It takes exactly **one trade per 24-hour window**:

1. **Entry** — the first 1-minute close that crosses from below to above
   its 240-bar simple moving average (the 4-hour mean). The whole equity
   goes in, one buy order, max slippage 100 bps.
2. **Exits** (whichever comes first):
   - take-profit at **+1.5%** vs the position's cost,
   - trailing stop **1.0%** below the highest close since entry
     (this also acts as the stop-loss when the price never rises),
   - hard stop-loss at **−1.5%** vs cost,
   - max hold **480 bars** (8 hours).
3. After that trade the bot stays flat. No entries in the last 60 bars.

## Why one trade

The dev window is a falling, choppy range ($65,083 → $63,261, −2.80%)
with one clean multi-hour recovery (+2%) in the middle. Every
high-frequency rule tested on it loses money after the ~26–30 bps
round-trip cost — the house EMA-cross baseline loses −$148.17 on 80
trades, and every mean-reversion, short-momentum and Donchian variant
swept either never fires or ends negative. The only rules that clear
the dev gate (net PnL > $0) are patient, low-frequency trend rules that
take a single confirmed move and then stop: they catch the one real
recovery and refuse to pay the chop for a second trade.

## How to run it

```sh
python3 -P -s main.py        # reads newline-delimited JSON on stdin, writes replies on stdout
python3 test_synthetic.py    # synthetic-bar smoke test (no network, no kit needed)
```

The bot is Python 3.13, standard library only, no network, no wall
clock, no files. It uses the kit's Python SDK shim, copied byte-for-byte
under `vendor/makefun_bars.py`.

## Files

- `main.py` — the bot.
- `vendor/makefun_bars.py` — the kit's SDK shim (byte-for-byte copy).
- `test_synthetic.py` — synthetic-bar smoke test.
- `DOSSIER.md` — strategy, parameters, validation numbers, risks.
- `LICENSE` — MIT (from `makefun init`).

## Validation (dev window, local replay grader)

| metric | value |
|---|---|
| net PnL | **+$13.74 USDC (+1.37%)** |
| trades | 2 (1 round trip, win rate 100%) |
| fees | $0.81 |
| max drawdown | 0.64% |
| Sharpe (per-bar) | +0.042 |
| split half 1 (bars 0–719) | +$13.74 |
| split half 2 (bars 720–1439) | −$8.78 |
| deterministic | 2 runs, identical replies |

The replay grader is an exact port of the harness fill math and was
verified to reproduce the official `grade-local` numbers for all six
house baselines (including ema-cross at −$148.17 / 80 trades / 14.97%
drawdown / Sharpe −0.203). The official `grade-local` cannot grade this
bot on this machine: Docker is not installed, and its `--driver process`
mode runs node22 only (Python 3.13 runs only inside Docker).

The single trade: buy decided at bar 332 (close $63,812.89, 4h mean
$63,756.43), filled at bar 333's open; take-profit sell decided at bar
502 (close $64,921.10, position worth $1,015.35 on a $1,000 cost),
filled at bar 503's open.
