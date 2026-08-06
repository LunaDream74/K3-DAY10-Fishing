from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pandas as pd

from core.config import load_settings
from evaluation.testset import build_test_set
from observability.quality import build_freshness_report, run_data_quality_checks
from observability.reporting import generate_corruption_report, generate_phase1_report


PROJECT_DIR = Path(__file__).resolve().parents[1]


def _clean_df() -> pd.DataFrame:
    return pd.read_json(PROJECT_DIR / "data" / "clean" / "papers_clean.json")


def _settings_with_quality_dir(tmp_path: Path):
    settings = load_settings(PROJECT_DIR)
    return replace(settings, paths=replace(settings.paths, quality_dir=tmp_path / "quality"))


def test_build_test_set_is_deterministic_and_grounded(tmp_path: Path) -> None:
    df = _clean_df()
    first = build_test_set(df, tmp_path / "first.json")
    second = build_test_set(df.sample(frac=1, random_state=42), tmp_path / "second.json")

    assert first == second
    assert len(first) == 24  # 8 representative papers x summary/authors/date.
    assert {item["question_type"] for item in first} == {"summary", "authors", "date"}
    assert len({item["id"] for item in first}) == len(first)
    assert all(item["ground_truth"] for item in first)
    assert all(len(item["ground_truth_doc_ids"]) == 1 for item in first)
    assert {item["ground_truth_doc_ids"][0] for item in first}.issubset(set(df["paper_id"]))


def test_clean_data_passes_quality_and_freshness(tmp_path: Path) -> None:
    df = _clean_df()
    settings = _settings_with_quality_dir(tmp_path)

    quality = run_data_quality_checks(df, settings, "baseline_quality")
    freshness = build_freshness_report(df, settings, tmp_path / "baseline_freshness.json")

    assert quality["passed"] is True
    assert quality["failed_checks"] == 0
    assert freshness["is_fresh"] is True
    assert freshness["stale_rows"] == 0
    assert (tmp_path / "quality" / "baseline_quality.json").exists()


def test_corruption_is_detected(tmp_path: Path) -> None:
    df = _clean_df().iloc[:-2].copy()
    df.loc[df.index[0], "summary"] = ""
    df.loc[df.index[1], "title"] = "bad"
    df.loc[df.index[2], "published"] = "2000-01-01"
    df.loc[df.index[2], "age_days"] = 9999
    df.loc[df.index[3], "summary"] = "[CORRUPTED NOISE] " + df.loc[df.index[3], "summary"]
    df = pd.concat([df, df.iloc[[4]]], ignore_index=True)
    settings = _settings_with_quality_dir(tmp_path)

    quality = run_data_quality_checks(df, settings, "corrupted_quality")
    freshness = build_freshness_report(df, settings, tmp_path / "corrupted_freshness.json")
    failed = {check["name"] for check in quality["checks"] if not check["passed"]}

    assert quality["passed"] is False
    assert {
        "row_count",
        "paper_id_unique",
        "title_length",
        "summary_complete",
        "freshness_threshold",
        "corruption_markers_absent",
    }.issubset(failed)
    assert freshness["is_fresh"] is False
    assert freshness["stale_rows"] >= 1


def test_markdown_reports_render_artifact_values(tmp_path: Path) -> None:
    metrics = {
        "samples": 24,
        "retrieval_hit_rate": 0.75,
        "mean_token_f1": 0.5,
        "judge_accuracy": 0.625,
        "mean_judge_score": 3.25,
        "ragas": {"skipped": "disabled for test"},
    }
    quality = {"passed": True, "total_rows": 24, "passed_checks": 2, "failed_checks": 0, "checks": []}
    freshness = {
        "latest_published": "2026-08-01",
        "oldest_published": "2026-02-01",
        "stale_rows": 0,
        "total_rows": 24,
        "is_fresh": True,
        "freshness_threshold_days": 180,
    }
    phase_path = tmp_path / "phase1.md"
    comparison_path = tmp_path / "comparison.md"

    generate_phase1_report(phase_path, {"source": "Crossref", "records": 24}, metrics, quality, freshness)
    generate_corruption_report(
        comparison_path,
        metrics,
        {**metrics, "retrieval_hit_rate": 0.25},
        {**metrics, "retrieval_hit_rate": 0.70},
        {**quality, "passed": False, "failed_checks": 2},
        quality,
        {**freshness, "is_fresh": False, "stale_rows": 3},
        freshness,
    )

    phase_text = phase_path.read_text(encoding="utf-8")
    comparison_text = comparison_path.read_text(encoding="utf-8")
    assert "Crossref" in phase_text
    assert "0.7500" in phase_text
    assert "Corruption impact" in comparison_text
    assert "-0.5000" in comparison_text
    assert "Data-quality recovery observed: **yes**" in comparison_text
