#!/usr/bin/env python3
"""Score Function calculator CLI (dependency-free)."""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, Tuple

FACE_ORDER = ("spec", "code", "test", "sec", "pr", "dep")


def clip(value: float, lower: float = 0.0, upper: float = 1.0) -> float:
    """Clamp value into [lower, upper]."""
    return max(lower, min(upper, value))


def logistic(x: float, tau: float, k: float) -> float:
    """Logistic function H(x; tau, k)."""
    return 1.0 / (1.0 + math.exp(-k * (x - tau)))


def penalty(scale: float, value: float, tau: float, k: float) -> float:
    """Return multiplicative penalty term (1 - scale * H(...))."""
    return 1.0 - scale * logistic(value, tau, k)


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError as exc:  # pragma: no cover - informative error
        raise SystemExit(f"Invalid JSON in {path}: {exc}")


def _parse_scalar(value: str) -> Any:
    if value.startswith("{") and value.endswith("}"):
        import re

        jsonish = re.sub(r"([\{,]\s*)([A-Za-z_][\w-]*)\s*:", r'\1"\\2":', value)
        jsonish = jsonish.replace("'", '"')
        return json.loads(jsonish)
    if value.startswith('"') and value.endswith('"'):
        return value[1:-1]
    if value.startswith("'") and value.endswith("'"):
        return value[1:-1]
    lowered = value.lower()
    if lowered in {"true", "false"}:
        return lowered == "true"
    if lowered in {"null", "~"}:
        return None
    try:
        if "." in value or "e" in value.lower():
            return float(value)
        return int(value)
    except ValueError:
        return value


def _load_simple_yaml(text: str) -> Dict[str, Any]:
    root: Dict[str, Any] = {}
    stack: list[Tuple[int, Dict[str, Any]]] = [(-1, root)]
    for raw in text.splitlines():
        stripped_line = raw.split("#", 1)[0].rstrip()
        if not stripped_line.strip():
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        while len(stack) > 1 and indent <= stack[-1][0]:
            stack.pop()
        current = stack[-1][1]
        if ":" not in stripped_line:
            raise SystemExit(f"Unsupported line in YAML: {raw}")
        key, value = stripped_line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if not value:
            new_dict: Dict[str, Any] = {}
            current[key] = new_dict
            stack.append((indent, new_dict))
            continue
        current[key] = _parse_scalar(value)
    return root


def load_config(path: Path) -> Dict[str, Any]:
    text = path.read_text()
    try:
        import yaml  # type: ignore

        return yaml.safe_load(text)
    except Exception:
        pass
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return _load_simple_yaml(text)


def _ensure_face(metrics: Dict[str, Any], face: str) -> Dict[str, Any]:
    try:
        return metrics[face]
    except KeyError as exc:  # pragma: no cover - input validation
        raise SystemExit(f"Missing face '{face}' in metrics") from exc


def _get(metric_face: Dict[str, Any], key: str) -> float:
    try:
        return float(metric_face[key])
    except KeyError as exc:  # pragma: no cover - input validation
        raise SystemExit(f"Missing metric '{key}'") from exc


