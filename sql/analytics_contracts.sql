-- Gold mart: daily_features. Always compute lags from prior observations.
-- NOTE: this SQL expresses the metric definitions and can be run on SQLite.

-- Full-price vs promotional units, with censored stockout targets flagged.
SELECT sku,
       SUM(CASE WHEN promo_planned=1 THEN units_sold ELSE 0 END) AS promo_units,
       SUM(CASE WHEN promo_planned=0 THEN units_sold ELSE 0 END) AS regular_units,
       SUM(is_stockout) AS stockout_days,
       COUNT(*) AS observed_days
FROM daily_features
GROUP BY sku
ORDER BY sku;

-- Data quality: every store-SKU must have contiguous daily observations.
WITH consecutive AS (
 SELECT store_id,sku,day,LAG(day) OVER(PARTITION BY store_id,sku ORDER BY day) AS prior
 FROM raw_sales
)
SELECT store_id,sku, COUNT(*) AS gap_count
FROM consecutive
WHERE prior IS NOT NULL AND julianday(day)-julianday(prior) <> 1
GROUP BY store_id,sku;
