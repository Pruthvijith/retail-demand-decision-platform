"""End-to-end batch orchestration entrypoint with artifact and quality gates."""

import argparse
import json
from pathlib import Path

from retail_decisions.forecast import train_and_backtest
from retail_decisions.synthetic import populate
from retail_decisions.warehouse import connect, materialize_features, quality_report


def run(db_path: str, output: str, days: int = 180, stores: int = 3) -> dict:
    source = populate(db_path, days=days, stores=stores)
    with connect(db_path) as db:
        quality = quality_report(db)
        if not quality["quality_pass"]:
            raise ValueError(f"Invalid bronze layer: {quality}")
        mart_rows = materialize_features(db)
    model_report = train_and_backtest(db_path, output)
    report = {"source": source, "quality": quality, "gold_feature_rows": mart_rows,
              "model": model_report, "inventory_scenario": model_report["one_day_inventory_scenario"]}
    Path(output).mkdir(parents=True, exist_ok=True)
    (Path(output) / "pipeline_report.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="retail.sqlite")
    parser.add_argument("--output", default="artifacts")
    parser.add_argument("--days", type=int, default=180)
    parser.add_argument("--stores", type=int, default=3)
    args = parser.parse_args()
    report = run(args.db, args.output, days=args.days, stores=args.stores)
    print(json.dumps({"quality": report["quality"],
                      "champion": report["model"]["selected_champion"],
                      "holdout": report["model"]["holdout_test"],
                      "replenishment": report["inventory_scenario"]}, indent=2))


if __name__ == "__main__":
    main()
