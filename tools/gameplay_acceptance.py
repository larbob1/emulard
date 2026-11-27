#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Evaluate owner-attested gameplay evidence; never export paths or metadata."""
import argparse
import hashlib
import json
from math import isfinite
from pathlib import Path
import re

from frame_report import summarize

MILESTONES = (5, 10, 20, 30)
CONFIG_FIELDS = ("revision", "platform", "driver", "hardware", "profile", "scene",
                 "settings", "cache_state", "flags", "resolution", "warmup")
CHECKS = ("full_scene", "responsive_controls", "no_crash", "no_missing_required_draws",
          "no_invalid_memory_access", "measured_window_matches_log", "independent_trial")


def number(value):
    return type(value) in (int, float) and isfinite(value)


def validate_config(config):
    if not isinstance(config, dict):
        return False
    if any(not isinstance(config.get(key), str) or not config[key].strip()
           for key in CONFIG_FIELDS):
        return False
    return bool(re.fullmatch(r"[0-9a-fA-F]{40}", config["revision"]))


def run_evidence(run, report):
    frames = report.get("individual_frame_times", {})
    quality = report.get("interval_sample_quality", {})
    count = frames.get("samples", 0)
    elapsed = run.get("elapsed_seconds")
    visible = run.get("correctly_displayed_frames")
    checks = run.get("checks", {})
    checks = checks if isinstance(checks, dict) else {}
    reasons = []
    failures = []
    valid_elapsed = number(elapsed) and elapsed > 0
    valid_visible = type(visible) is int and visible >= 0
    if not valid_elapsed or not valid_visible:
        reasons.append("owner_frame_count_or_elapsed_missing_or_invalid")
    if any(checks.get(key) is not True for key in CHECKS):
        reasons.append("owner_attestation_incomplete_or_failed")
    if any(checks.get(key) is False for key in CHECKS):
        failures.append("owner_reported_failed_check")
    if not count or not frames.get("duration_ms_rounded_samples"):
        reasons.append("individual_frame_samples_missing")
    if frames.get("invalid_batches", 0):
        reasons.append("invalid_frame_batches")
    if not report.get("samples"):
        reasons.append("interval_samples_missing")
    if quality.get("invalid_after_warmup", 0):
        reasons.append("invalid_interval_samples")
    drops = report.get("intervals_with_dropped_draws")
    if drops is None:
        reasons.append("drop_evidence_missing")
    elif drops > 0:
        failures.append("reported_dropped_draws")
    p = frames.get("frame_ms_percentiles", {})
    p95, p99 = p.get("p95"), p.get("p99")
    if not number(p95) or not number(p99):
        reasons.append("frame_tail_evidence_missing")
    if valid_elapsed and count:
        # Rounded individual durations introduce up to 0.5 ms per sample.
        # Allow up to one second for operator timing boundary uncertainty.
        delta = abs(frames["duration_ms_rounded_samples"] - elapsed * 1000)
        if delta > 1000 + 0.5 * count:
            reasons.append("frame_log_duration_not_consistent_with_owner_window")
    if valid_visible and count and visible > count:
        reasons.append("visible_frame_count_exceeds_logged_samples")
    fps = visible / elapsed if valid_elapsed and valid_visible else None
    return {
        "elapsed_seconds": elapsed if valid_elapsed else None,
        "correctly_displayed_frames": visible if valid_visible else None,
        "owner_attested_visible_fps": round(fps, 6) if fps is not None else None,
        "approx_present_fps": frames.get("approx_present_fps"),
        "individual_frame_samples": count,
        "interval_samples": report.get("samples", 0),
        "p95_ms": p95,
        "p99_ms": p99,
        "reported_drop_intervals": drops,
        "evidence_issues": reasons,
        "correctness_failures": failures,
        "milestones": {
            str(target): milestone(target, fps, elapsed, p95, p99, reasons, failures)
            for target in MILESTONES
        },
    }


