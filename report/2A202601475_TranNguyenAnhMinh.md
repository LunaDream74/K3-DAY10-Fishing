# Báo cáo cá nhân — Day 10: Data Pipeline & Data Observability

## 1. Thông tin cá nhân

| Thông tin | Nội dung |
| --- | --- |
| Họ và tên | Trần Nguyễn Anh Minh |
| MSSV | 2A202601475 |
| Khóa/Lớp | K3 |
| Tên nhóm | K3-DAY10-Fishing |
| Vai trò chính | Evaluation & Observability Owner (thành viên 2) |
| Repository | https://github.com/LunaDream74/K3-DAY10-Fishing |
| Ngày hoàn thành phần việc | 2026-08-06 |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao | Trạng thái |
| --- | --- | --- | --- | --- |
| Evaluation set | `src/evaluation/testset.py` — `build_test_set()` | Cleaned DataFrame từ role 1 | `data/eval/test_set.json` | Hoàn thành |
| Data quality | `src/observability/quality.py` — `run_data_quality_checks()` | DataFrame và `Settings` | Quality payload và `data/quality/<report_name>.json` | Hoàn thành |
| Freshness monitoring | `src/observability/quality.py` — `build_freshness_report()` | DataFrame, ngưỡng 180 ngày và đường dẫn output | `data/quality/freshness_report.json` | Hoàn thành |
| Baseline reporting | `src/observability/reporting.py` — `generate_phase1_report()` | Source summary, metrics, quality và freshness payload | `data/reports/phase1_report.md` | Hoàn thành và đã được role 3 tích hợp |
| Corruption reporting | `src/observability/reporting.py` — `generate_corruption_report()` | Metrics/quality/freshness của ba trạng thái | `data/reports/corruption_report.md` | Hoàn thành và đã được role 3 tích hợp |
| Kiểm thử | `tests/test_role2.py` | Clean artifact và dữ liệu corruption giả lập | 4 kiểm thử tập trung | Hoàn thành |

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động | Thành viên/module được hỗ trợ | Kết quả |
| --- | --- | --- |
| Xác minh clean data contract | Role 1 — ingestion/cleaning | Xác nhận 24 dòng, 16 cột, `paper_id` unique, summary dài 826–2610 ký tự và `age_days` từ 5–175 |
| Chuẩn hóa interface tích hợp | Role 3 — `phase1.py`, `corruption_flow.py` | Giữ nguyên chữ ký các hàm và cung cấp JSON/Markdown contract ổn định |
| Chuẩn bị artifact baseline | Role 3 — integration | Bàn giao test set, baseline quality và freshness artifacts trong commit `267049a` |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao | Cách xác minh |
| --- | --- | --- | --- |
| Tạo test set deterministic | `build_test_set()`; `data/eval/test_set.json` | 24 mẫu: 8 summary, 8 authors, 8 date | Đọc JSON và đếm `question_type`; kiểm thử tính deterministic |
| Xây data-quality contract | `run_data_quality_checks()` | 16 checks thuộc schema, completeness, uniqueness, validity, consistency và freshness | `data/quality/baseline_quality.json` |
| Theo dõi freshness | `build_freshness_report()` | Latest `2026-08-01`, oldest `2026-02-12`, 0 stale row, trạng thái fresh | `data/quality/freshness_report.json` |
| Xây báo cáo baseline | `generate_phase1_report()` | Markdown gồm source, metrics, quality checks, freshness và interpretation | `test_markdown_reports_render_artifact_values` |
| Xây báo cáo so sánh | `generate_corruption_report()` | Bảng baseline/corrupted/repaired, corruption impact và repair recovery | `test_markdown_reports_render_artifact_values` |
| Kiểm thử corruption signals | `test_corruption_is_detected()` | Phát hiện row loss, duplicate, title ngắn, summary rỗng, stale date và corruption marker | `pytest`: 4 tests passed |

Output cụ thể nổi bật là `data/eval/test_set.json`. Artifact này chứa 24 câu hỏi có ID ổn định, ground truth không rỗng và `ground_truth_doc_ids` trỏ đúng vào `paper_id` trong clean dataset. Clean data hiện không có categories nên tôi không sinh category question với ground truth rỗng.

Phần việc được commit và push lên `origin/main` tại commit:

