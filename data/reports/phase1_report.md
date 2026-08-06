# Phase 1 Baseline Report

> This report is generated from pipeline artifacts; values are not manually entered.

## Source summary

| Field | Value |
| --- | --- |
| source_api | Crossref REST API |
| query | agentic retrieval augmented generation large language model |
| records_fetched | 24 |
| clean_rows | 24 |
| collection_name | papers-baseline |

## Evaluation metrics

| Metric | Value |
| --- | ---: |
| `retrieval_hit_rate` | 1.0000 |
| `mean_token_f1` | 0.6667 |
| `judge_accuracy` | 0.6667 |
| `mean_judge_score` | 3.6667 |
| `ragas` | Skipped — Set RUN_RAGAS=1 to enable the slower Ragas pass. |

## Data quality

Overall status: **PASS**  
Rows checked: **24**  
Checks passed/failed: **16/0**

| Check | Dimension | Status | Failed rows | Expectation |
| --- | --- | --- | ---: | --- |
| required_columns | schema | PASS | 0 | columns present: age_days, paper_id, published, summary, text_for_embedding, title |
| row_count | completeness | PASS | 0 | >= 24 rows |
| paper_id_complete | completeness | PASS | 0 | 0 empty paper_id values |
| paper_id_unique | uniqueness | PASS | 0 | 0 rows with duplicate paper_id values |
| title_complete | completeness | PASS | 0 | 0 empty titles |
| title_length | validity | PASS | 0 | all non-empty titles have >= 10 characters |
| summary_complete | completeness | PASS | 0 | 0 empty summaries |
| summary_length | validity | PASS | 0 | all summaries have >= 100 characters |
| summary_chars_consistent | consistency | PASS | 0 | summary_chars equals the normalized summary length |
| text_for_embedding_complete | completeness | PASS | 0 | 0 empty text_for_embedding values |
| text_for_embedding_consistent | consistency | PASS | 0 | each embedding text contains its title and summary |
| published_valid | validity | PASS | 0 | all published values are parseable dates |
| age_days_valid | validity | PASS | 0 | all age_days values are numeric and >= 0 |
| published_age_consistent | consistency | PASS | 0 | age_days agrees with published date within 1 day |
| freshness_threshold | freshness | PASS | 0 | 0 rows older than 180 days |
| corruption_markers_absent | validity | PASS | 0 | 0 rows containing known corruption/noise markers |

## Freshness

| Signal | Value |
| --- | --- |
| Latest publication | 2026-08-01 |
| Oldest publication | 2026-02-12 |
| Stale rows | 0 |
| Total rows | 24 |
| Threshold (days) | 180 |
| Freshness status | PASS |

## Interpretation

- Data quality status: **PASS**.
- Freshness status: **FRESH**.
- Retrieval hit rate: **1.0000** across **24** evaluation samples.
