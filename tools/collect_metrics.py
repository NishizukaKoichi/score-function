#!/usr/bin/env python3
"""Collect Score Function metrics from ESLint/Jest/pytest/Syft/Semgrep/Stryker outputs."""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, Optional


def clip(value: float) -> float:
    return max(0.0, min(1.0, value))


def ratio(part: float, whole: float) -> float:
    return 0.0 if whole <= 0 else part / whole


def warn(message: str) -> None:
    print(f"[collect-metrics] {message}", file=sys.stderr)


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Aggregate reports into Score Function metrics")
    parser.add_argument("--reports-dir", default="reports", help="Base directory for report files")
    parser.add_argument("--eslint", help="Path to ESLint JSON report (default: reports/eslint.json)")
    parser.add_argument("--jest", help="Path to Jest coverage-summary.json")
    parser.add_argument("--pytest", help="Path to pytest json-report output")
    parser.add_argument("--stryker", help="Path to Stryker mutation report JSON")
    parser.add_argument("--semgrep", help="Path to Semgrep JSON output")
    parser.add_argument("--syft", help="Path to Syft JSON (with matches)")
    parser.add_argument("--spec", help="Optional spec metrics JSON override")
    parser.add_argument("--pr", help="Optional PR operations metrics JSON override")
    parser.add_argument("--dep", help="Optional deploy metrics JSON override")
    parser.add_argument("--strict", action="store_true", help="Fail if a required report is missing")
    return parser.parse_args(list(argv) if argv is not None else None)


def resolve(base: Path, override: Optional[str], default_name: str) -> Path:
    return Path(override) if override else (base / default_name)


def load_json(path: Path, *, label: str, required: bool) -> Optional[Any]:
    try:
        return json.loads(path.read_text())
    except FileNotFoundError:
        if required:
            raise SystemExit(f"Missing required report: {label} -> {path}")
        warn(f"missing optional report: {label} -> {path}")
        return None
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid JSON in {path}: {exc}") from exc


def summarize_eslint(report: Optional[Any]) -> Dict[str, float]:
    summary = {"files": 0.0, "errors": 0.0, "warnings": 0.0, "complexity": 0.0}
    if not isinstance(report, list):
        return summary
    files = len(report)
    errors = 0
    warnings = 0
    complexity_hits = 0
    for item in report:
        if not isinstance(item, dict):
            continue
        errors += int(item.get("errorCount", 0) + item.get("fatalErrorCount", 0))
        warnings += int(item.get("warningCount", 0))
        complexity_hits += sum(
            1
            for message in item.get("messages", [])
            if isinstance(message, dict) and str(message.get("ruleId", "")).startswith("complexity")
        )
    summary.update(
        {
            "files": float(files),
            "errors": float(errors),
            "warnings": float(warnings),
            "complexity": float(complexity_hits),
        }
    )
    return summary


def summarize_jest(report: Optional[Any]) -> Dict[str, float]:
    if not isinstance(report, dict):
        return {"coverage": 0.0}
    total = report.get("total", {})
    sections = [section for section in total.values() if isinstance(section, dict) and "pct" in section]
    if not sections:
        return {"coverage": 0.0}
    coverage = sum(float(section["pct"]) for section in sections) / (len(sections) * 100.0)
    return {"coverage": clip(coverage)}


def summarize_pytest(report: Optional[Any]) -> Dict[str, float]:
    summary = {"pass_rate": 0.0, "fail_rate": 0.0, "skipped_rate": 0.0, "avg_duration": 0.0}
    if not isinstance(report, dict):
        return summary
    total = float(report.get("summary", {}).get("total", 0))
    passed = float(report.get("summary", {}).get("passed", 0))
    failed = float(report.get("summary", {}).get("failed", 0)) + float(report.get("summary", {}).get("error", 0))
    skipped = float(report.get("summary", {}).get("skipped", 0))
    tests = report.get("tests")
    durations = []
    if isinstance(tests, list):
        for case in tests:
            if not isinstance(case, dict):
                continue
            duration = case.get("duration")
            if isinstance(duration, (int, float)):
                durations.append(float(duration))
    avg_duration = sum(durations) / len(durations) if durations else float(report.get("duration", 0.0))
    pass_rate = ratio(passed, total)
    fail_rate = ratio(failed, total) if total else 0.0
    skipped_rate = ratio(skipped, total)
    summary.update(
        {
            "pass_rate": clip(pass_rate),
            "fail_rate": clip(fail_rate if fail_rate > 0 else 1.0 - pass_rate),
            "skipped_rate": clip(skipped_rate),
            "avg_duration": clip(avg_duration / 600.0),  # normalize 10m window
        }
    )
    return summary