```text
267049a Implement role 2 evaluation and observability
```

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Pipeline cần một evaluation set cố định để so sánh công bằng ba trạng thái baseline, corrupted và repaired. Đồng thời, nhóm cần các tín hiệu observability đủ rõ để phát hiện dữ liệu thiếu, duplicate, text hỏng và dữ liệu cũ trước khi các lỗi này ảnh hưởng đến retrieval hoặc câu trả lời của agent. Cuối cùng, metrics và quality signals phải được trình bày thành báo cáo có thể truy ngược về artifact thật.

### Cách triển khai

`build_test_set()` kiểm tra clean schema, yêu cầu tối thiểu bốn document, sắp xếp theo `paper_id` và chọn tối đa tám paper trải đều trên corpus bằng chỉ số xác định. Cách này không phụ thuộc thứ tự input và không cần random seed. Với mỗi paper, hàm thử tạo bốn loại câu hỏi: summary, authors, date và categories. Câu hỏi chỉ được thêm nếu ground truth tương ứng không rỗng. Với dataset hiện tại, categories bị bỏ qua, nên kết quả là 24 câu hỏi thuộc ba loại.

`run_data_quality_checks()` tạo danh sách check có cùng schema:

```json
{
  "name": "paper_id_unique",
  "dimension": "uniqueness",
  "passed": true,
  "failed_rows": 0,
  "observed": 0,
  "expected": "0 rows with duplicate paper_id values"
}
```

Các check bao phủ required columns, row count, `paper_id`, title, summary, `summary_chars`, `text_for_embedding`, publication date, `age_days`, freshness threshold và corruption marker. Overall status chỉ pass khi tất cả checks pass.

`build_freshness_report()` parse `published`, đếm stale rows theo `settings.freshness_threshold_days`, ghi nhận ngày mới nhất/cũ nhất và đánh dấu `is_fresh`. Dữ liệu rỗng, ngày không parse được hoặc age không hợp lệ đều không được coi là fresh.

Hai hàm reporting chỉ render giá trị nhận từ artifact payload; chúng không tự tạo hoặc suy diễn metrics. Corruption report tính:

- `corruption impact = corrupted - baseline`;
- `repair recovery = repaired - corrupted`.

### Input, output và contract

| Thành phần | Mô tả |
| --- | --- |
| Input | Cleaned DataFrame có `paper_id`, `title`, `summary`, `authors_joined`, `categories_joined`, `published`, `age_days`, `summary_chars`, `text_for_embedding` |
| Evaluation output | Danh sách object gồm `id`, `question_type`, `question`, `ground_truth`, `ground_truth_doc_ids` |
| Quality output | Payload gồm `report_name`, `total_rows`, `passed`, số checks pass/fail và danh sách `checks` |
| Freshness output | `latest_published`, `oldest_published`, `stale_rows`, `total_rows`, `is_fresh`, threshold và invalid-row counts |
| Module phụ thuộc | `core.config`, `core.utils`, clean schema của `ingestion.cleaning` |
| Module sử dụng output | `evaluation.metrics`, `pipelines.phase1`, `pipelines.corruption_flow` |
| Điều kiện lỗi cần xử lý | Thiếu cột, corpus quá nhỏ, ground truth rỗng, duplicate ID, ngày không hợp lệ, DataFrame rỗng, metrics thiếu |

### Cách xác minh

Các lệnh thực tế đã chạy:

```powershell
python -m pytest -q --basetemp .venv\pytest_commit_check
python -m pip check
git diff --check
```

