# Corruption and Repair Comparison Report

> Baseline, corrupted and repaired metrics must be produced with the same evaluation set.

## Evaluation comparison

| Metric | Baseline | Corrupted | Repaired | Corruption impact | Repair recovery |
| --- | ---: | ---: | ---: | ---: | ---: |
| `retrieval_hit_rate` | 1.0000 | 0.8750 | 1.0000 | -0.1250 | +0.1250 |
| `mean_token_f1` | 0.6667 | 0.5475 | 0.6667 | -0.1192 | +0.1192 |
| `judge_accuracy` | 0.6667 | 0.5417 | 0.6667 | -0.1250 | +0.1250 |
| `mean_judge_score` | 3.6667 | 3.1667 | 3.6667 | -0.5000 | +0.5000 |

`Corruption impact = corrupted - baseline`; `repair recovery = repaired - corrupted`.

## Data-quality comparison

Baseline quality is documented in `phase1_report.md`; this function receives corrupted and repaired quality artifacts.

| State | Overall status | Passed checks | Failed checks | Rows |
| --- | --- | ---: | ---: | ---: |
| Corrupted | FAIL | 9 | 7 | 24 |
| Repaired | PASS | 16 | 0 | 24 |

### Failed checks after corruption

- `paper_id_unique`: 4 failed row(s).
- `title_length`: 1 failed row(s).
- `summary_complete`: 2 failed row(s).
- `summary_length`: 2 failed row(s).
- `published_age_consistent`: 2 failed row(s).
- `freshness_threshold`: 2 failed row(s).
- `corruption_markers_absent`: 2 failed row(s).

## Freshness comparison

| State | Status | Stale rows | Total rows | Latest | Oldest |
| --- | --- | ---: | ---: | --- | --- |
| Corrupted | FAIL | 2 | 24 | 2026-07-13 | 2020-01-01 |
| Repaired | PASS | 0 | 24 | 2026-08-01 | 2026-02-12 |

## Evidence-based observations

- Retrieval hit rate changed by **-0.1250** after corruption.
- Retrieval hit rate changed by **+0.1250** after repair.
- Data-quality recovery observed: **yes**.
- Freshness recovery observed: **yes**.

A causal conclusion should only be made when the corruption log, quality/freshness signals and evaluation metrics show corresponding changes.