def milestone(target, fps, elapsed, p95, p99, issues, failures):
    if failures:
        return "failed"
    if issues:
        return "insufficient_evidence"
    if fps < target:
        return "failed"
    if target == 30:
        if elapsed < 600 or p95 > 50 or p99 > 100:
            return "failed"
    return "meets_owner_attested_criteria"


def evaluate(manifest, reports):
    if not isinstance(manifest, dict) or not validate_config(manifest.get("configuration")):
        raise ValueError("invalid reference configuration")
    runs = manifest.get("runs")
    if not isinstance(runs, list) or not runs or len(runs) != len(reports):
        raise ValueError("invalid runs")
    if any(not isinstance(run, dict) for run in runs):
        raise ValueError("invalid run")
    identifiers = [run.get("id") for run in runs]
    if any(not isinstance(i, str) or not i.strip() for i in identifiers):
        raise ValueError("invalid trial identifier")
    if len(set(identifiers)) != len(identifiers):
        raise ValueError("duplicate trial identifiers")
    if any(run.get("configuration") != manifest["configuration"] for run in runs):
        raise ValueError("mismatched reference configuration")
    evidence = [run_evidence(run, report) for run, report in zip(runs, reports)]
    gates = {}
    for target in MILESTONES:
        states = [run["milestones"][str(target)] for run in evidence]
        # Retain failures even if more runs have not yet been collected.
        if "failed" in states:
            status = "failed"
        elif len(states) < 3 or "insufficient_evidence" in states:
            status = "insufficient_evidence"
        else:
            status = "meets_owner_attested_criteria"
        gates[str(target)] = {"status": status,
                              "qualifying_runs": states.count("meets_owner_attested_criteria"),
                              "failed_runs": states.count("failed"),
                              "insufficient_runs": states.count("insufficient_evidence")}
    return {
        "runs": evidence,
        "milestones": gates,
        "independent_trials_operator_attested": len(runs) >= 3 and all(
            isinstance(run.get("checks"), dict)
            and run["checks"].get("independent_trial") is True for run in runs),
        "independently_verified_gameplay": False,
        "note": "Local evaluation of owner-attested counts, correctness and matched configuration, not independent gameplay verification. Individual frame times are rounded present durations, not proven displayed frames. Missing whole log records may be undetectable. M5 requires every trial >=600 s, >=30 correctly displayed FPS, p95 <=50 ms, p99 <=100 ms; all gates require at least three independent trials. No configuration strings, paths or IDs exported.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    args = parser.parse_args()
    try:
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        if not isinstance(manifest, dict) or not isinstance(manifest.get("runs"), list):
            raise ValueError("invalid manifest")
        paths, digests, reports = set(), set(), []
        for run in manifest["runs"]:
            if not isinstance(run, dict) or not isinstance(run.get("log"), str):
                raise ValueError("invalid log reference")
            path = (args.manifest.parent / run["log"]).resolve()
            if path in paths:
                raise ValueError("repeated input path")
            paths.add(path)
            # Hash locally while parsing; never export a digest or raw log.
            digest = hashlib.sha256()
            with path.open("rb") as handle:
                def lines():
                    for line in handle:
                        digest.update(line)
                        yield line.decode("utf-8", errors="replace")
                report = summarize(lines(), target_fps=30)
            fingerprint = digest.digest()
            if fingerprint in digests:
                raise ValueError("identical log content")
            digests.add(fingerprint)
            reports.append(report)
        result = evaluate(manifest, reports)
    except (OSError, ValueError, TypeError, OverflowError):
        print(json.dumps({"status": "invalid_or_unavailable_evidence"}))
        return 1
    print(json.dumps(result, indent=2, allow_nan=False))
    return 0 if result["milestones"]["30"]["status"] == "meets_owner_attested_criteria" else 2


if __name__ == "__main__":
    raise SystemExit(main())
