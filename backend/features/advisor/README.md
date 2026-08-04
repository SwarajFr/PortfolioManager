# Advisor

Answers the two questions a person actually asks about their portfolio:

1. **What should I sell or top up?** — `portfolio_actions()`
2. **What should I buy for X% in Y months?** — `buy_ideas(horizon_months, target_gain_pct)`

It owns no market data and no scoring of its own. The exit engine already scores
holdings, the fragility engine already measures correlation and the screener
already ranks the NSE500; this feature combines them into a ranked answer where
**every candidate arrives with the reasons and the numbers behind it**.

## Why it is shaped this way

The agent that preceded it handed an LLM four raw-data tools and asked it to do
the analysis — rank a holdings table, decide what to cut. Small local models
hallucinate exactly that. So the ranking happens in Python and the model only
narrates: each candidate carries `reasons: [{code, value, ctx, text}]` where
`text` is already written. Nothing in an answer originates in the model.

That also makes the reasoning testable. A test asserts a stock 30% underwater
produces a `loss_severity` reason with value `-30`, without caring how the
sentence reads.

## Nothing is hardcoded

`horizon_months` and `target_gain_pct` are arguments. "5% in two months" and
"10% in three" run the same code and return genuinely different lists — see
`tests/test_advisor_service.py::test_buy_ideas_change_with_the_horizon_and_target`,
where shortening the horizon inverts the answer entirely. Callers that pass
nothing fall back to the user's saved profile, never to a literal in the code.
Thresholds live in `settings.py` for the same reason.

## The reachability model

The core of question 2. A stock can only be a candidate for a target it can
plausibly reach in the time available:

```
horizon_trading_days = horizon_months × 21
expected_move_pct    = atr_pct × √horizon_trading_days     # random-walk scaling
ratio                = expected_move_pct / target_gain_pct
```

`ratio` maps to a tier: `too_slow` (< 1.0, dropped — its own typical range cannot
cover the target), `stretch`, `plausible`, `comfortable`, and `too_wild` (> 5.0).
`too_wild` names are dropped for everyone except an explicitly aggressive
profile: a stock that swings 50% is not a way to earn 10%, because the stop gets
hit first. Bounds are configurable.

The stop is volatility-based (`atr_stop_multiple × ATR` below entry), so a calm
stock gets a tight stop and a jumpy one gets room — which is what makes
`reward_risk` comparable across candidates.

A second gate follows it: `min_reward_risk` (default 1.0). Reachability alone
does not catch a stock that swings enough to reach the target but whose stop sits
further away than the target does — that trade risks more than it aims to make,
and is likelier to stop out than to pay. Together the two gates leave a band of
roughly `target/√days ≤ atr_pct ≤ target/2`.

`buy_ideas` returning an empty list is a real answer, not a failure. Ask for 10%
in a month and often nothing qualifies; `excluded.counts` says why.

## Layout

| Module | Role |
|---|---|
| `metrics.py` | Pure per-stock indicators + reachability + trade levels. No I/O. Reuses `screener/compute.py`'s `sma`/`rsi`. |
| `ranking.py` | Pure `rank_sell` / `rank_topup` / `rank_buy`. Emits reason *codes*, never prose. |
| `narrate.py` | Reason code → sentence. One template dict. |
| `service.py` | The only I/O layer: gathers from the other features, ranks, narrates, journals. |
| `journal.py` | The recommendation journal (see below). |
| `settings.py` | `advisor_settings`: investor profile + tuning knobs. |
| `routes.py` | `/api/advisor/*` — lets the whole feature be tested with curl, no LLM. |

## "Top up" means add to strength

A holding qualifies only if the exit engine flags nothing (`exit_score` under
`topup_max_exit_score`), it passes at least 3 of 5 technical strength checks, and
it still has room under the single-holding cap from Portfolio settings. It is
deliberately **not** averaging down — a position the exit engine dislikes is
filtered out before ranking, so this can never suggest adding to a loser.

## Memory

Three layers, all deterministic — none inferred by an LLM:

- **Conversation context** — the chat tab's own history (frontend, `chatStore.js`).
- **Investor profile** — an explicit form: risk tolerance, default horizon and
  target, capital available, symbols to never suggest, free-text notes.
- **Recommendation journal** — every call recorded with its date, price and
  one-line rationale, deduped to one entry per symbol per kind per day. Replayed
  by `advice_history()` against the current price, so "what did you tell me last
  month, and how did it do?" has an honest answer.

The journal is written **by the service, not by the LLM** — a small model cannot
be relied on to call a "record this" tool, and an advisor that only remembers
what it felt like remembering is not accountable.

## Account isolation

`advisor_settings` and `advisor_journal` are user-scoped: both are absent from
`core.settings_store._UNSCOPED_TABLES` and keyed by Zerodha `user_id`. They hold
one person's risk appetite, capital and recommendation history. Going through the
settings store rather than a new SQLite table means account isolation, schema
migration and fail-closed writes come from the module that already guarantees
them. `tests/test_advisor_journal.py` asserts this directly.
