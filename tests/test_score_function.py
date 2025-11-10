import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

from score_function import score_function, load_config, load_json  # noqa: E402

CONFIG = load_config(Path("score-function.yml"))
SAMPLE = load_json(Path("examples/metrics.sample.json"))


def test_faces_match_reference():
    result = score_function(CONFIG, SAMPLE)
    assert pytest.approx(result["faces"]["spec"], rel=1e-5) == 82.4085
    assert pytest.approx(result["faces"]["sec"], rel=1e-5) == 85.6


def test_gate_conditions():
    result = score_function(CONFIG, SAMPLE)
    assert result["gate_ok"] is True
    assert result["geo"] > 80


def test_penalty_floor_applied():
    low_metrics = json.loads(Path("examples/metrics.sample.json").read_text())
    low_metrics["code"]["SA"] = 0.2
    low_metrics["uncertainty_sigma"] = 0.5
    result = score_function(CONFIG, low_metrics)
    assert result["faces"]["code"] < CONFIG["gate"]["min_each"]
    assert result["final"] < 80
