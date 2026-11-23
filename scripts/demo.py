"""Run the full retail policy replay twice on a deterministic dataset."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from retail_decisions.pipeline import run


def main() -> None:
    with TemporaryDirectory() as folder:
        db, out = str(Path(folder)/'retail.sqlite'), str(Path(folder)/'result')
        first, second = run(db, out), run(db, out)
        assert second['source']['rows_inserted'] == 0
        assert first['model'] == second['model']
        print(json.dumps(dict(rows=first['gold_feature_rows'], replay_inserted=0,
                              holdout=first['model']['holdout_test'],
                              policy=first['inventory_scenario']), indent=2))


if __name__ == '__main__':
    main()
