# Group Report — Day 10: Data Pipeline & Data Observability

## 1. Thông tin bài nộp

| Thông tin | Nội dung |
| --- | --- |
| Khóa/Lớp | K3 |
| Tên nhóm | K3-DAY10-Fishing — Nhóm 3 người |
| Repository | https://github.com/LunaDream74/K3-DAY10-Fishing |
| Ngày hoàn thành | 2026-08-06 |

### Thành viên và phân công

| STT | Họ và tên | MSSV | Vai trò chính | Module/deliverable sở hữu |
| --: | --- | --- | --- | --- |
| 1 | Nguyễn Hữu Thắng | 2A202601435 | Data Ingestion & Cleaning Owner | `crossref.py`, `cleaning.py`; raw/clean artifacts |
| 2 | Trần Nguyễn Anh Minh | 2A202601475 | Evaluation & Observability Owner | `testset.py`, `quality.py`, `reporting.py`; evaluation/quality reports |
| 3 | Nguyễn Hữu Hiếu | 2A202601429 | Corruption & Integration Owner | `corruption.py`, `phase1.py`, `corruption_flow.py`; end-to-end flows |

## 2. Tóm tắt kết quả

Nhóm đã hoàn thành pipeline hai pha từ Crossref đến đánh giá và phục hồi dữ liệu. Pha baseline lấy 24 công bố theo chủ đề agentic RAG/LLM, lưu response để audit, parse thành `PaperRecord`, làm sạch thành 24 documents và index bằng MiniLM trong ChromaDB. Evaluation set cố định gồm 24 câu hỏi summary, authors và date. Baseline đạt retrieval hit rate 1.0000, Mean Token F1 0.6667 và data quality PASS 16/16 checks; toàn bộ 24 records fresh theo ngưỡng 180 ngày.

Pha corruption áp dụng sáu nhóm lỗi: xóa record mới, blank summary, inject noise, truncate title, làm cũ ngày và duplicate. Quality chuyển sang FAIL 9/16, freshness có 2 stale rows, hit rate giảm còn 0.8750 và Token F1 còn 0.5475. Repair đọc lại raw snapshot rồi chạy cleaning/index/evaluation cùng test set, phục hồi toàn bộ quality, freshness và metrics về baseline.

Phân tích answers cho thấy tác động metric trực tiếp đến từ một ground-truth document bị xóa và một document bị blank summary. Các lỗi noise/truncate/stale vẫn được observability phát hiện, nhưng test set không chứa ground truth tương ứng nên chưa thể quy kết tác động riêng lên agent. Lần chạy cuối sử dụng GPT-4o-mini trực tiếp qua OpenAI cho LLM judge; answers artifacts chứa reasoning chi tiết của model và không còn fallback heuristic. Ragas được chủ động bỏ qua.

## 3. Kiến trúc và luồng dữ liệu

```text
Crossref Works API
    -> raw response + flat PaperRecord snapshot
    -> cleaning, validation, freshness fields
    -> MiniLM embeddings + ChromaDB baseline index
    -> fixed evaluation set + baseline evaluation
    -> quality/freshness reports
    -> controlled corruption + corrupted index/evaluation
    -> repair from raw snapshot + repaired index/evaluation
    -> baseline/corrupted/repaired comparison report
```

### Trách nhiệm của từng khối

