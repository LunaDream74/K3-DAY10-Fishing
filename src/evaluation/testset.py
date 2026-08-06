from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from core.utils import first_sentence, normalize_whitespace, write_json


MIN_DOCUMENTS = 4
MAX_SELECTED_DOCUMENTS = 8
REQUIRED_COLUMNS = {
    "paper_id",
    "title",
    "summary",
    "authors_joined",
    "categories_joined",
    "published",
}


def _text(value: Any) -> str:
    """Return a normalized string while treating pandas missing values as empty."""
    if value is None or (not isinstance(value, (list, dict)) and pd.isna(value)):
        return ""
    return normalize_whitespace(str(value))


def _representative_rows(df: pd.DataFrame) -> pd.DataFrame:
    """Select rows deterministically and spread them across the whole corpus."""
    ordered = df.sort_values("paper_id", kind="stable").reset_index(drop=True)
    sample_size = min(MAX_SELECTED_DOCUMENTS, len(ordered))
    if sample_size == len(ordered):
        return ordered

    # Integer arithmetic avoids duplicate positions and stays stable across runs.
    positions = [(index * (len(ordered) - 1)) // (sample_size - 1) for index in range(sample_size)]
    return ordered.iloc[positions].reset_index(drop=True)


def build_test_set(df: pd.DataFrame, output_path) -> list[dict[str, Any]]:
    """Build a deterministic, corpus-grounded evaluation set.

    Empty optional facts are skipped instead of producing questions with an
    unusable ground truth.  This matters for Crossref records, which frequently
    have no subjects/categories.
    """
    missing_columns = sorted(REQUIRED_COLUMNS.difference(df.columns))
    if missing_columns:
        raise ValueError(f"Clean dataframe is missing required columns: {', '.join(missing_columns)}")
    if len(df) < MIN_DOCUMENTS:
        raise ValueError(f"At least {MIN_DOCUMENTS} clean documents are required to build a test set.")

    samples: list[dict[str, Any]] = []
    for row in _representative_rows(df).to_dict(orient="records"):
        paper_id = _text(row["paper_id"])
        title = _text(row["title"])
        summary = _text(row["summary"])
        authors = _text(row["authors_joined"])
        categories = _text(row["categories_joined"])
        published = _text(row["published"])

        if not paper_id or not title:
            continue

        facts = [
            (
                "summary",
                f"What is the paper '{title}' about?",
                first_sentence(summary),
            ),
            (
                "authors",
                f"Who are the authors of the paper '{title}'?",
                authors,
            ),
            (
                "date",
                f"When was the paper '{title}' published?",
                published,
            ),
            (
                "categories",
                f"What categories are associated with the paper '{title}'?",
                categories,
            ),
        ]
        for question_type, question, ground_truth in facts:
            ground_truth = _text(ground_truth)
            if not ground_truth:
                continue
            samples.append(
                {
                    "id": f"{paper_id}::{question_type}",
                    "question_type": question_type,
                    "question": question,
                    "ground_truth": ground_truth,
                    "ground_truth_doc_ids": [paper_id],
                }
            )

    if not samples:
        raise ValueError("No valid evaluation questions could be generated from the clean dataframe.")
    if len({sample["id"] for sample in samples}) != len(samples):
        raise ValueError("Evaluation question IDs are not unique; check paper_id uniqueness.")

    write_json(Path(output_path), samples)
    return samples
