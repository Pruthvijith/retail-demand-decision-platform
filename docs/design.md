# Product requirements and operating notes

## User decision and opportunity

A retail planner must choose a forecast and a stock buffer. The replay compares both excess and shortage units on the same store, SKU and day. A weighted error metric alone would hide the service trade-off.

| Stakeholder | Priority and milestone | Acceptance criterion |
|---|---|---|
| Demand planner | P0 · compare forecasts | Select on a common chronological validation window. Report both model and seasonal error on held-out rows. |
| Store operations | P0 · service guardrail | Report days short and units short alongside excess units for both policies. |
| Finance | P1 · cost sensitivity | Expose assumed unit costs and calibration. Refit both buffers after any change to the cost ratio. |

## Metric definitions and validation

The mart uses lag 1, lag 7 and a trailing seven-day mean. The forecast also sees weekday, planned price and promotion. Cutoffs apply to all series: training ends before May 18, validation ends before June 8 and testing ends June 29, 2026. On validation, choose the lower weighted error and fit a policy-specific residual quantile of 3/(3+0.6). A separate one-day policy replay on test applies a rounded-up stock target to each uncensored observation.

Across 385 eligible test store-SKU days, the forest achieved 21.08% weighted absolute percentage error against 28.43% for the seasonal baseline. Under €3.00 per short unit and €0.60 per excess unit, modeled cost fell from €2,578.80 to €1,801.20. Shortage days increased from 35 to 52. **A service-level guardrail could reverse the selection.**

## Architecture decision record

**Accepted for this local workload.** SQLite window functions make feature timing inspectable. A scikit-learn forest can express interactions between calendar and store demand. A one-week seasonal baseline exposes whether the extra complexity buys anything on the same dates.

Synthetic.py produces one row per store, SKU and day. Warehouse.py enforces identity and checks dates before building strictly lagged features. Forecast.py fits a forest on earlier dates and compares it with last week on validation. Policy.py converts asymmetric costs to a validation residual quantile. The test output gives shortage days, lost units and excess units for identical opportunities. Opening stock is used to identify censored targets and never enters the forecast matrix.

The implementation lives in [the Python package](../src/retail_decisions). The boundaries are exercised by [the test suite](../tests).

## Operating procedure

The quality gate rejects interior date gaps before any feature replacement. Preserve the input SQLite database and regenerate the mart after repairing inputs. Rerun an identical source configuration for replay. Start a fresh database for a changed simulator configuration. Proposed daily batch objective: deliver one reconciled mart before planner review.

1. Reproduce the baseline with `python scripts/demo.py`. Compare the decision fields with the committed example.
2. Run the regression suite before changing input definitions or thresholds. Use the persistent example in the README to inspect intermediate state.
3. Replay the source and compare results across independent runs before releasing a new batch definition.

### Container example

From the repository root:

```shell
docker build -t portfolio-demo .
docker run --rm portfolio-demo
```

The container runs the isolated demo and exits.
This configuration awaits Docker execution. The same demo was exercised with the installed Python package.

## Constraints, reliability and delivery

The holdout has no promotion days. Stockouts censor demand, and the replay excludes stockout targets. Each day starts independently with no carryover, delivery lead time, supplier minimums or cross-SKU substitution. This makes the EUR results sensitivity estimates.

Deliver the quality-gated mart first, then validate a baseline, then compare ordering decisions. Before a pilot, run several rolling origins covering promotions, obtain category-specific costs and agree an acceptable shortage rate.

Local demo data and code are independent of former employers. Cost scenarios use declared assumptions. Operational targets describe a proposed pilot.
