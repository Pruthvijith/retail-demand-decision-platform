# Interview preparation · Retail demand and inventory decisions

Use first-person wording after you have run the demo and can explain or change the code yourself. Describe this as a portfolio implementation. Quantities below refer to the synthetic fixture.

## 30-second introduction

I built a retail portfolio project to answer a planner’s question: would a better forecast actually lead to better stock decisions? On a synthetic holdout, forecast error improved by seven percentage points and modeled inventory cost fell, but shortage days increased from 35 to 52. I would take that trade-off to operations before recommending a pilot.

## Two-minute technical explanation

Synthetic.py produces one row per store, SKU and day. Warehouse.py enforces identity and checks dates before building strictly lagged features. Forecast.py fits a forest on earlier dates and compares it with last week on validation. Policy.py converts asymmetric costs to a validation residual quantile. The test output gives shortage days, lost units and excess units for identical opportunities. Opening stock is used to identify censored targets and never enters the forecast matrix.

The mart uses lag 1, lag 7 and a trailing seven-day mean. The forecast also sees weekday, planned price and promotion. Cutoffs apply to all series: training ends before May 18, validation ends before June 8 and testing ends June 29, 2026. On validation, choose the lower weighted error and fit a policy-specific residual quantile of 3/(3+0.6). A separate one-day policy replay on test applies a rounded-up stock target to each uncensored observation.

Across 385 eligible test store-SKU days, the forest achieved 21.08% weighted absolute percentage error against 28.43% for the seasonal baseline. Under €3.00 per short unit and €0.60 per excess unit, modeled cost fell from €2,578.80 to €1,801.20. Shortage days increased from 35 to 52. **A service-level guardrail could reverse the selection.**

The holdout has no promotion days. Stockouts censor demand, and the replay excludes stockout targets. Each day starts independently with no carryover, delivery lead time, supplier minimums or cross-SKU substitution. This makes the EUR results sensitivity estimates.

## Architecture walkthrough

Open the files in this order and follow one record through the system.

[synthetic.py](../src/retail_decisions/synthetic.py) · [warehouse.py](../src/retail_decisions/warehouse.py) · [forecast.py](../src/retail_decisions/forecast.py) · [policy.py](../src/retail_decisions/policy.py)

Synthetic.py produces one row per store, SKU and day. Warehouse.py enforces identity and checks dates before building strictly lagged features. Forecast.py fits a forest on earlier dates and compares it with last week on validation. Policy.py converts asymmetric costs to a validation residual quantile. The test output gives shortage days, lost units and excess units for identical opportunities. Opening stock is used to identify censored targets and never enters the forecast matrix.

## Five technical questions

**1. Why align cutoff dates across products?**

A random row split can let information from the same future business day influence an earlier forecast.

**2. What information is available at prediction time?**

Prior realized sales and price and promotion assumed planned before the target day.

**3. Why exclude days that sell out?**

Observed sales are a lower bound on demand. Exclusion reduces target contamination but creates selection bias and leaves censored lag values.

**4. How does buffer calibration work?**

The chosen quantile of validation residuals is 0.8333 for the documented unit costs. A higher shortage cost pushes that quantile up.

**5. Is this a multi-week supply simulation?**

It evaluates independent next-day targets. A long-horizon simulation would need inventory state, delivery arrivals and a treatment of censored demand.

## Five product and business questions

**1. What would make finance reject the experiment?**

The assumed cost ratio may be wrong. Obtain lost contribution and disposal or holding costs by category.

**2. What would make stores reject it?**

They may accept some excess inventory to avoid more shortage days.

**3. What metric would you lead with?**

The cost and service pair. Show weighted forecast error as a diagnostic.

**4. What is missing from the June holdout?**

It has no promotion targets. Require further date windows before claiming promotional performance.

**5. How would you phase adoption?**

Use planner shadow orders, measure overrides, then compare availability and waste in comparable stores.

## What to demonstrate live

Run `python scripts/demo.py`. Point to one input, the relevant transformation and the output that supports your decision. Double the shortage cost, refit both residual buffers with the new ratio and pass the same cost assumptions to both replays. Explain any change in shortage days.

## Main trade-off and next test

SQLite window functions make feature timing inspectable. A scikit-learn forest can express interactions between calendar and store demand. A one-week seasonal baseline exposes whether the extra complexity buys anything on the same dates.

The holdout has no promotion days. Stockouts censor demand, and the replay excludes stockout targets. Each day starts independently with no carryover, delivery lead time, supplier minimums or cross-SKU substitution. This makes the EUR results sensitivity estimates.

## CV wording for a portfolio section

- Compared seasonal and random-forest demand forecasts in a synthetic retail replay, measuring cost, shortage days and excess units across 385 held-out store-SKU days.