| Khối | Input | Xử lý chính | Output/artifact | Owner |
| --- | --- | --- | --- | --- |
| Ingestion | Crossref Works API | Query, retry/backoff, parse nested metadata | `data/raw/crossref_response.json`, `crossref_records.json` | Nguyễn Hữu Thắng |
| Cleaning | `list[PaperRecord]` | Strip XML/HTML, normalize, validate, deduplicate, freshness/embedding fields | `data/clean/papers_clean.csv/.json` | Nguyễn Hữu Thắng |
| Embedding/index | Clean DataFrame | MiniLM normalized embeddings, Chroma cosine collections | `data/chroma/`, `data/embeddings/` | Nguyễn Hữu Hiếu (integration) |
| Evaluation | Clean corpus và test set | 24 ground-truth questions, retrieval/answer scoring | `data/eval/`, `data/results/*metrics.json` | Trần Nguyễn Anh Minh |
| Observability | Baseline/corrupted/repaired DataFrames | 16 schema, completeness, validity, consistency, uniqueness và freshness checks | `data/quality/`, generated reports | Trần Nguyễn Anh Minh |
| Corruption/repair | Baseline clean data và raw snapshot | Sáu corruption actions; repair bằng re-clean raw snapshot | corrupted/repaired datasets, log và metrics | Nguyễn Hữu Hiếu |
| Orchestration | Tất cả module trên | Chạy đúng thứ tự, dùng chung test set | `phase1_report.md`, `corruption_report.md` | Nguyễn Hữu Hiếu |

## 4. Cách tái hiện kết quả

### Cấu hình không chứa secret

| Biến/cấu hình | Giá trị sử dụng |
| --- | --- |
| `LLM_PROVIDER` | `openai` |
| `LLM_MODEL` | `gpt-4o-mini` |
| Embedding model | `sentence-transformers/all-MiniLM-L6-v2` |
| Số lượng Crossref records | 24 |
| Retrieval `top_k` | 4 |
| Freshness threshold | 180 ngày |
| Random seed | Không dùng; corruption chọn dòng theo thứ tự xác định |
| `REFRESH_SOURCE`, `REFRESH_TEST_SET` | `False`, dùng snapshot/test set cố định |

Không có API key hoặc nội dung `.env` trong báo cáo/repository.

### Lệnh cài đặt và chạy thực tế

```powershell
uv sync
.\.venv\Scripts\python.exe -u script\run_phase1.py
.\.venv\Scripts\python.exe -u script\run_corruption_flow.py
```

### Kết quả tái hiện

| Lệnh | Trạng thái | Thời điểm chạy gần nhất | Bằng chứng |
| --- | --- | --- | --- |
| Baseline pipeline | Thành công, exit code 0 | 2026-08-06 11:54 (UTC+7) | `data/reports/phase1_report.md`, baseline metrics |
| Corruption flow | Thành công, exit code 0 | 2026-08-06 11:54 (UTC+7) | `data/reports/corruption_report.md`, corruption log |

Lần chạy cần quyền mạng để tải/kiểm tra MiniLM trên Hugging Face. Model đã được cache sau lần tải đầu.

## 5. Ingestion, cleaning và data contract

### Nguồn dữ liệu

| Thuộc tính | Giá trị |
| --- | --- |
| Source | `https://api.crossref.org/works` |
| Query | `agentic retrieval augmented generation large language model` |
| Filter | `from-pub-date:2026-02-07,has-abstract:true` |
| Raw artifact hiện tại | Tạo ngày 2026-08-06; pipeline gần nhất load lại snapshot |
| Số record nhận được | 24 |
| Retry/backoff | Tối đa 4 lần, backoff factor 1.0; retry 429/500/502/503/504 và tôn trọng `Retry-After` |

### Raw và clean schema

| Trường | Kiểu dữ liệu | Bắt buộc? | Ý nghĩa | Xử lý khi thiếu/sai |
| --- | --- | --- | --- | --- |
| `paper_id` | string | Có | DOI, document identity | Drop nếu thiếu; lowercase; deduplicate |
| `title` | string | Có | Tiêu đề công bố | Drop nếu thiếu; strip tag/whitespace |
| `summary` | string | Có | Abstract hoặc description | Fallback description; drop nếu dưới 100 ký tự sau clean |
| `authors` / `categories` | list[string] | Không | Tác giả/chủ đề chuẩn hóa | List rỗng; loại item trống/trùng |
| `published`, `updated` | `YYYY-MM-DD` string | Published có | Ngày xuất bản/cập nhật | Parse Crossref `date-parts`; drop nếu published lỗi |
| `age_days` | integer | Có | Tuổi record tại thời điểm chạy | Tính theo UTC; không âm |
| `authors_joined`, `categories_joined` | string | Có | Chuỗi metadata cho retrieval/report | Join bằng dấu phẩy |
| `summary_chars` | integer | Có | Độ dài summary đã normalize | Tính lại sau clean |
| `text_for_embedding` | string | Có | Nội dung đưa vào MiniLM | Rebuild từ title/authors/summary |
| `abs_url`, `pdf_url`, `comment` | string | Không | Link và publisher metadata | Chuỗi rỗng nếu thiếu |

