#!/usr/bin/env python3
"""Collect metrics for the Score Function (template for ESLint/Jest/pytest/Syft/Semgrep/Stryker)."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

REPORTS = {
    "eslint": Path("reports/eslint.json"),
    "jest": Path("reports/coverage-summary.json"),
    "pytest": Path("reports/pytest.json"),
    "semgrep": Path("reports/semgrep.json"),
    "syft": Path("reports/syft.json"),
    "stryker": Path("reports/stryker-report.json"),
}


def clip(value: float) -> float:
    return max(0.0, min(1.0, value))


def ratio(part: float, whole: float) -> float:
    return 0.0 if whole <= 0 else part / whole


def load_report(path: Path) -> Optional[Any]:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        print(f"warning: cannot parse {path}: {exc}", file=sys.stderr)
        return None


def summarize_eslint(report: Optional[Any]) -> Dict[str, float]:
    if not isinstance(report, list):
        return {"files": 0.0, "errors": 0.0, "warnings": 0.0, "complexity": 0.0}
    files = len(report)
    errors = sum((item.get("errorCount", 0) + item.get("fatalErrorCount", 0)) for item in report)
    warnings = sum(item.get("warningCount", 0) for item in report)
    complexity_hits = sum(
        1
        for item in report
        for message in item.get("messages", [])
        if message.get("ruleId", "").startswith("complexity")
    )
    return {
        "files": float(files),
        "errors": float(errors),
        "warnings": float(warnings),
        "complexity": float(complexity_hits),
    }


def summarize_jest(report: Optional[Any]) -> Dict[str, float]:
    coverage = 0.0
    if isinstance(report, dict):
        total = report.get("total", {})
        sections = [section for section in total.values() if isinstance(section, dict) and "pct" in section]
        if sections:
            coverage = clip(sum(section["pct"] for section in sections) / (len(sections) * 100.0))
    return {"coverage": coverage}


def summarize_pytest(report: Optional[Any]) -> Dict[str, float]:
    if not isinstance(report, dict):
        return {"pass_rate": 0.0, "failures": 0.0}
    summary = report.get("summary", {})
    total = float(summary.get("total", 0))
    passed = float(summary.get("passed", 0))
    failures = float(summary.get("failed", 0)) + float(summary.get("error", 0))
    return {"pass_rate": clip(ratio(passed, total)), "failures": clip(ratio(failures, total))}


def summarize_stryker(report: Optional[Any]) -> Dict[str, float]:
    if not isinstance(report, dict):
        return {"mutation_score": 0.0}
    score = report.get("mutationScore")
    if isinstance(score, (int, float)):
        return {"mutation_score": clip(float(score) / 100.0)}
    return {"mutation_score": 0.0}


def summarize_semgrep(report: Optional[Any]) -> Dict[str, float]:
    if not isinstance(report, dict):
        return {"findings": 0.0}
    results = report.get("results")
    if isinstance(results, list):
        return {"findings": float(len(results))}
    return {"findings": 0.0}


def summarize_syft(report: Optional[Any]) -> Dict[str, float]:
    if not isinstance(report, dict):
        return {"vulns": 0.0, "critical": 0.0}
    matches = report.get("matches", [])
    if not isinstance(matches, list):
        return {"vulns": 0.0, "critical": 0.0}
    vulns = len(matches)
    critical = sum(1 for item in matches if item.get("severity", "").lower() == "critical")
    return {"vulns": float(vulns), "critical": float(critical)}


def build_metrics(reports: Dict[str, Any]) -> Dict[str, Any]:
    eslint = summarize_eslint(reports.get("eslint"))
    jest = summarize_jest(reports.get("jest"))
    pytest = summarize_pytest(reports.get("pytest"))
    stryker = summarize_stryker(reports.get("stryker"))
    semgrep = summarize_semgrep(reports.get("semgrep"))
    syft = summarize_syft(reports.get("syft"))

    lint_denominator = max(1.0, eslint["files"] * 5.0)
    code_sa = clip(1.0 - (eslint["errors"] / lint_denominator))
    code_cc = clip(ratio(eslint["complexity"], max(1.0, eslint["files"])))
    code_dp = clip(eslint["warnings"] / lint_denominator)

    mutation_score = stryker["mutation_score"]
    test_failures = max(pytest["failures"], 1.0 - pytest["pass_rate"])

    spec_metrics = {
        "RC": 0.8,
        "TR": 0.75,
        "AM": 0.2,
        "CN": 0.15,
        "EX": 0.8,
    }

    code_metrics = {
        "SA": code_sa,
        "CC": code_cc,
        "DP": code_dp,
        "DE": 0.85,
        "DT": 0.75,
        "PF": 0.6,
    }

    jest_coverage = jest["coverage"]
    test_metrics = {
        "CV": jest_coverage,
        "MT": mutation_score or pytest["pass_rate"],
        "FL": clip(test_failures),
        "SK": 0.05,
        "ST": clip(pytest["pass_rate"]),
    }

    sec_metrics = {
        "CVSS_sum": clip(syft["vulns"] / 25.0),
        "SE": clip(1.0 - semgrep["findings"] / 100.0),
        "dep_vulns": clip(syft["vulns"] / 50.0),
        "AT": 0.7,
        "ML": 0.6,
        "critical_count": int(syft["critical"]),
    }

    pr_metrics = {
        "RR": 0.9,
        "risk": 0.3,
        "DV": 0.6,
        "RB": 0.05,
        "CI": 0.95,
    }

    dep_metrics = {
        "SR": 0.9,
        "CFR": clip(test_failures),
        "MT": 0.4,
        "RBK": 0.05,
        "PRG": clip(semgrep["findings"] / 50.0),
        "EB": 0.1,
    }

    return {
        "spec": spec_metrics,
        "code": code_metrics,
        "test": test_metrics,
        "sec": sec_metrics,
        "pr": pr_metrics,
        "dep": dep_metrics,
        "uncertainty_sigma": 0.12,
    }


def main(argv: Iterable[str] | None = None) -> int:
    data = {name: load_report(path) for name, path in REPORTS.items()}
    metrics = build_metrics(data)
    json.dump(metrics, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