def summarize_stryker(report: Optional[Any]) -> Dict[str, float]:
    if not isinstance(report, dict):
        return {"mutation_score": 0.0}
    score = report.get("mutationScore") or report.get("mutationScoreBasedOnCoveredCode")
    if isinstance(score, (int, float)):
        return {"mutation_score": clip(float(score) / 100.0)}
    return {"mutation_score": 0.0}


def summarize_semgrep(report: Optional[Any]) -> Dict[str, float]:
    counts = Counter()
    total = 0
    if isinstance(report, dict):
        results = report.get("results")
        if isinstance(results, list):
            for item in results:
                if not isinstance(item, dict):
                    continue
                severity = (
                    item.get("extra", {}).get("severity")
                    if isinstance(item.get("extra"), dict)
                    else None
                )
                severity = str(severity or "info").lower()
                counts[severity] += 1
                total += 1
    high = counts.get("high", 0) + counts.get("error", 0)
    medium = counts.get("medium", 0) + counts.get("warning", 0)
    low = counts.get("low", 0) + counts.get("info", 0)
    return {
        "total": float(total),
        "high": float(high),
        "medium": float(medium),
        "low": float(low),
        "density": clip(total / 100.0),
        "high_ratio": clip(ratio(high, total)),
    }


def summarize_syft(report: Optional[Any]) -> Dict[str, float]:
    if not isinstance(report, dict):
        return {"vulns": 0.0, "critical": 0.0, "avg_cvss": 0.0, "confirmed": 0.0}
    matches = report.get("matches")
    if not isinstance(matches, list):
        return {"vulns": 0.0, "critical": 0.0, "avg_cvss": 0.0, "confirmed": 0.0}
    severities = Counter()
    cvss_scores = []
    confirmed = 0
    for match in matches:
        if not isinstance(match, dict):
            continue
        vuln = match.get("vulnerability")
        severity = None
        if isinstance(vuln, dict):
            severity = vuln.get("severity")
            cvss_list = vuln.get("cvss")
            if isinstance(cvss_list, list):
                for entry in cvss_list:
                    metrics = entry.get("metrics") if isinstance(entry, dict) else None
                    if isinstance(metrics, list):
                        for metric in metrics:
                            score = metric.get("score") if isinstance(metric, dict) else None
                            if isinstance(score, (int, float)):
                                cvss_scores.append(float(score))
        severity = str(severity or match.get("severity", "info")).lower()
        severities[severity] += 1
        status = str(match.get("status", "")).lower()
        if status in {"affected", "vulnerable"}:
            confirmed += 1
    avg_cvss = (sum(cvss_scores) / len(cvss_scores)) if cvss_scores else 0.0
    return {
        "vulns": float(sum(severities.values())),
        "critical": float(severities.get("critical", 0)),
        "avg_cvss": clip(avg_cvss / 10.0),
        "confirmed": float(confirmed),
    }


def build_spec(raw: Optional[Any]) -> Dict[str, float]:
    default = {"RC": 0.8, "TR": 0.75, "AM": 0.2, "CN": 0.15, "EX": 0.8}
    if not isinstance(raw, dict):
        return default
    merged = default.copy()
    for key, value in raw.items():
        try:
            merged[key] = clip(float(value))
        except (TypeError, ValueError):
            warn(f"invalid spec value for {key}: {value}")
    return merged


def build_pr(raw: Optional[Any]) -> Dict[str, float]:
    default = {"RR": 0.9, "risk": 0.3, "DV": 0.6, "RB": 0.05, "CI": 0.95}
    if not isinstance(raw, dict):
        return default
    merged = default.copy()
    for key, value in raw.items():
        try:
            merged[key] = clip(float(value))
        except (TypeError, ValueError):
            warn(f"invalid PR value for {key}: {value}")
    return merged


