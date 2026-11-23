import json
from datetime import date, timedelta

import numpy as np
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from retail_decisions.decisions import recommend_reorder
from retail_decisions.forecast import evaluate, train_and_backtest
from retail_decisions.pipeline import run
from retail_decisions.synthetic import populate
from retail_decisions.warehouse import (
    connect,
    load_product,
    load_sale,
    materialize_features,
    quality_report,
)


class PlatformTests(TestCase):
    def test_ingestion_idempotent_and_domain_checks(self):
        tmp_path = Path(self.enterContext(TemporaryDirectory()))
        path = tmp_path / "db.sqlite"
        with connect(path) as db:
            load_product(db, "sku_1", "home", 3)
            assert load_sale(db, "id_01", "store_1", "sku_1", date(2026, 1, 1), 3, 0, 4.5, 10)
            assert not load_sale(db, "id_01", "store_1", "sku_1", date(2026, 1, 1), 3, 0, 4.5, 10)
            with self.assertRaises(ValueError):
                load_sale(db, "id_02", "store_1", "sku_1", date(2026, 1, 2), 11, 0, 4.5, 10)
            with self.assertRaisesRegex(ValueError, "Conflicting"):
                load_sale(db, "id_01", "store_1", "sku_1", date(2026, 1, 1), 4, 0, 4.5, 10)
            assert quality_report(db)["quality_pass"]

    def test_quality_catches_gaps(self):
        tmp_path = Path(self.enterContext(TemporaryDirectory()))
        with connect(tmp_path / "db.sqlite") as db:
            load_product(db, "sku_1", "home", 3)
            for idx in (0, 2):
                load_sale(db, f"id_{idx}", "store_1", "sku_1", date(2026, 1, 1) + timedelta(days=idx),
                          3, 0, 4.5, 10)
            assert quality_report(db)["date_gaps"] == 1
            with self.assertRaises(ValueError):
                materialize_features(db)

    def test_gold_features_use_only_prior_sales(self):
        tmp_path = Path(self.enterContext(TemporaryDirectory()))
        path = str(tmp_path / "db.sqlite")
        populate(path, days=100, stores=1)
        with connect(path) as db:
            assert materialize_features(db) == 600
            rows = db.execute("SELECT * FROM daily_features WHERE sku='sku_01' "
                              "ORDER BY day LIMIT 9").fetchall()
            assert rows[0]["lag_1"] is None
            assert rows[0]["lag_7"] is None
            assert rows[1]["lag_1"] == rows[0]["units_sold"]
            assert rows[7]["lag_7"] == rows[0]["units_sold"]
            assert materialize_features(db) == 600

    def test_backtest_untouched_chronological_holdout(self):
        tmp_path = Path(self.enterContext(TemporaryDirectory()))
        path, output = str(tmp_path / "db.sqlite"), str(tmp_path / "artifacts")
        populate(path, days=115, stores=1)
        with connect(path) as db:
            materialize_features(db)
        report = train_and_backtest(path, output)
        assert report["row_counts"]["test"] > 0
        assert report["train_end_exclusive"] < report["validation_end_exclusive"]
        assert report["validation_end_exclusive"] <= report["test_end_inclusive"]
        assert report["selected_champion"] in {"random_forest", "seasonal_naive"}
        assert json.loads((tmp_path / "artifacts" / "backtest.json").read_text())

    def test_metrics_and_reordering(self):
        self.assertAlmostEqual(evaluate(np.array([10, 20.0]), np.array([12, 18.0])).wmape, 4 / 30)
        self.assertAlmostEqual(evaluate(np.array([10, 20.0]), np.array([12, 18.0])).bias, 0)
        suggestion = recommend_reorder(10, 10, lead_time_days=3)
        assert suggestion.suggested_order_units > 20
        assert recommend_reorder(0, 100, 1).suggested_order_units == 0
        with self.assertRaises(ValueError):
            recommend_reorder(-1, 10, 3)

    def test_full_pipeline(self):
        tmp_path = Path(self.enterContext(TemporaryDirectory()))
        result = run(str(tmp_path / "db.sqlite"), str(tmp_path / "out"), days=100, stores=1)
        assert result["quality"]["quality_pass"]
        assert result["gold_feature_rows"] == 600
