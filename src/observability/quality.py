from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
import re
from typing import Any

import pandas as pd

from core.config import Settings
from core.utils import write_json


MIN_SUMMARY_CHARS = 100
MIN_TITLE_CHARS = 10
REQUIRED_COLUMNS = {
    "paper_id",
    "title",
    "summary",
    "published",
    "age_days",
    "text_for_embedding",
}
CORRUPTION_MARKER = re.compile(
    r"\[(?:corrupt(?:ed|ion)?|noise)[^\]]*\]|corrupted[_ -]?noise|noise[_ -]?token|lorem\s+ipsum|#{3,}|@{3,}",
    re.IGNORECASE,
)


def _text_series(df: pd.DataFrame, column: str) -> pd.Series:
    if column not in df:
        return pd.Series("", index=df.index, dtype="string")
    return df[column].astype("string").fillna("").str.strip()


def _check(
    name: str,
    dimension: str,
    passed: bool,
    failed_rows: int,
    observed: Any,
    expected: str,
) -> dict[str, Any]:
    return {
        "name": name,
        "dimension": dimension,
        "passed": bool(passed),
        "failed_rows": int(failed_rows),
        "observed": observed,
        "expected": expected,
    }


def _quality_report_path(settings: Settings, report_name: str) -> Path:
    clean_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", Path(str(report_name)).stem).strip("._")
    if not clean_name:
        raise ValueError("report_name must contain at least one safe filename character.")
    return settings.paths.quality_dir / f"{clean_name}.json"


