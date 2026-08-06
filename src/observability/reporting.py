from __future__ import annotations

from pathlib import Path
from typing import Any

from core.utils import write_text


CORE_METRICS = (
    "retrieval_hit_rate",
    "mean_token_f1",
    "judge_accuracy",
    "mean_judge_score",
)


def _escape(value: Any) -> str:
    if value is None:
        return "N/A"
    return str(value).replace("|", "\\|").replace("\n", " ")


def _format_value(value: Any) -> str:
    if value is None:
        return "N/A"
    if isinstance(value, bool):
        return "PASS" if value else "FAIL"
    if isinstance(value, float):
        return f"{value:.4f}"
    if isinstance(value, (dict, list)):
        return _escape(value)
    return _escape(value)


def _metric(metrics: dict[str, Any], name: str) -> Any:
    return metrics.get(name) if isinstance(metrics, dict) else None


def _numeric_metric(metrics: dict[str, Any], name: str) -> float | None:
    value = _metric(metrics, name)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _delta(current: float | None, reference: float | None) -> str:
    if current is None or reference is None:
        return "N/A"
    return f"{current - reference:+.4f}"


def _quality_lines(quality: dict[str, Any]) -> list[str]:
    checks = quality.get("checks", []) if isinstance(quality, dict) else []
    if not checks:
        return ["| N/A | N/A | N/A | N/A | N/A |"]
    lines: list[str] = []
    for check in checks:
        lines.append(
            "| {name} | {dimension} | {status} | {failed} | {expected} |".format(
                name=_escape(check.get("name")),
                dimension=_escape(check.get("dimension")),
                status="PASS" if check.get("passed") else "FAIL",
                failed=_escape(check.get("failed_rows", "N/A")),
                expected=_escape(check.get("expected")),
            )
        )
    return lines


def _ragas_summary(metrics: dict[str, Any]) -> str:
    ragas = metrics.get("ragas") if isinstance(metrics, dict) else None
    if not isinstance(ragas, dict):
        return _format_value(ragas)
    if "skipped" in ragas:
        return f"Skipped — {_escape(ragas['skipped'])}"
    if "error" in ragas:
        return f"Error — {_escape(ragas['error'])}"
    return _format_value(ragas)

def generate_phase1_report(
    report_path,
    source_summary: dict[str, Any],
    metrics: dict[str, Any],
    quality: dict[str, Any],
    freshness: dict[str, Any],
) -> None:
    """Write an evidence-based Markdown summary for the baseline pipeline."""
    source_rows = [f"| {_escape(key)} | {_format_value(value)} |" for key, value in source_summary.items()]
    if not source_rows:
        source_rows = ["| N/A | N/A |"]

    metric_rows = [
        f"| `{name}` | {_format_value(_metric(metrics, name))} |" for name in CORE_METRICS
    ]
    metric_rows.append(f"| `ragas` | {_ragas_summary(metrics)} |")

    freshness_rows = [
        ("Latest publication", freshness.get("latest_published")),
        ("Oldest publication", freshness.get("oldest_published")),
        ("Stale rows", freshness.get("stale_rows")),
        ("Total rows", freshness.get("total_rows")),
        ("Threshold (days)", freshness.get("freshness_threshold_days")),
        ("Freshness status", freshness.get("is_fresh")),
    ]

    lines = [
        "# Phase 1 Baseline Report",
        "",
        "> This report is generated from pipeline artifacts; values are not manually entered.",
        "",
        "## Source summary",
        "",
        "| Field | Value |",
        "| --- | --- |",
        *source_rows,
        "",
        "## Evaluation metrics",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
        *metric_rows,
        "",
        "## Data quality",
        "",
        f"Overall status: **{'PASS' if quality.get('passed') else 'FAIL'}**  ",
        f"Rows checked: **{_escape(quality.get('total_rows', 'N/A'))}**  ",
        f"Checks passed/failed: **{_escape(quality.get('passed_checks', 'N/A'))}/{_escape(quality.get('failed_checks', 'N/A'))}**",
        "",
        "| Check | Dimension | Status | Failed rows | Expectation |",
        "| --- | --- | --- | ---: | --- |",
        *_quality_lines(quality),
        "",
        "## Freshness",
        "",
        "| Signal | Value |",
        "| --- | --- |",
        *[f"| {label} | {_format_value(value)} |" for label, value in freshness_rows],
        "",
        "## Interpretation",
        "",
        f"- Data quality status: **{'PASS' if quality.get('passed') else 'FAIL'}**.",
        f"- Freshness status: **{'FRESH' if freshness.get('is_fresh') else 'STALE OR INVALID'}**.",
        f"- Retrieval hit rate: **{_format_value(metrics.get('retrieval_hit_rate'))}** across **{_format_value(metrics.get('samples'))}** evaluation samples.",
        "",
    ]
    write_text(Path(report_path), "\n".join(lines))


