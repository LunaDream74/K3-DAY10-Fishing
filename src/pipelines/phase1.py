from __future__ import annotations

from datetime import UTC, datetime

from core.config import load_settings
from core.utils import read_json
from evaluation.metrics import evaluate_pipeline
from evaluation.testset import build_test_set
from ingestion.cleaning import build_clean_dataframe, save_clean_dataframe
from ingestion.crossref import fetch_source_records, load_raw_records
from observability.quality import build_freshness_report, run_data_quality_checks
from observability.reporting import generate_phase1_report
from retrieval.index import LocalEmbeddingIndex


def run_phase1_pipeline() -> None:
    """Xây dựng và thực thi Baseline Data Pipeline end-to-end cho Pha 1.

    Các bước thực hiện:
    1. Load cấu hình hệ thống (Settings).
    2. Load hoặc fetch raw records từ Crossref API.
    3. Làm sạch dữ liệu (Clean data) & tạo data frame chuẩn.
    4. Lưu cleaned dataset dưới dạng CSV và JSON.
    5. Khởi tạo & nạp vector store ChromaDB (Baseline Collection).
    6. Tạo bộ câu hỏi kiểm thử cố định (Test Set) nếu chưa có.
    7. Chạy đánh giá RAG Agent trên Test Set (Baseline Metrics).
    8. Chạy Data Quality Checks và Freshness Monitoring.
    9. Xuất báo cáo Markdown tổng hợp cho Phase 1 (phase1_report.md).
    """
    print("=== [PHASE 1] Starting Baseline Data Pipeline ===")
    settings = load_settings()

    # Step 2: Load or Fetch Raw Records
    if settings.paths.raw_records_json.exists() and not settings.refresh_source:
        print(f"Loading raw records from existing file: {settings.paths.raw_records_json}")
        records = load_raw_records(settings.paths.raw_records_json)
    else:
        print("Fetching fresh records from Crossref API...")
        records = fetch_source_records(settings)
    print(f"Fetched/Loaded {len(records)} raw paper records.")

    # Step 3 & 4: Clean Data & Persist Artifacts
    print("Cleaning raw records and building clean DataFrame...")
    run_time = datetime.now(UTC)
    clean_df = build_clean_dataframe(records, run_date=run_time)
    save_clean_dataframe(clean_df, settings.paths.clean_csv, settings.paths.clean_json)
    print(f"Saved {len(clean_df)} cleaned records to {settings.paths.clean_csv}")

    # Step 5: Build Chroma Index for Baseline
    print(f"Building ChromaDB collection '{settings.baseline_collection_name}'...")
    index = LocalEmbeddingIndex.build(
        df=clean_df,
        settings=settings,
        embeddings_output_path=settings.paths.embeddings_json,
    )
    print(f"Baseline vector index successfully created with {len(clean_df)} documents.")

    # Step 6: Build or Load Evaluation Test Set
    if settings.paths.eval_testset.exists() and not settings.refresh_test_set:
        print(f"Loading existing test set from {settings.paths.eval_testset}")
        test_set = read_json(settings.paths.eval_testset)
    else:
        print("Generating new evaluation test set...")
        test_set = build_test_set(clean_df, settings.paths.eval_testset)
    print(f"Evaluation test set ready with {len(test_set)} question samples.")

    # Step 7: Evaluate Pipeline
    print("Evaluating RAG Agent against evaluation test set...")
    eval_bundle = evaluate_pipeline(
        settings=settings,
        index=index,
        test_set_path=settings.paths.eval_testset,
        metrics_output_path=settings.paths.baseline_metrics,
        answers_output_path=settings.paths.baseline_answers,
    )
    print("Baseline evaluation completed:")
    print(f"  - Retrieval Hit Rate : {eval_bundle.summary.get('retrieval_hit_rate'):.4f}")
    print(f"  - Mean Token F1     : {eval_bundle.summary.get('mean_token_f1'):.4f}")
    print(f"  - Mean Judge Score   : {eval_bundle.summary.get('mean_judge_score'):.4f}")

    # Step 8: Observability - Data Quality Checks & Freshness Monitoring
    print("Running Data Quality Checks and Freshness Monitoring...")
    quality_result = run_data_quality_checks(clean_df, settings, report_name="baseline_quality")
    freshness_result = build_freshness_report(clean_df, settings, report_path=settings.paths.freshness_report)

    # Step 9: Generate Markdown Phase 1 Report
    print("Generating Phase 1 Markdown Report...")
    source_summary = {
        "source_api": settings.source_api,
        "query": settings.source_query,
        "records_fetched": len(records),
        "clean_rows": len(clean_df),
        "collection_name": settings.baseline_collection_name,
    }
    generate_phase1_report(
        report_path=settings.paths.baseline_report,
        source_summary=source_summary,
        metrics=eval_bundle.summary,
        quality=quality_result,
        freshness=freshness_result,
    )
    print(f"=== [PHASE 1] Baseline Pipeline Successfully Completed ===")
    print(f"Report written to: {settings.paths.baseline_report}")


def main() -> None:
    run_phase1_pipeline()


if __name__ == "__main__":
    main()