### Quy tắc cleaning trên baseline

| Quy tắc | Quality dimension | Số record bị loại/vi phạm | Cách xác minh |
| --- | --- | ---: | --- |
| Drop thiếu DOI/title | Completeness | 0 trong parsed snapshot | 24 raw → 24 clean |
| Strip XML/HTML và normalize whitespace | Validity | 24 records được normalize | Clean CSV/JSON |
| Drop summary dưới 100 ký tự | Validity | 0 | `summary_length`: PASS, 0 failed rows |
| Parse và chuẩn hóa published | Validity | 0 | `published_valid`: PASS |
| Deduplicate DOI | Uniqueness | 0 | `paper_id_unique`: PASS |
| Tính/đối chiếu `age_days` | Consistency | 0 | `published_age_consistent`: PASS |

`paper_id` là DOI lowercase và ổn định xuyên suốt raw, index, evaluation và repair. `text_for_embedding` có dạng `Title: ... | Authors: ... | Summary: ...`. `age_days` là chênh lệch ngày UTC giữa thời điểm chạy và `published`, được chặn tối thiểu ở 0.

## 6. Evaluation setup

| Thành phần | Cấu hình thực tế |
| --- | --- |
| Số câu hỏi | 24 |
| `question_type` | 8 summary, 8 authors, 8 date |
| Ground-truth document ID | DOI từ clean dataset trong `ground_truth_doc_ids` |
| Embedding model | `sentence-transformers/all-MiniLM-L6-v2` |
| Vector store/collections | ChromaDB cosine: `papers-baseline`, `papers-corrupted`, `papers-repaired` |
| Retrieval `top_k` | 4 |
| LLM provider/model | OpenAI / `gpt-4o-mini`; judge được gọi thành công trong lần chạy cuối |
| Test set chung | `data/eval/test_set.json` |

Cùng một test set được dùng cho ba trạng thái để giữ cố định câu hỏi, ground truth và độ khó. Nhờ vậy delta metrics phản ánh thay đổi corpus/index do corruption và repair, không bị nhiễu bởi việc đổi bộ đề.

## 7. Kết quả baseline

### Artifact checklist

| Artifact | Đường dẫn thực tế | Trạng thái | Ghi chú |
| --- | --- | --- | --- |
| Raw response/records | `data/raw/` | Có | Response audit và 24 flat records |
| Cleaned dataset | `data/clean/papers_clean.csv/.json` | Có | 24 rows |
| Embedding manifest/index | `data/embeddings/`, `data/chroma/` | Có | Baseline/corrupted/repaired collections |
| Evaluation set | `data/eval/test_set.json` | Có | 24 samples |
| Baseline metrics/answers | `data/results/baseline_*.json` | Có | 24 evaluated samples |
| Quality/freshness | `data/quality/` | Có | Ba trạng thái |
| Generated reports | `data/reports/` | Có | Phase 1 và comparison report |

### Baseline metrics

| Metric | Giá trị | Diễn giải |
| --- | ---: | --- |
| `retrieval_hit_rate` | 1.0000 | Ground-truth DOI xuất hiện trong top-4 ở 24/24 samples |
| `mean_token_f1` | 0.6667 | Trung bình overlap token giữa answer và ground truth |
| `judge_accuracy` | 0.6250 | GPT-4o-mini đánh dấu đúng 15/24 samples |
| `mean_judge_score` | 3.5000 | Điểm judge trung bình do GPT-4o-mini chấm |
| Ragas | N/A | Skipped; cần `RUN_RAGAS=1` để bật pass chậm hơn |

## 8. Data quality và freshness

### Quality checks baseline