def generate_corruption_report(
    report_path,
    baseline_metrics: dict[str, Any],
    corrupted_metrics: dict[str, Any],
    repaired_metrics: dict[str, Any],
    corrupted_quality: dict[str, Any],
    repaired_quality: dict[str, Any],
    corrupted_freshness: dict[str, Any],
    repaired_freshness: dict[str, Any],
) -> None:
    """Write a baseline/corrupted/repaired comparison using measured artifacts."""
    metric_rows: list[str] = []
    for name in CORE_METRICS:
        baseline = _numeric_metric(baseline_metrics, name)
        corrupted = _numeric_metric(corrupted_metrics, name)
        repaired = _numeric_metric(repaired_metrics, name)
        metric_rows.append(
            "| `{name}` | {baseline} | {corrupted} | {repaired} | {impact} | {recovery} |".format(
                name=name,
                baseline=_format_value(baseline),
                corrupted=_format_value(corrupted),
                repaired=_format_value(repaired),
                impact=_delta(corrupted, baseline),
                recovery=_delta(repaired, corrupted),
            )
        )

    quality_rows = []
    for state, payload in (("Corrupted", corrupted_quality), ("Repaired", repaired_quality)):
        quality_rows.append(
            f"| {state} | {_format_value(payload.get('passed'))} | "
            f"{_escape(payload.get('passed_checks', 'N/A'))} | {_escape(payload.get('failed_checks', 'N/A'))} | "
            f"{_escape(payload.get('total_rows', 'N/A'))} |"
        )

    freshness_rows = []
    for state, payload in (("Corrupted", corrupted_freshness), ("Repaired", repaired_freshness)):
        freshness_rows.append(
            f"| {state} | {_format_value(payload.get('is_fresh'))} | "
            f"{_escape(payload.get('stale_rows', 'N/A'))} | {_escape(payload.get('total_rows', 'N/A'))} | "
            f"{_escape(payload.get('latest_published'))} | {_escape(payload.get('oldest_published'))} |"
        )

    baseline_hit = _numeric_metric(baseline_metrics, "retrieval_hit_rate")
    corrupted_hit = _numeric_metric(corrupted_metrics, "retrieval_hit_rate")
    repaired_hit = _numeric_metric(repaired_metrics, "retrieval_hit_rate")
    quality_recovered = bool(repaired_quality.get("passed")) and not bool(corrupted_quality.get("passed"))
    freshness_recovered = bool(repaired_freshness.get("is_fresh")) and not bool(corrupted_freshness.get("is_fresh"))

    lines = [
        "# Corruption and Repair Comparison Report",
        "",
        "> Baseline, corrupted and repaired metrics must be produced with the same evaluation set.",
        "",
        "## Evaluation comparison",
        "",
        "| Metric | Baseline | Corrupted | Repaired | Corruption impact | Repair recovery |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
        *metric_rows,
        "",
        "`Corruption impact = corrupted - baseline`; `repair recovery = repaired - corrupted`.",
        "",
        "## Data-quality comparison",
        "",
        "Baseline quality is documented in `phase1_report.md`; this function receives corrupted and repaired quality artifacts.",
        "",
        "| State | Overall status | Passed checks | Failed checks | Rows |",
        "| --- | --- | ---: | ---: | ---: |",
        *quality_rows,
        "",
        "### Failed checks after corruption",
        "",
        *(
            [
                f"- `{_escape(check.get('name'))}`: {_escape(check.get('failed_rows'))} failed row(s)."
                for check in corrupted_quality.get("checks", [])
                if not check.get("passed")
            ]
            or ["- None."]
        ),
        "",
        "## Freshness comparison",
        "",
        "| State | Status | Stale rows | Total rows | Latest | Oldest |",
        "| --- | --- | ---: | ---: | --- | --- |",
        *freshness_rows,
        "",
        "## Evidence-based observations",
        "",
        f"- Retrieval hit rate changed by **{_delta(corrupted_hit, baseline_hit)}** after corruption.",
        f"- Retrieval hit rate changed by **{_delta(repaired_hit, corrupted_hit)}** after repair.",
        f"- Data-quality recovery observed: **{'yes' if quality_recovered else 'no'}**.",
        f"- Freshness recovery observed: **{'yes' if freshness_recovered else 'no'}**.",
        "",
        "A causal conclusion should only be made when the corruption log, quality/freshness signals and evaluation metrics show corresponding changes.",
        "",
    ]
    write_text(Path(report_path), "\n".join(lines))