- **Kết quả mong đợi:** toàn bộ unit-style tests pass, dependency graph không hỏng và diff không có whitespace error.
- **Kết quả thực tế:** `4 passed`, `No broken requirements found`, `git diff --check` thành công.
- **Artifacts:** `data/eval/test_set.json`, `data/quality/baseline_quality.json`, `data/quality/freshness_report.json`.

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Evaluation set phải dùng lại nguyên vẹn ở cả baseline, corrupted và repaired. Nếu mỗi lần chạy chọn paper ngẫu nhiên thì thay đổi metrics có thể đến từ test set chứ không phải data corruption.
- **Các phương án đã cân nhắc:** (1) random sampling; (2) dùng toàn bộ 24 paper; (3) deterministic representative sampling trên danh sách đã sort.
- **Phương án đã chọn:** sort theo `paper_id`, chọn tối đa tám vị trí trải đều và tạo các loại câu hỏi có ground truth hợp lệ.
- **Lý do:** kết quả tái lập được, test set vừa đủ nhỏ để hạn chế số lượt LLM judge, nhưng vẫn phủ nhiều document và nhiều loại factual question.
- **Bằng chứng:** cùng DataFrame khi shuffle với `random_state=42` vẫn tạo test set giống hệt; kiểm thử `test_build_test_set_is_deterministic_and_grounded` pass. Artifact có 24 ID unique và mọi `ground_truth_doc_ids` đều tồn tại trong clean corpus.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng:** Test set ban đầu đặt title trong dấu nháy kép, trong khi `retrieval/qa.py` chỉ nhận exact title bằng biểu thức chính quy dùng dấu nháy đơn: `r"'([^']+)'"`.
- **Bước tái hiện:** so sánh câu hỏi sinh bởi `build_test_set()` với logic `_extract`/`lookup` trong `qa.py` trước khi commit.
- **Nguyên nhân gốc:** contract về cú pháp câu hỏi chưa đồng nhất giữa evaluation-set builder và QA lookup.
- **Cách xử lý:** đổi format thành `What is the paper '<title>' about?` và áp dụng tương tự cho authors/date/categories.
- **Cách xác minh sau khi sửa:** tái sinh `data/eval/test_set.json`, chạy lại toàn bộ tests; kết quả `4 passed`.
- **Điều học được:** data contract không chỉ gồm tên trường và kiểu dữ liệu; format text được downstream parser sử dụng cũng là một phần của contract tích hợp.

Một vấn đề môi trường khác là pytest ban đầu không có quyền truy cập temp directory mặc định của Windows. Tôi chuyển `--basetemp` vào `.venv`, xác nhận tests chạy bình thường và thêm pytest temp/cache paths vào `.gitignore`. Đây là lỗi môi trường, không phải lỗi logic của role 2.

## 7. Hiểu biết về luồng end-to-end

1. Crossref trả raw response; ingestion parse thành `PaperRecord` và lưu raw artifacts. Cleaning chuẩn hóa text/list/date, loại record không hợp lệ, tính `age_days`, tạo `text_for_embedding` rồi lưu clean CSV/JSON. Sentence Transformer mã hóa `text_for_embedding`; ChromaDB lưu vector cùng metadata để semantic search và exact lookup.
2. Evaluation set chứa câu hỏi, đáp án chuẩn và `ground_truth_doc_ids`. Retrieval hit khi một document ID chuẩn xuất hiện trong danh sách document truy hồi. Câu trả lời được so với `ground_truth` bằng token F1 và LLM judge nếu provider khả dụng; nếu không, code có heuristic fallback.
3. Quality checks đo nhiều chiều như schema, completeness, uniqueness, validity và consistency. Freshness monitoring tập trung vào tuổi dữ liệu: publication range, stale-row count và trạng thái fresh/stale theo ngưỡng 180 ngày.
4. Phải dùng cùng test set vì chỉ khi biến kiểm soát này được giữ nguyên mới có thể quy thay đổi metrics cho corruption hoặc repair. Tạo test set mới sau corruption có thể loại bỏ đúng những document bị xóa và che mất ảnh hưởng thật.
5. Repair thành công khi repaired clean artifacts được tái tạo từ raw source đáng tin cậy, quality/freshness signals phục hồi, và các metrics retrieval/answer tiến gần baseline. Cần đối chiếu cùng test set, corruption log, metrics JSON và comparison report; chỉ việc pipeline chạy hết không đủ chứng minh repair thành công.

## 8. Phân tích kết quả

### Metrics chính sau khi role 3 chạy tích hợp

| Metric/signal | Baseline | Corrupted | Repaired | Nhận xét cá nhân |
| --- | ---: | ---: | ---: | --- |
| `retrieval_hit_rate` | 1.0000 | 0.8750 | 1.0000 | Corruption làm giảm 0.1250; repair phục hồi hoàn toàn |
| `mean_token_f1` | 0.6667 | 0.5475 | 0.6667 | Giảm 0.1192 rồi phục hồi đúng baseline |
| `judge_accuracy` | 0.6667 | 0.5417 | 0.6667 | Giảm 0.1250 rồi phục hồi; cả ba lượt dùng heuristic fallback |
| `mean_judge_score` | 3.6667 | 3.1667 | 3.6667 | Giảm 0.5000 rồi phục hồi 0.5000 |
| Quality checks | PASS 16/16 | FAIL 9/16 | PASS 16/16 | Corrupted data làm fail 7 checks; repaired data phục hồi toàn bộ |
| Freshness status | FRESH, 0/24 stale | STALE, 2/24 stale | FRESH, 0/24 stale | Oldest date đổi từ `2026-02-12` thành `2020-01-01`, sau repair trở lại baseline |