def run_data_quality_checks(df: pd.DataFrame, settings: Settings, report_name: str) -> dict[str, Any]:
    """Run deterministic completeness, validity, uniqueness and freshness checks."""
    checks: list[dict[str, Any]] = []
    total_rows = len(df)
    missing_columns = sorted(REQUIRED_COLUMNS.difference(df.columns))
    checks.append(
        _check(
            "required_columns",
            "schema",
            not missing_columns,
            len(missing_columns),
            missing_columns,
            f"columns present: {', '.join(sorted(REQUIRED_COLUMNS))}",
        )
    )

    target_rows = settings.max_results
    checks.append(
        _check(
            "row_count",
            "completeness",
            total_rows >= target_rows,
            max(0, target_rows - total_rows),
            total_rows,
            f">= {target_rows} rows",
        )
    )

    paper_ids = _text_series(df, "paper_id")
    empty_paper_ids = paper_ids.eq("")
    duplicate_paper_ids = paper_ids.ne("") & paper_ids.duplicated(keep=False)
    checks.extend(
        [
            _check(
                "paper_id_complete",
                "completeness",
                not empty_paper_ids.any(),
                int(empty_paper_ids.sum()),
                int(empty_paper_ids.sum()),
                "0 empty paper_id values",
            ),
            _check(
                "paper_id_unique",
                "uniqueness",
                not duplicate_paper_ids.any(),
                int(duplicate_paper_ids.sum()),
                int(duplicate_paper_ids.sum()),
                "0 rows with duplicate paper_id values",
            ),
        ]
    )

    titles = _text_series(df, "title")
    empty_titles = titles.eq("")
    short_titles = titles.ne("") & titles.str.len().lt(MIN_TITLE_CHARS)
    checks.extend(
        [
            _check(
                "title_complete",
                "completeness",
                not empty_titles.any(),
                int(empty_titles.sum()),
                int(empty_titles.sum()),
                "0 empty titles",
            ),
            _check(
                "title_length",
                "validity",
                not short_titles.any(),
                int(short_titles.sum()),
                int(short_titles.sum()),
                f"all non-empty titles have >= {MIN_TITLE_CHARS} characters",
            ),
        ]
    )

    summaries = _text_series(df, "summary")
    empty_summaries = summaries.eq("")
    short_summaries = summaries.str.len().lt(MIN_SUMMARY_CHARS)
    checks.extend(
        [
            _check(
                "summary_complete",
                "completeness",
                not empty_summaries.any(),
                int(empty_summaries.sum()),
                int(empty_summaries.sum()),
                "0 empty summaries",
            ),
            _check(
                "summary_length",
                "validity",
                not short_summaries.any(),
                int(short_summaries.sum()),
                int(short_summaries.sum()),
                f"all summaries have >= {MIN_SUMMARY_CHARS} characters",
            ),
        ]
    )

    if "summary_chars" in df:
        declared_summary_chars = pd.to_numeric(df["summary_chars"], errors="coerce")
        summary_length_mismatch = declared_summary_chars.isna() | declared_summary_chars.ne(summaries.str.len())
        checks.append(
            _check(
                "summary_chars_consistent",
                "consistency",
                not summary_length_mismatch.any(),
                int(summary_length_mismatch.sum()),
                int(summary_length_mismatch.sum()),
                "summary_chars equals the normalized summary length",
            )
        )

    embedding_text = _text_series(df, "text_for_embedding")
    empty_embedding_text = embedding_text.eq("")
    embedding_mismatch = pd.Series(False, index=df.index)
    if "text_for_embedding" in df and "title" in df and "summary" in df:
        embedding_mismatch = pd.Series(
            [
                bool(title and summary and (title not in content or summary not in content))
                for title, summary, content in zip(titles, summaries, embedding_text, strict=False)
            ],
            index=df.index,
        )
    checks.extend(
        [
            _check(
                "text_for_embedding_complete",
                "completeness",
                not empty_embedding_text.any(),
                int(empty_embedding_text.sum()),
                int(empty_embedding_text.sum()),
                "0 empty text_for_embedding values",
            ),
            _check(
                "text_for_embedding_consistent",
                "consistency",
                not embedding_mismatch.any(),
                int(embedding_mismatch.sum()),
                int(embedding_mismatch.sum()),
                "each embedding text contains its title and summary",
            ),
        ]
    )

    published = pd.to_datetime(_text_series(df, "published"), errors="coerce", utc=True, format="mixed")
    invalid_published = published.isna()
    ages = pd.to_numeric(df["age_days"], errors="coerce") if "age_days" in df else pd.Series(float("nan"), index=df.index)
    invalid_ages = ages.isna() | ages.lt(0)
    stale_rows = ages.gt(settings.freshness_threshold_days)
    today = pd.Timestamp(datetime.now(UTC).date(), tz=UTC)
    calculated_ages = (today - published.dt.normalize()).dt.days
    inconsistent_ages = ~(invalid_published | invalid_ages) & calculated_ages.sub(ages).abs().gt(1)
    checks.extend(
        [
            _check(
                "published_valid",
                "validity",
                not invalid_published.any(),
                int(invalid_published.sum()),
                int(invalid_published.sum()),
                "all published values are parseable dates",
            ),
            _check(
                "age_days_valid",
                "validity",
                not invalid_ages.any(),
                int(invalid_ages.sum()),
                int(invalid_ages.sum()),
                "all age_days values are numeric and >= 0",
            ),
            _check(
                "published_age_consistent",
                "consistency",
                not inconsistent_ages.any(),
                int(inconsistent_ages.sum()),
                int(inconsistent_ages.sum()),
                "age_days agrees with published date within 1 day",
            ),
            _check(
                "freshness_threshold",
                "freshness",
                not stale_rows.any(),
                int(stale_rows.sum()),
                int(stale_rows.sum()),
                f"0 rows older than {settings.freshness_threshold_days} days",
            ),
        ]
    )

    corruption_markers = (titles + " " + summaries).str.contains(CORRUPTION_MARKER, na=False)
    checks.append(
        _check(
            "corruption_markers_absent",
            "validity",
            not corruption_markers.any(),
            int(corruption_markers.sum()),
            int(corruption_markers.sum()),
            "0 rows containing known corruption/noise markers",
        )
    )

    payload: dict[str, Any] = {
        "report_name": Path(str(report_name)).stem,
        "generated_at": datetime.now(UTC).isoformat(),
        "total_rows": total_rows,
        "passed": all(check["passed"] for check in checks),
        "passed_checks": sum(1 for check in checks if check["passed"]),
        "failed_checks": sum(1 for check in checks if not check["passed"]),
        "checks": checks,
    }
    write_json(_quality_report_path(settings, report_name), payload)
    return payload


def build_freshness_report(df: pd.DataFrame, settings: Settings, report_path) -> dict[str, Any]:
    """Summarize publication-date freshness and persist it as JSON."""
    published = pd.to_datetime(_text_series(df, "published"), errors="coerce", utc=True, format="mixed")
    ages = pd.to_numeric(df["age_days"], errors="coerce") if "age_days" in df else pd.Series(float("nan"), index=df.index)
    invalid_published_rows = int(published.isna().sum())
    invalid_age_rows = int((ages.isna() | ages.lt(0)).sum())
    stale_rows = int(ages.gt(settings.freshness_threshold_days).sum())
    valid_published = published.dropna()

    payload: dict[str, Any] = {
        "latest_published": valid_published.max().date().isoformat() if not valid_published.empty else None,
        "oldest_published": valid_published.min().date().isoformat() if not valid_published.empty else None,
        "stale_rows": stale_rows,
        "total_rows": len(df),
        "is_fresh": bool(len(df) > 0 and stale_rows == 0 and invalid_published_rows == 0 and invalid_age_rows == 0),
        "freshness_threshold_days": settings.freshness_threshold_days,
        "invalid_published_rows": invalid_published_rows,
        "invalid_age_rows": invalid_age_rows,
        "generated_at": datetime.now(UTC).isoformat(),
    }
    write_json(Path(report_path), payload)
    return payload
