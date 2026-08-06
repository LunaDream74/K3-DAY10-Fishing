from __future__ import annotations

from datetime import UTC, datetime
from html import unescape
from pathlib import Path
import re

import pandas as pd

from core.utils import write_csv, write_json
from ingestion.crossref import PaperRecord


def build_clean_dataframe(records: list[PaperRecord], run_date: datetime) -> pd.DataFrame:
    """TODO(student): clean raw records thanh dataframe san sang de embed.

    Pseudo-code:
    1. Normalize title, summary, authors, categories.
    2. Parse published/updated date.
    3. Tinh age_days.
    4. Tao cot helper:
       - authors_joined
       - categories_joined
       - summary_chars
       - text_for_embedding
    5. Drop duplicates va filter row xau.
    6. Sort dataframe va return.
    """
    columns = [
        "paper_id", "title", "summary", "authors", "categories", "primary_category",
        "published", "updated", "age_days", "abs_url", "pdf_url", "comment",
        "authors_joined", "categories_joined", "summary_chars", "text_for_embedding",
    ]
    normalized_run_date = pd.Timestamp(run_date)
    if normalized_run_date.tzinfo is None:
        normalized_run_date = normalized_run_date.tz_localize(UTC)
    else:
        normalized_run_date = normalized_run_date.tz_convert(UTC)

    rows: list[dict] = []
    for record in records:
        paper_id = _clean_text(record.paper_id).lower()
        title = _clean_text(record.title, strip_markup=True)
        summary = _clean_text(record.summary, strip_markup=True)
        authors = _clean_list(record.authors)
        categories = _clean_list(record.categories)
        primary_category = _clean_text(record.primary_category)
        if not primary_category and categories:
            primary_category = categories[0]

        published_ts = pd.to_datetime(record.published, errors="coerce", utc=True)
        updated_ts = pd.to_datetime(record.updated, errors="coerce", utc=True)
        # Short abstracts carry too little semantic information for useful retrieval.
        if not paper_id or not title or len(summary) < 100 or pd.isna(published_ts):
            continue

        published = published_ts.date().isoformat()
        updated = "" if pd.isna(updated_ts) else updated_ts.date().isoformat()
        age_days = max(0, int((normalized_run_date.normalize() - published_ts.normalize()).days))
        authors_joined = ", ".join(authors)
        categories_joined = ", ".join(categories)
        text_for_embedding = f"Title: {title} | Authors: {authors_joined} | Summary: {summary}"

        rows.append(
            {
                "paper_id": paper_id,
                "title": title,
                "summary": summary,
                "authors": authors,
                "categories": categories,
                "primary_category": primary_category,
                "published": published,
                "updated": updated,
                "age_days": age_days,
                "abs_url": _clean_text(record.abs_url),
                "pdf_url": _clean_text(record.pdf_url),
                "comment": _clean_text(record.comment),
                "authors_joined": authors_joined,
                "categories_joined": categories_joined,
                "summary_chars": len(summary),
                "text_for_embedding": text_for_embedding,
            }
        )

    if not rows:
        return pd.DataFrame(columns=columns)

    df = pd.DataFrame(rows, columns=columns)
    # Prefer the most recently updated copy when Crossref returns the same DOI more than once.
    df["_updated_sort"] = pd.to_datetime(df["updated"], errors="coerce", utc=True)
    df = df.sort_values(["_updated_sort", "published", "paper_id"], ascending=[False, False, True])
    df = df.drop_duplicates(subset=["paper_id"], keep="first").drop(columns="_updated_sort")
    return df.sort_values(["published", "paper_id"], ascending=[False, True]).reset_index(drop=True)


def save_clean_dataframe(df: pd.DataFrame, csv_path: Path, json_path: Path) -> None:
    """Persist the same cleaned dataset as CSV and record-oriented JSON artifacts."""
    write_csv(df, csv_path)
    write_json(json_path, df.to_dict(orient="records"))


def _clean_text(value: object, *, strip_markup: bool = False) -> str:
    text = "" if value is None else unescape(str(value))
    if strip_markup:
        text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _clean_list(values: object) -> list[str]:
    if values is None:
        return []
    source = values if isinstance(values, (list, tuple, set)) else [values]
    result: list[str] = []
    seen: set[str] = set()
    for value in source:
        text = _clean_text(value)
        key = text.casefold()
        if text and key not in seen:
            seen.add(key)
            result.append(text)
    return result