### Kết luận từ số liệu hiện có

Baseline clean dataset đạt 16/16 quality checks, có 24/24 dòng trong phạm vi freshness và retrieval hit rate đạt 1.0000. Corruption flow xóa hai paper mới nhất, blank hai summary, inject noise vào hai summary, truncate một title, làm stale hai publication date và thêm hai duplicate. Sau corruption, quality giảm còn 9/16 checks pass và freshness chuyển từ fresh sang stale.

Hai chuỗi nguyên nhân–bằng chứng từ artifacts thực tế:

1. **Drop latest records và các lỗi text/date/duplicate** → quality giảm từ 16/16 xuống 9/16, stale rows tăng từ 0 lên 2 → retrieval hit rate giảm `1.0000 → 0.8750`, mean token F1 giảm `0.6667 → 0.5475`, judge accuracy giảm `0.6667 → 0.5417`.
2. **Repair bằng cách tái tạo clean data từ raw records** → quality phục hồi 16/16, stale rows trở về 0 → retrieval hit rate, mean token F1, judge accuracy và mean judge score đều trở lại đúng giá trị baseline.

Corruption ảnh hưởng rõ nhất đến retrieval là `drop_latest_records`. Ba retrieval miss đều thuộc paper `10.2118/234689-pa`, một trong hai paper bị xóa, tương ứng ba câu hỏi summary/authors/date của cùng ground-truth document. Điều này giải thích trực tiếp mức giảm hit rate `3/24 = 0.125`.

Kết quả khác kỳ vọng là baseline `mean_token_f1` chỉ đạt 0.6667 dù retrieval hit rate bằng 1.0000. Phân tích answers artifact cho thấy cả tám câu hỏi `authors` có token F1 bằng 0, trong khi summary và date đạt 1.0 ở baseline. Nguyên nhân là test set dùng mẫu “Who are the authors...” nhưng `_extract_answer()` trong `qa.py` chỉ nhận diện “who authored” hoặc “list the authors”. Đây là contract mismatch giữa evaluation question và deterministic answer parser; cần sửa wording hoặc mở rộng parser rồi chạy lại cả ba trạng thái trước khi coi metrics mới là kết quả cuối cùng.

Ngoài ra, `ragas` được skip và cả 24 judge verdict ở mỗi trạng thái đều ghi `Fallback heuristic judge used because the LLM evaluator was unavailable.` Vì vậy `judge_accuracy` và `mean_judge_score` hiện phản ánh heuristic dựa trên token F1, không phải đánh giá của một LLM bên ngoài. Báo cáo không diễn giải chúng như LLM-based metrics.

## 9. Điều học được và hướng cải thiện

### Ba điều quan trọng nhất

1. Data contract phải bao gồm schema, semantics, naming, artifact path và cả format text mà downstream parser phụ thuộc.
2. Observability tốt cần trả về tín hiệu có cấu trúc (`dimension`, `failed_rows`, `observed`, `expected`) thay vì chỉ một boolean pass/fail, để có thể giải thích nguyên nhân và tự động render report.
3. Đánh giá ảnh hưởng dữ liệu lên RAG cần giữ nguyên test set; nếu thay đổi evaluation data giữa các trạng thái thì không thể đưa ra kết luận nhân quả đáng tin cậy.

### Nếu có thêm thời gian

Tôi sẽ bổ sung contract/schema validation bằng Pydantic cho evaluation và quality payload, đồng thời thêm integration test chạy một embedding backend nhẹ hoặc mock index qua toàn bộ `evaluate_pipeline()`. Cải thiện sẽ được đo bằng tỷ lệ payload validation pass, branch coverage cho error cases và khả năng chạy lại baseline/corruption/repaired với cùng hash của test set.

## 10. Cam kết của thành viên

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Mọi kết luận về kết quả đều có artifact hoặc metric để đối chiếu.
- [x] Tôi không ghi “đã chạy thành công” cho phần chưa được kiểm chứng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Trần Nguyễn Anh Minh

**Ngày xác nhận:** 2026-08-06
