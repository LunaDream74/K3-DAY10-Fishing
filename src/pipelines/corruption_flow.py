from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd

from core.config import load_settings
from core.utils import read_json
from evaluation.metrics import evaluate_pipeline
from ingestion.cleaning import build_clean_dataframe, save_clean_dataframe
from ingestion.corruption import corrupt_clean_dataframe
from ingestion.crossref import load_raw_records
from observability.quality import build_freshness_report, run_data_quality_checks
from observability.reporting import generate_corruption_report
from pipelines.phase1 import run_phase1_pipeline
from retrieval.index import LocalEmbeddingIndex


def run_corruption_flow_pipeline() -> None:
    """Thực thi toàn bộ luồng Pha 2: Corrupt ➔ Evaluate ➔ Repair từ Raw ➔ Re-evaluate ➔ Compare.

    Các bước thực hiện:
    1. Kiểm tra & đảm bảo Baseline artifacts đã tồn tại (nếu chưa có thì chạy Phase 1).
    2. Đọc dữ liệu cleaned baseline (`papers_clean.csv`) và baseline metrics.
    3. Bơm các dạng lỗi dữ liệu có chủ đích (`corrupt_clean_dataframe`).
    4. Lưu corrupted dataset và tạo ChromaDB collection 'papers-corrupted'.
    5. Đánh giá lại RAG Agent trên bộ đề thi cũ với dữ liệu lỗi.
    6. Chạy Data Quality & Freshness checks trên corrupted dataset (Kỳ vọng: FAIL).
    7. Phục hồi (REPAIR) dữ liệu bằng cách nạp lại từ snapshot `data/raw/crossref_records.json`
       và chạy lại quy trình `build_clean_dataframe`.
    8. Tạo ChromaDB collection 'papers-repaired' với dữ liệu đã phục hồi.
    9. Đánh giá lại RAG Agent trên dữ liệu phục hồi (Kỳ vọng: Khôi phục mức Baseline).
    10. Xuất báo cáo so sánh Markdown tổng hợp đối chiếu 3 trạng thái (`corruption_report.md`).
    """
    print("=== [PHASE 2] Starting Data Corruption, Repair & Comparison Flow ===")
    settings = load_settings()

    # Step 1: Ensure Baseline Artifacts Exist
    if not settings.paths.clean_csv.exists() or not settings.paths.baseline_metrics.exists():
        print("Baseline artifacts not found. Running Phase 1 Baseline first...")
        run_phase1_pipeline()

    # Step 2: Read Baseline Data
    print("Loading Baseline Metrics and Cleaned Dataset...")
    baseline_metrics = read_json(settings.paths.baseline_metrics)
    baseline_df = pd.read_csv(settings.paths.clean_csv)

    # Step 3 & 4: Simulate Data Corruption & Build Corrupted Index
    print("Simulating controlled data corruption...")
    corrupted_df = corrupt_clean_dataframe(baseline_df, output_log_path=settings.paths.corruption_log)
    save_clean_dataframe(corrupted_df, settings.paths.corrupted_clean_csv, settings.paths.corrupted_clean_json)
    print(f"Saved corrupted dataset ({len(corrupted_df)} rows) to {settings.paths.corrupted_clean_csv}")

    print(f"Building ChromaDB collection '{settings.corrupted_collection_name}'...")
    corrupted_index = LocalEmbeddingIndex.build(
        df=corrupted_df,
        settings=settings,
        embeddings_output_path=settings.paths.corrupted_embeddings_json,
    )

    # Step 5: Evaluate Corrupted Pipeline
    print("Evaluating RAG Agent against Corrupted Dataset...")
    corrupted_bundle = evaluate_pipeline(
        settings=settings,
        index=corrupted_index,
        test_set_path=settings.paths.eval_testset,
        metrics_output_path=settings.paths.corrupted_metrics,
        answers_output_path=settings.paths.corrupted_answers,
    )
    print("Corrupted evaluation completed:")
    print(f"  - Corrupted Hit Rate   : {corrupted_bundle.summary.get('retrieval_hit_rate'):.4f}")
    print(f"  - Corrupted Token F1   : {corrupted_bundle.summary.get('mean_token_f1'):.4f}")
    print(f"  - Corrupted Judge Score: {corrupted_bundle.summary.get('mean_judge_score'):.4f}")

    # Step 6: Run Quality & Freshness on Corrupted Data
    print("Running Data Quality Checks on Corrupted Dataset...")
    corrupted_quality = run_data_quality_checks(corrupted_df, settings, report_name="corrupted_quality")
    corrupted_freshness = build_freshness_report(
        corrupted_df, settings, report_path=settings.paths.quality_dir / "corrupted_freshness.json"
    )

    # Step 7: REPAIR Data from Raw Records
    print("Repairing dataset by re-running clean pipeline from raw snapshot...")
    raw_records = load_raw_records(settings.paths.raw_records_json)
    repaired_df = build_clean_dataframe(raw_records, run_date=datetime.now(UTC))
    save_clean_dataframe(repaired_df, settings.paths.repaired_clean_csv, settings.paths.repaired_clean_json)
    print(f"Saved repaired dataset ({len(repaired_df)} rows) to {settings.paths.repaired_clean_csv}")

    # Step 8: Build Chroma Index for Repaired Data
    print(f"Building ChromaDB collection '{settings.repaired_collection_name}'...")
    repaired_index = LocalEmbeddingIndex.build(
        df=repaired_df,
        settings=settings,
        embeddings_output_path=settings.paths.repaired_embeddings_json,
    )

    # Step 9: Evaluate Repaired Pipeline
    print("Evaluating RAG Agent against Repaired Dataset...")
    repaired_bundle = evaluate_pipeline(
        settings=settings,
        index=repaired_index,
        test_set_path=settings.paths.eval_testset,
        metrics_output_path=settings.paths.repaired_metrics,
        answers_output_path=settings.paths.repaired_answers,
    )
    print("Repaired evaluation completed:")
    print(f"  - Repaired Hit Rate    : {repaired_bundle.summary.get('retrieval_hit_rate'):.4f}")
    print(f"  - Repaired Token F1    : {repaired_bundle.summary.get('mean_token_f1'):.4f}")
    print(f"  - Repaired Judge Score : {repaired_bundle.summary.get('mean_judge_score'):.4f}")

    # Step 10: Run Quality & Freshness on Repaired Data
    print("Running Data Quality Checks on Repaired Dataset...")
    repaired_quality = run_data_quality_checks(repaired_df, settings, report_name="repaired_quality")
    repaired_freshness = build_freshness_report(
        repaired_df, settings, report_path=settings.paths.quality_dir / "repaired_freshness.json"
    )

    # Step 11: Generate Comparison Report
    print("Generating Comparison Report (Baseline vs Corrupted vs Repaired)...")
    generate_corruption_report(
        report_path=settings.paths.comparison_report,
        baseline_metrics=baseline_metrics,
        corrupted_metrics=corrupted_bundle.summary,
        repaired_metrics=repaired_bundle.summary,
        corrupted_quality=corrupted_quality,
        repaired_quality=repaired_quality,
        corrupted_freshness=corrupted_freshness,
        repaired_freshness=repaired_freshness,
    )
    print("=== [PHASE 2] Data Corruption, Repair & Comparison Flow Successfully Completed ===")
    print(f"Comparison report written to: {settings.paths.comparison_report}")


def main() -> None:
    run_corruption_flow_pipeline()


if __name__ == "__main__":
    main()