def build_dep(eslint: Dict[str, float], pytest: Dict[str, float], jest: Dict[str, float],
              semgrep: Dict[str, float], syft: Dict[str, float], raw: Optional[Any]) -> Dict[str, float]:
    base = {
        "SR": clip(pytest["pass_rate"] or 0.85),
        "CFR": clip(pytest["fail_rate"] or 0.05),
        "MT": clip(pytest["avg_duration"]),
        "RBK": clip(0.3 * pytest["fail_rate"] + 0.7 * ratio(syft["critical"], max(1.0, syft["vulns"] + 1))),
        "PRG": clip(semgrep["high_ratio"]),
        "EB": clip(1.0 - jest["coverage"]),
    }
    if not isinstance(raw, dict):
        return base
    merged = base.copy()
    for key, value in raw.items():
        try:
            merged[key] = clip(float(value))
        except (TypeError, ValueError):
            warn(f"invalid deploy value for {key}: {value}")
    return merged


def build_metrics(reports: Dict[str, Any]) -> Dict[str, Any]:
    eslint = summarize_eslint(reports.get("eslint"))
    jest = summarize_jest(reports.get("jest"))
    pytest = summarize_pytest(reports.get("pytest"))
    syft = summarize_syft(reports.get("syft"))
    semgrep = summarize_semgrep(reports.get("semgrep"))
    stryker = summarize_stryker(reports.get("stryker"))

    lint_denominator = max(1.0, eslint["files"] * 5.0)
    code_sa = clip(1.0 - (eslint["errors"] / lint_denominator))
    code_cc = clip(ratio(eslint["complexity"], max(1.0, eslint["files"])))
    code_dp = clip(eslint["warnings"] / lint_denominator)

    mutation_score = stryker["mutation_score"]
    test_failures = pytest["fail_rate"]

    spec_metrics = build_spec(reports.get("spec"))

    code_metrics = {
        "SA": code_sa,
        "CC": code_cc,
        "DP": code_dp,
        "DE": clip(0.6 + 0.4 * jest["coverage"]),
        "DT": clip(0.5 + 0.5 * (1.0 - eslint["warnings"] / lint_denominator)),
        "PF": clip(0.7 + 0.3 * (1.0 - ratio(syft["critical"], max(1.0, syft["vulns"] + 1)))),
    }

    test_metrics = {
        "CV": jest["coverage"],
        "MT": clip(max(mutation_score, pytest["pass_rate"])),
        "FL": clip(test_failures),
        "SK": pytest["skipped_rate"],
        "ST": pytest["pass_rate"],
    }

    sec_metrics = {
        "CVSS_sum": syft["avg_cvss"],
        "SE": clip(1.0 - semgrep["density"]),
        "dep_vulns": clip(syft["vulns"] / 50.0),
        "AT": clip(1.0 - semgrep["high_ratio"]),
        "ML": clip(1.0 - ratio(syft["critical"], max(1.0, syft["vulns"] + 1))),
        "critical_count": int(round(syft["critical"])),
    }

    pr_metrics = build_pr(reports.get("pr"))
    dep_metrics = build_dep(eslint, pytest, jest, semgrep, syft, reports.get("dep"))

    sigma = clip(0.05 + 0.4 * semgrep["density"] + 0.4 * ratio(syft["critical"], max(1.0, syft["vulns"] + 5)))

    return {
        "spec": spec_metrics,
        "code": code_metrics,
        "test": test_metrics,
        "sec": sec_metrics,
        "pr": pr_metrics,
        "dep": dep_metrics,
        "uncertainty_sigma": sigma,
    }


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)
    base = Path(args.reports_dir)
    required = args.strict

    reports = {
        "eslint": load_json(resolve(base, args.eslint, "eslint.json"), label="ESLint", required=required),
        "jest": load_json(resolve(base, args.jest, "coverage-summary.json"), label="Jest", required=required),
        "pytest": load_json(resolve(base, args.pytest, "pytest-report.json"), label="pytest", required=required),
        "stryker": load_json(resolve(base, args.stryker, "stryker-report.json"), label="Stryker", required=required),
        "semgrep": load_json(resolve(base, args.semgrep, "semgrep.json"), label="Semgrep", required=required),
        "syft": load_json(resolve(base, args.syft, "syft.json"), label="Syft", required=required),
        "spec": load_json(Path(args.spec), label="Spec", required=False) if args.spec else None,
        "pr": load_json(Path(args.pr), label="PR", required=False) if args.pr else None,
        "dep": load_json(Path(args.dep), label="Deploy", required=False) if args.dep else None,
    }

    metrics = build_metrics(reports)
    json.dump(metrics, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