def compute_faces(config: Dict[str, Any], metrics: Dict[str, Any]) -> Dict[str, float]:
    weights = config["weights"]
    thresholds = config["thresholds"]
    k = config.get("k_steep", 14)

    faces: Dict[str, float] = {}

    spec_metrics = _ensure_face(metrics, "spec")
    rc = clip(_get(spec_metrics, "RC"))
    tr = clip(_get(spec_metrics, "TR"))
    am = clip(_get(spec_metrics, "AM"))
    cn = clip(_get(spec_metrics, "CN"))
    ex = clip(_get(spec_metrics, "EX"))
    spec_score = 100.0 * (
        weights["spec"]["RC"] * rc
        + weights["spec"]["TR"] * tr
        + weights["spec"]["AM_inv"] * (1.0 - am)
        + weights["spec"]["CN_inv"] * (1.0 - cn)
        + weights["spec"]["EX"] * ex
    )
    spec_pen = penalty(0.3, am, thresholds["spec"]["ambig_tau"], k) * penalty(
        0.3, cn, thresholds["spec"]["conflict_tau"], k
    )
    faces["spec"] = spec_score * spec_pen

    code_metrics = _ensure_face(metrics, "code")
    sa = clip(_get(code_metrics, "SA"))
    cc = clip(_get(code_metrics, "CC"))
    dp = clip(_get(code_metrics, "DP"))
    de = clip(_get(code_metrics, "DE"))
    dt = clip(_get(code_metrics, "DT"))
    pf = clip(_get(code_metrics, "PF"))
    code_score = 100.0 * (
        weights["code"]["SA"] * sa
        + weights["code"]["CC_inv"] * (1.0 - cc)
        + weights["code"]["DP_inv"] * (1.0 - dp)
        + weights["code"]["DE"] * de
        + weights["code"]["DT"] * dt
        + weights["code"]["PF"] * pf
    )
    code_pen = penalty(0.4, cc, thresholds["code"]["cc_tau"], k)
    faces["code"] = code_score * code_pen

    test_metrics = _ensure_face(metrics, "test")
    cv = clip(_get(test_metrics, "CV"))
    mt = clip(_get(test_metrics, "MT"))
    fl = clip(_get(test_metrics, "FL"))
    sk = clip(_get(test_metrics, "SK"))
    st = clip(_get(test_metrics, "ST"))
    test_score = 100.0 * (
        weights["test"]["CV"] * cv
        + weights["test"]["MT"] * mt
        + weights["test"]["FL_inv"] * (1.0 - fl)
        + weights["test"]["SK_inv"] * (1.0 - sk)
        + weights["test"]["ST"] * st
    )
    test_pen = penalty(0.5, 1.0 - mt, thresholds["test"]["low_mt_tau"], k) * penalty(
        0.3, 1.0 - cv, thresholds["test"]["low_cv_tau"], k
    )
    faces["test"] = test_score * test_pen

    sec_metrics = _ensure_face(metrics, "sec")
    vv = 1.0 - clip(_get(sec_metrics, "CVSS_sum"))
    se = clip(_get(sec_metrics, "SE"))
    dpv = clip(_get(sec_metrics, "dep_vulns"))
    at = clip(_get(sec_metrics, "AT"))
    ml = clip(_get(sec_metrics, "ML"))
    sec_score = 100.0 * (
        weights["sec"]["VV"] * vv
        + weights["sec"]["SE"] * se
        + weights["sec"]["DPV_inv"] * (1.0 - dpv)
        + weights["sec"]["AT"] * at
        + weights["sec"]["ML"] * ml
    )
    if int(sec_metrics.get("critical_count", 0)) >= 1:
        sec_score *= 0.25
    faces["sec"] = sec_score

    pr_metrics = _ensure_face(metrics, "pr")
    rr = clip(_get(pr_metrics, "RR"))
    rk = clip(_get(pr_metrics, "risk"))
    dv = clip(_get(pr_metrics, "DV"))
    rb = clip(_get(pr_metrics, "RB"))
    ci = clip(_get(pr_metrics, "CI"))
    pr_score = 100.0 * (
        weights["pr"]["RR"] * rr
        + weights["pr"]["RK_inv"] * (1.0 - rk)
        + weights["pr"]["DV"] * dv
        + weights["pr"]["RB_inv"] * (1.0 - rb)
        + weights["pr"]["CI"] * ci
    )
    pr_pen = penalty(0.4, rk, thresholds["pr"]["risk_tau"], k)
    faces["pr"] = pr_score * pr_pen

    dep_metrics = _ensure_face(metrics, "dep")
    sr = clip(_get(dep_metrics, "SR"))
    cfr = clip(_get(dep_metrics, "CFR"))
    mt_dep = clip(_get(dep_metrics, "MT"))
    rbk = clip(_get(dep_metrics, "RBK"))
    prg = clip(_get(dep_metrics, "PRG"))
    eb = clip(_get(dep_metrics, "EB"))
    dep_score = 100.0 * (
        weights["dep"]["SR"] * sr
        + weights["dep"]["CFR_inv"] * (1.0 - cfr)
        + weights["dep"]["MT_inv"] * (1.0 - mt_dep)
        + weights["dep"]["RBK_inv"] * (1.0 - rbk)
        + weights["dep"]["PRG_inv"] * (1.0 - prg)
        + weights["dep"]["EB_inv"] * (1.0 - eb)
    )
    dep_pen = penalty(0.5, prg, thresholds["dep"]["perf_reg_tau"], k) * penalty(
        0.3, cfr, thresholds["dep"]["cfr_tau"], k
    )
    faces["dep"] = dep_score * dep_pen

    return faces


def score_function(config: Dict[str, Any], metrics: Dict[str, Any]) -> Dict[str, Any]:
    faces = compute_faces(config, metrics)
    profile = config.get("profile", "sre")
    weights = config.get("external_weights", {}).get(profile, {})
    floor_each = config["gate"]["floor_each"]

    weighted_faces = {
        face: faces[face] * weights.get(face, 1.0)
        for face in FACE_ORDER
    }

    adjusted = [max(floor_each, weighted_faces[face]) / 100.0 for face in FACE_ORDER]
    geo = 100.0 * math.prod(adjusted) ** (1.0 / len(adjusted))

    sigma = clip(float(metrics.get("uncertainty_sigma", 0.0)))
    final = geo * (1.0 - 0.1 * sigma)

    gate_ok = min(faces.values()) >= config["gate"]["min_each"] and geo >= config["gate"]["min_geo"]

    return {
        "faces": {face: round(faces[face], 4) for face in FACE_ORDER},
        "weighted_faces": {face: round(weighted_faces[face], 4) for face in FACE_ORDER},
        "geo": round(geo, 4),
        "final": round(final, 4),
        "gate_ok": bool(gate_ok),
        "profile": profile,
    }


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Score Function calculator")
    parser.add_argument("config", help="Path to score-function.yml (or JSON)")
    parser.add_argument("metrics", help="Path to metrics.json")
    args = parser.parse_args(list(argv) if argv is not None else None)

    config_path = Path(args.config)
    metrics_path = Path(args.metrics)

    config = load_config(config_path)
    metrics = load_json(metrics_path)
    result = score_function(config, metrics)
    json.dump(result, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