| Nhóm check | Quality dimension | Kỳ vọng | Kết quả baseline | Bằng chứng |
| --- | --- | --- | --- | --- |
| Required columns | Schema | Có đủ 6 cột lõi | PASS | `baseline_quality.json` |
| Row count | Completeness | ≥24 | PASS, 24 | Cùng artifact |
| ID/title/summary/text complete | Completeness | 0 empty | PASS, 0 failed | Cùng artifact |
| `paper_id` unique | Uniqueness | 0 duplicate rows | PASS | Cùng artifact |
| Title ≥10, summary ≥100 | Validity | 0 vi phạm | PASS | Cùng artifact |
| Summary chars/text consistency | Consistency | 0 vi phạm | PASS | Cùng artifact |
| Published/age valid và consistent | Validity/Consistency | Sai lệch ≤1 ngày | PASS | Cùng artifact |
| Freshness/noise markers | Freshness/Validity | 0 stale, 0 marker | PASS | Cùng artifact |

Tổng baseline: **PASS 16/16 checks**, 0 failed checks.

### Freshness baseline

| Thuộc tính | Giá trị |
| --- | --- |
| Dataset được đo | `data/clean/papers_clean.csv` |
| Ngày mới nhất | 2026-08-01 |
| Ngày cũ nhất | 2026-02-12 |
| Ngưỡng freshness | 180 ngày |
| Trạng thái | FRESH/PASS |
| Lý do | 0/24 records stale; không có ngày/age không hợp lệ |

## 9. Corruption scenarios và repair

| Corruption | Cách tạo | Records tác động | Quality signal thực tế | Tác động agent quan sát được |
| --- | --- | ---: | --- | --- |
| Drop latest | Xóa 2 records mới nhất | 2 | Corpus thiếu 2 DOI nhưng row count bị duplicate bù lại | Một DOI thuộc test set gây 3 retrieval misses |
| Blank summary | Set summary rỗng, chars=0 | 2 | Completeness/length fail 2 rows | Một ground-truth summary giảm F1 từ 1.0 xuống 0.0 |
| Inject noise | Thêm `[corrupted_noise] lorem ipsum ###` | 2 | Noise marker fail 2 rows | Chưa đo riêng: không thuộc ground-truth test docs |
| Truncate title | Đổi title thành `Short` | 1 | Title length fail 1 row | Chưa đo riêng: không thuộc ground-truth test docs |
| Stale date | Đổi published thành 2020-01-01, age=2400 | 2 | Freshness và date-age consistency fail 2 rows | Không có sample tương ứng; freshness FAIL |
| Add duplicates | Nhân bản 2 dòng cuối | 2 DOI/4 duplicate rows | Uniqueness fail 4 rows | Hai DOI có trong test set nhưng metric không đổi quan sát được |

- **Corruption log:** `data/results/corruption_log.json` — có đủ action, count, affected DOI và mô tả.
- **Repair:** Không chỉnh trực tiếp corrupted CSV. Pipeline đọc `data/raw/crossref_records.json`, chạy lại cùng `build_clean_dataframe`, lưu repaired clean artifacts, rebuild collection và đánh giá lại trên test set cũ. Cách này giữ data lineage và tránh che lỗi bằng sửa tay.

## 10. So sánh baseline, corrupted và repaired

| Metric/signal | Baseline | Corrupted | Repaired | Delta corruption | Recovery | Nhận xét |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `retrieval_hit_rate` | 1.0000 | 0.8750 | 1.0000 | -0.1250 | +0.1250 | Phục hồi đúng baseline |
| `mean_token_f1` | 0.6667 | 0.5475 | 0.6667 | -0.1192 | +0.1192 | Phục hồi đúng baseline |
| `judge_accuracy` | 0.6250 | 0.5417 | 0.6250 | -0.0833 | +0.0833 | GPT-4o-mini judge; phục hồi baseline |
| `mean_judge_score` | 3.5000 | 3.2917 | 3.5000 | -0.2083 | +0.2083 | GPT-4o-mini judge; phục hồi baseline |
| Quality checks | PASS 16/16 | FAIL 9/16 | PASS 16/16 | -7 passed | +7 passed | Phục hồi toàn bộ checks |
| Freshness | PASS, 0 stale | FAIL, 2 stale | PASS, 0 stale | +2 stale | -2 stale | Phục hồi hoàn toàn |

