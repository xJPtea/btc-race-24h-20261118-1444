# DOSSIER — btc-race-24h-20261118-1444 entry

## Strategy

**Mean-cross trend rider, one trade per run.** Long only, cbBTC/USDC,
$1,000 USDC start, max 1 position, max 16 orders per reply.

- **Entry:** first 1-minute close that crosses from below to above its
  240-bar simple moving average (4-hour mean). Full equity in, one buy,
  max slippage 100 bps.
- **Exits (first to trigger):**
  - take-profit: position value ≥ cost × 1.015 (+150 bps)
  - trailing stop: close ≤ highest close since entry × 0.99 (−100 bps
    from the peak; doubles as the stop-loss if the price never rises)
  - hard stop-loss: position value ≤ cost × 0.985 (−150 bps)
  - max hold: 480 bars (8 h)
- **After the trade:** flat for the rest of the window. No entries in
  the last 60 bars.

## Parameters

| parameter | value | role |
|---|---|---|
| MEAN_BARS | 240 | 4-hour mean for the entry cross |
| TAKE_PROFIT_BPS | 150 | +1.5% vs cost |
| TRAILING_STOP_BPS | 100 | 1.0% below the peak since entry |
| HARD_STOP_BPS | 150 | −1.5% vs cost |
| MAX_HOLD_BARS | 480 | 8 h |
| END_FLAT_BARS | 60 | no entries in the last hour |
| MAX_SLIPPAGE_BPS | 100 | 1.0% worst accepted fill slippage |

## How the parameters were chosen

A parameter sweep over ~60 variants on the dev window (1,440 bars),
graded with a local replay grader (exact port of the harness fill math):

- **Mean reversion** (buy dips vs the 240-bar mean, sell at the mean,
  with/without EMA confirmation): 0–18 trades, best −$3.79, most
  variants never fire — the dip and the confirmation almost never hold
  at the same bar, and every filled dip keeps falling (win rate 0%).
- **Slow EMA cross** (30/120, 60/240): best −$4.51, 4 trades.
- **Hourly momentum + trailing stop** (60-min return > +30…+100 bps):
  best −$8.64.
- **Donchian breakout** (new 60/120-bar high + trailing stop):
  best −$17.19.
- **Mean-cross + trailing stop, one trade:** +$5.20…+$9.63 across
  trailing stops 80–150 bps — a smooth plateau, not a spike.
- **Adding take-profit +150 bps:** +$13.74. TP 120/150/180 bps gives
  +$10.79/+$13.74/+$17.14 (smooth, not a spike); TP ≥ 200 bps never
  binds and the trailing stop exits at +$7.17. TP 150 was picked as the
  middle of the smooth region, not the peak.
- **Multi-trade versions** (same rule, re-entry allowed, cooldowns
  120/240/480 bars): −$0.68…−$7.13 — the second trade in this window is
  always a loser. That is why the bot stops after one trade.
- **Confirmation variants** (entry needs the close 10+ bps above the
  mean): 0 trades — a cross is a one-bar event and never jumps that far
  in one minute. Dropped.

## Validation

Grader: `~/workspace/makefun/btc-race-24h-20261118-1444-grade/replay.py`
— an exact port of the harness fill math (BigInt constant-product pool,
buy spend = notional×(10000−4)/10000, sell price = max(1,
open×(10000−2)/(10000×M)), fees, max_slippage vs latest close,
flatten at the last close, per-bar Sharpe). Verified to reproduce the
official `grade-local` result **exactly** for all six house baselines:

| baseline | replay grader | official grade-local |
|---|---|---|
| ema-cross | −$148.17, 80 trades, DD 14.97%, Sharpe −0.203, fees $29.51 | identical |
| buy-and-hold | −$31.63, 1 trade, DD 3.25% | identical (dev gate run) |
| hold-cash | $0.00, 0 trades | identical |
| momentum | −$23.87, 1 trade | identical |
| adx-momentum | −$75.57, 30 trades | identical |
| rsi-bollinger | −$39.92, 19 trades | identical |

Final entry, full dev window (1,440 bars):

| metric | value |
|---|---|
| net PnL | **+$13.74 USDC (+1.37%)** — dev gate (> $0) PASSED |
| trades | 2 (1 round trip, win rate 100%) |
| fees | $0.81 |
| max drawdown | 0.64% (≤ 25% guardrail) |
| Sharpe (per-bar) | +0.042 |
| rejected orders | none |
| deterministic | 2 runs, identical replies, 2nd run PnL +$13.74 |

Split-half sanity check (fresh run on each half, $1,000 start):

| half | net PnL | trades | win rate |
|---|---|---|---|
| half 1 (bars 0–719) | **+$13.74** | 2 | 100% |
| half 2 (bars 720–1439) | −$8.78 | 2 | 0% |

The single trade on the full window: buy decided bar 332 (close
$63,812.89, 4h mean $63,756.43), filled bar 333 open; take-profit sell
decided bar 502 (close $64,921.10, value $1,015.35 on $1,000 cost),
filled bar 503 open.

Synthetic-bar test (`python3 test_synthetic.py`): PASSED — buy on the
mean cross at seq 240, sell on the take-profit at seq 256 (value
$1,015.98), and zero orders in 300 flat bars.

## Risks (honest)

1. **The edge is concentrated in one half.** Half 2 loses −$8.78 on its
   own run. The full-window profit comes from the recovery in half 1,
   and the one-trade rule is what keeps the bot out of the losing
   half-2 trade. This is not a strategy that wins in all regimes; it
   wins when the first confirmed multi-hour turn is real.
2. **Race-window false start.** If the live window's first mean-cross is
   a chop fake-out, the trade loses up to ~1.0% + ~$0.80 costs. Max
   loss on the single trade is bounded by the trailing stop / hard stop
   at about −1.5% + costs.
3. **No trade at all.** If the live price never closes above its 4-hour
   mean, the bot makes 0 trades and fails the race's ≥1-trade guardrail
   (PnL $0, no prize). This is the price of the one-trade discipline.
4. **Overfitting.** Parameters were tuned on one 24-hour window. The
   plateau (trailing stop 80–150 bps all positive, TP 120–180 bps all
   +$10–$17) gives some comfort, but the race window is a different
   24 hours and the numbers will differ.
5. **Official grade-local could not be run on this bot.** Docker is not
   installed on this VM, and `grade-local --driver process` runs node22
   only ("python3.13 runs only inside Docker"). The server grades in
   Docker, so the official dev grade happens at submit time. The local
   replay grader is the evidence in the meantime, and it matches the
   official grader exactly on every baseline it can grade.

## What did not work (for the record)

- EMA(8)/EMA(21) trend-following as approved in the original plan:
  the house ema-cross baseline loses −$148.17 with 80 trades (win rate
  5%). The approved plan's trend idea was tested first and abandoned on
  the evidence; the mean-cross rule above is what replaced it. The bot
  shares no code with any baseline.
- Mean reversion, hourly momentum, Donchian breakout, RSI/Bollinger,
  ADX momentum: all negative on the dev window (see sweep above).