Hai chuỗi bằng chứng:

1. Drop một ground-truth DOI và blank một ground-truth summary → corpus thiếu nội dung, quality FAIL → 3 retrieval misses, hit rate giảm 0.1250 và Token F1 giảm 0.1192.
2. Re-clean từ raw snapshot → uniqueness/completeness/freshness trở lại PASS → cả bốn evaluation metrics bằng đúng baseline.

Không quy kết riêng noise/truncate/stale làm giảm agent metric vì test set không bao phủ các DOI đó. Judge metrics trong lần chạy cuối được GPT-4o-mini chấm thật; baseline và repaired bằng nhau, trong khi corrupted giảm 0.0833 accuracy và 0.2083 mean score.

## 11. Vấn đề tích hợp quan trọng

- **Triệu chứng:** Lần chạy baseline trong sandbox dừng tại bước load MiniLM với lỗi kết nối tới Hugging Face; log có `WinError 10061` và request tới `huggingface.co`.
- **Nguyên nhân:** Môi trường chạy giới hạn kết nối mạng trong khi model cần được tải/kiểm tra cache lần đầu; không phải lỗi ingestion hay schema.
- **Cách xử lý:** Chạy lại với quyền mạng phù hợp và Python unbuffered để quan sát log. Model được cache; pipeline tiếp tục build Chroma và evaluation.
- **Cách xác minh:** Sau khi cấu hình `OPENAI_API_KEY`, `LLM_PROVIDER=openai` và `LLM_MODEL=gpt-4o-mini`, cả `run_phase1.py` và `run_corruption_flow.py` kết thúc exit code 0. Answers artifacts chứa reasoning riêng cho từng sample do GPT-4o-mini trả về, không còn thông báo fallback.

## 12. Giới hạn và hướng cải thiện

| Giới hạn hiện tại | Ảnh hưởng | Hướng cải thiện có thể kiểm chứng |
| --- | --- | --- |
| Evaluation set không bao phủ mọi corrupted DOI | Không thể tách riêng tác động của noise/truncate/stale | Thêm questions cho mọi affected DOI; đo coverage theo corruption action |
| Sáu lỗi được bật đồng thời | Khó quy kết delta metric cho từng loại | Chạy ablation: một corruption mỗi run, giữ nguyên test set |
| LLM judge có tính không hoàn toàn deterministic | Judge score có thể dao động nhẹ giữa các lần chạy | Cố định temperature/seed nếu provider hỗ trợ và chạy lặp để báo cáo mean/std |
| Ragas bị skip | Thiếu faithfulness/context metrics | Chạy `RUN_RAGAS=1` và lưu artifact riêng |
| Embedding manifest chứa absolute `persist_path` | Khó portable giữa máy thành viên | Lưu relative path hoặc resolve từ project root khi load |
| Chroma binary/cache được commit sau mỗi rebuild | Repo phình và có orphan index directories | Ignore generated index, rebuild bằng pipeline; lưu manifest/checksum thay binary |
| Crossref là nguồn sống, raw corpus chỉ 24 records | Khả năng tổng quát hạn chế | Version raw snapshot, tăng corpus và báo cáo query timestamp/checksum |

## 13. Checklist trước khi nộp

- [x] Thông tin nhóm và repository chính xác.
- [x] Phân công khớp với module, artifact và kết quả thực tế.
- [x] Lệnh tái hiện đã được chạy lại trên phiên bản dùng để nộp.
- [x] Baseline, corrupted và repaired dùng cùng evaluation set.
- [x] Bảng metrics khớp với các file trong `data/results/`.
- [x] Quality/freshness conclusions khớp với `data/quality/`.
- [x] Các đường dẫn báo cáo và artifact truy cập được.
- [x] Ba thành viên đã có báo cáo vai trò riêng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
