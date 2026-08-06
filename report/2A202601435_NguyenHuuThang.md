# Báo cáo cá nhân — Day 10: Data Pipeline & Data Observability

## 1. Thông tin cá nhân

| Thông tin | Nội dung |
| --- | --- |
| Họ và tên | Nguyễn Hữu Thắng |
| MSSV | 2A202601435 |
| Khóa/Lớp | K3 |
| Tên nhóm | K3-DAY10-Fishing |
| Vai trò chính | Thành viên 1 — Data Ingestion & Cleaning Owner |
| Ngày hoàn thành | 2026-08-06 |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao | Trạng thái |
| --- | --- | --- | --- | --- |
| Thu thập và parse dữ liệu Crossref | `src/ingestion/crossref.py`: `parse_crossref_payload`, `fetch_source_records`, `load_raw_records` | Crossref Works API và cấu hình query/filter | Raw HTTP payload và danh sách phẳng theo `PaperRecord` | Hoàn thành |
| Làm sạch và mô hình hóa dữ liệu | `src/ingestion/cleaning.py`: `build_clean_dataframe`, `save_clean_dataframe` | Danh sách `PaperRecord`, thời điểm chạy | Clean DataFrame, CSV/JSON và `text_for_embedding` | Hoàn thành |
| Contract package ingestion | `src/ingestion/__init__.py` | Các hàm public của ingestion | Export hàm build/save clean data cho pipeline | Hoàn thành |

Phạm vi của tôi kết thúc ở việc bàn giao raw/clean artifacts và schema ổn định. Evaluation set, quality/freshness implementation, embedding, orchestration, corruption và repair thuộc owner khác. Tôi chỉ sử dụng artifact của các phần đó để xác nhận output mình tạo ra tương thích với pipeline.

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động | Thành viên/module được hỗ trợ | Kết quả |
| --- | --- | --- |
| Kiểm tra contract với retrieval và observability | `retrieval/index.py`, `observability/quality.py` | Clean dataset có đủ các cột downstream cần dùng |
| Sinh dữ liệu thật để nhóm tích hợp | Evaluation/observability và pipeline owners | Bàn giao 24 raw records và 24 clean records |
| Kiểm tra dữ liệu sau tích hợp | Quality/freshness artifacts của thành viên 2 | 16/16 quality checks pass; dữ liệu được đánh dấu fresh |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao | Cách xác minh |
| --- | --- | --- | --- |
| Gọi Crossref API theo query và filter cấu hình | `fetch_source_records` | Nhận 24 công bố khoa học | `data/raw/crossref_response.json` |
| Retry các lỗi HTTP tạm thời | `Retry`, `HTTPAdapter` trong `crossref.py` | Retry tối đa 4 lần, backoff 1 giây cho 429/500/502/503/504 | Đọc cấu hình retry và smoke test module |
| Parse payload lồng nhau | `parse_crossref_payload` | DOI, title, summary, authors, categories, dates và URL được đưa về `PaperRecord` | `data/raw/crossref_records.json` |
| Làm sạch XML/HTML và chuẩn hóa text | `build_clean_dataframe` | Title/summary sạch tag và khoảng trắng thừa | `data/clean/papers_clean.csv` |
| Lọc và deduplicate | `build_clean_dataframe` | Loại title rỗng, summary dưới 100 ký tự, ngày lỗi và DOI trùng | Quality report không có missing/duplicate/short summary |
| Tạo freshness và embedding fields | `age_days`, `summary_chars`, `text_for_embedding` | 24 records sẵn sàng cho retrieval | Clean CSV/JSON và freshness report |
| Lưu hai định dạng clean | `save_clean_dataframe` | CSV cho phân tích và JSON records cho pipeline | `data/clean/papers_clean.csv`, `data/clean/papers_clean.json` |

Output cụ thể của phần việc là một chuỗi artifact có thể audit: response nguyên bản từ Crossref → 24 `PaperRecord` → 24 clean records. Clean schema gồm 16 cột: `paper_id`, `title`, `summary`, `authors`, `categories`, `primary_category`, `published`, `updated`, `age_days`, `abs_url`, `pdf_url`, `comment`, `authors_joined`, `categories_joined`, `summary_chars`, `text_for_embedding`.

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Crossref trả về JSON có nhiều cấu trúc không đồng nhất: title là list, author là list các dict, ngày nằm trong `date-parts`, abstract có tag JATS/XML và một số metadata có thể thiếu. Nếu đưa trực tiếp dữ liệu này sang embedding, text nhiễu và schema không ổn định sẽ làm index khó xây dựng, freshness sai và document identity không đáng tin cậy.

### Cách triển khai

Ở tầng ingestion, tôi dùng query/filter từ `Settings`, gọi `https://api.crossref.org/works`, cấu hình retry/backoff cho lỗi tạm thời, rồi lưu payload trước khi biến đổi để bảo đảm khả năng audit. Parser ưu tiên `abstract`, fallback sang `description`; ghép `given` và `family` của tác giả; loại trùng authors/categories; chuẩn hóa ngày thiếu tháng hoặc ngày về ngày đầu tháng/năm; dùng DOI viết thường làm `paper_id`; và bỏ record không có DOI hoặc title.

Ở tầng cleaning, title và summary được decode HTML entity, bỏ tag XML/HTML và chuẩn hóa whitespace. Record bị loại nếu thiếu identity/title, summary dưới 100 ký tự hoặc ngày xuất bản không parse được. Các DOI trùng được giữ bản cập nhật mới nhất. `published` được chuẩn hóa `YYYY-MM-DD`, `age_days` được tính theo UTC và không âm. Trường embedding được tạo theo contract:

```text
Title: [title] | Authors: [authors_joined] | Summary: [summary]
```

### Input, output và contract

| Thành phần | Mô tả |
| --- | --- |
| Input | Crossref JSON hoặc snapshot JSON; `Settings`; `run_date` |
| Output | `list[PaperRecord]` và clean `pandas.DataFrame` |
| Module phụ thuộc | `core.config`, `core.utils`, `requests`, `pandas` |
| Module sử dụng output | `pipelines.phase1`, `retrieval.index`, evaluation và observability |
| Điều kiện lỗi cần xử lý | 429/503, response sai schema, thiếu DOI/title/summary, XML/JATS, ngày lỗi, duplicate DOI |

### Cách xác minh

```powershell
.\.venv\Scripts\python.exe -m compileall -q src
.\.venv\Scripts\python.exe -u script\run_phase1.py
.\.venv\Scripts\python.exe -u script\run_corruption_flow.py
```

Ngoài compile check, tôi đã chạy smoke test với payload giả lập gồm XML/JATS, `description` fallback, summary ngắn, record thiếu title, ngày lồng trong `date-parts` và DOI trùng; sau đó chạy thật với Crossref API.

- **Kết quả mong đợi:** parser và cleaner chạy không lỗi; record không đạt yêu cầu bị loại; bốn artifact raw/clean được tạo.
- **Kết quả thực tế:** ingestion tạo 24 raw records và cleaning giữ lại 24 clean records; baseline và corruption flow đều chạy hết với exit code 0. Baseline/repaired có 24 documents; corrupted dataset vẫn có 24 dòng do xóa 2 dòng rồi thêm 2 duplicate.
- **Artifact/log:** `data/raw/crossref_response.json`, `data/raw/crossref_records.json`, `data/clean/`, `data/results/`, `data/quality/` và `data/reports/`.

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Cần quyết định giữ nguyên abstract ngắn hay loại trước khi embedding.
- **Các phương án đã cân nhắc:** (1) giữ mọi abstract để tối đa số bản ghi; (2) loại summary dưới 100 ký tự để ưu tiên chất lượng ngữ nghĩa.
- **Phương án đã chọn:** Loại summary dưới 100 ký tự sau khi đã bỏ XML/HTML.
- **Lý do:** Độ dài phải được đo trên nội dung thật, không tính markup. Summary quá ngắn thường không đủ thông tin để retrieval phân biệt tài liệu, làm giảm chất lượng corpus dù row count cao hơn.
- **Bằng chứng quyết định phù hợp:** `baseline_quality.json` báo `summary_length` pass, 0 dòng vi phạm; toàn bộ 24 clean records có summary hợp lệ.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi nguyên văn:** `requests.exceptions.ProxyError: HTTPSConnectionPool(host='api.crossref.org', port=443): Max retries exceeded`.
- **Bước tái hiện:** Chạy fetch Crossref trong môi trường sandbox bị giới hạn mạng.
- **Nguyên nhân gốc:** Proxy của sandbox từ chối kết nối ra ngoài; không phải lỗi parser hoặc Crossref query.
- **Cách xử lý:** Chạy lại phép kiểm thử mạng với quyền kết nối phù hợp, giữ nguyên retry/backoff trong client.
- **Cách xác minh sau khi sửa:** API trả về 24 records; cả raw response và parsed records được ghi thành công.
- **Điều học được:** Cần phân biệt lỗi hạ tầng mạng với lỗi logic ingestion; raw artifact và thông báo lỗi đầy đủ giúp truy nguyên nhanh hơn.

## 7. Hiểu biết về luồng end-to-end

1. Crossref trả metadata; ingestion lưu response để audit và parse thành `PaperRecord`. Cleaning chuẩn hóa dữ liệu, tạo `text_for_embedding`; embedding model biến text thành vector và ChromaDB lưu vector cùng metadata để retrieval truy vấn.
2. Mỗi sample evaluation chứa câu hỏi, ground truth và `ground_truth_doc_ids`. IDs được so với tài liệu retrieval trả về để tính hit rate; câu trả lời được so với ground truth để tính Token F1 và judge metrics. Trong lần chạy cuối, evaluator sử dụng OpenAI GPT-4o-mini thành công; reasoning chi tiết cho từng sample được lưu trong answers artifacts.
3. Quality checks đo completeness, uniqueness, validity và consistency của dữ liệu. Freshness monitoring tập trung vào tuổi dữ liệu, ngày mới nhất/cũ nhất và số record vượt ngưỡng stale.
4. Baseline, corrupted và repaired phải dùng cùng test set để giữ nguyên độ khó và ground truth. Nếu thay test set, chênh lệch metric không còn phản ánh riêng tác động của corruption/repair.
5. Repair thành công khi repaired clean artifact khôi phục schema/chất lượng/freshness và các retrieval/answer metrics tiến gần hoặc trở lại baseline. Cần đối chiếu đồng thời clean data, quality report, freshness report và comparison metrics.

## 8. Phân tích kết quả

### Metrics và signal thực nghiệm

| Metric/signal | Baseline | Corrupted | Repaired | Nhận xét của cá nhân |
| --- | ---: | ---: | ---: | --- |
| `retrieval_hit_rate` | 1.0000 | 0.8750 | 1.0000 | Corruption làm giảm 0.1250; repair phục hồi hoàn toàn |
| `mean_token_f1` | 0.6667 | 0.5475 | 0.6667 | Giảm 0.1192 rồi trở lại baseline |
| `judge_accuracy` | 0.6250 | 0.5417 | 0.6250 | GPT-4o-mini judge giảm 0.0833 rồi phục hồi baseline |
| `mean_judge_score` | 3.5000 | 3.2917 | 3.5000 | GPT-4o-mini judge giảm 0.2083 rồi phục hồi baseline |
| Quality checks | PASS, 16/16 | FAIL, 9/16 | PASS, 16/16 | Corruption làm thất bại 7 checks; repair khôi phục tất cả |
| Freshness status | PASS, 0/24 stale | FAIL, 2/24 stale | PASS, 0/24 stale | Corruption đổi 2 ngày thành `2020-01-01` |

### Kết luận từ số liệu

Hai pipeline được chạy lại trên cùng `data/eval/test_set.json` gồm 24 câu hỏi: 8 câu summary, 8 câu authors và 8 câu date. Chuỗi bằng chứng quan sát được là:

1. **Corruption → quality/freshness giảm → agent metrics giảm:** corrupted dataset vi phạm uniqueness (4 duplicate rows), title length (1), summary completeness/length (2), date-age consistency (2), freshness (2) và noise marker (2). Quality chuyển từ PASS sang FAIL, hit rate giảm từ 1.0000 xuống 0.8750 và Token F1 giảm từ 0.6667 xuống 0.5475.
2. **Repair từ raw snapshot → quality/freshness phục hồi → metrics phục hồi:** chạy lại `build_clean_dataframe` từ `crossref_records.json` đưa quality về 16/16, stale rows về 0, hit rate về 1.0000 và Token F1 về 0.6667. Repaired metrics bằng đúng baseline trên cả bốn metric.

Phân tích theo từng câu hỏi cho thấy ba retrieval miss đều thuộc tài liệu `10.2118/234689-pa`, một trong hai tài liệu bị xóa. Việc blank summary của `10.1007/s10278-026-02086-9` làm câu summary của tài liệu này giảm Token F1 từ 1.0 xuống 0.0 dù retrieval vẫn hit. Đây là hai tác động trực tiếp có thể truy vết từ `corruption_log.json` sang answers artifacts.

Không thể kết luận inject-noise là corruption ảnh hưởng mạnh nhất trong lần chạy này: hai tài liệu bị inject noise, tài liệu bị truncate title và hai tài liệu bị làm stale không nằm trong ground-truth documents của test set. Chúng làm quality/freshness checks fail nhưng không có sample tương ứng để đo tác động riêng lên agent metrics. Hai duplicate documents có xuất hiện trong test set nhưng không tạo thay đổi metric quan sát được. Giới hạn này cho thấy evaluation set cần bao phủ từng corruption scenario nếu muốn quy kết tác động theo từng loại lỗi.

Trong lần chạy cuối, `baseline_answers.json`, `corrupted_answers.json` và `repaired_answers.json` chứa reasoning chi tiết do GPT-4o-mini tạo, xác nhận evaluator thật đã hoạt động. Judge accuracy giảm từ 0.6250 xuống 0.5417 và mean judge score giảm từ 3.5000 xuống 3.2917 sau corruption; cả hai trở lại đúng baseline sau repair. Vì LLM judge có thể có dao động giữa các lần gọi, các con số này gắn với artifacts của lần chạy 2026-08-06 và nên được tái hiện nhiều lần nếu cần ước lượng độ ổn định.

## 9. Điều học được và hướng cải thiện

### Ba điều quan trọng nhất

1. Raw response bất biến và parsed snapshot là hai lớp bằng chứng khác nhau: một lớp phục vụ audit nguồn, lớp còn lại tạo contract ổn định cho pipeline.
2. Data quality phải được áp dụng sau normalization; ví dụ độ dài summary trước khi bỏ XML không phản ánh lượng nội dung thật.
3. Retrieval phụ thuộc trực tiếp vào document identity và `text_for_embedding`; duplicate DOI, title bẩn hoặc abstract ngắn có thể làm kết quả tìm kiếm sai ngay cả khi embedding/index vẫn chạy được.

### Nếu có thêm thời gian

Tôi sẽ mở rộng evaluation set để mỗi DOI chịu từng loại corruption đều có câu hỏi summary/authors/date tương ứng, đồng thời thêm ablation run chỉ bật một corruption mỗi lần. Khi đó có thể đo riêng mức giảm hit rate và Token F1 của drop, blank summary, noise, truncate, stale và duplicate thay vì chỉ kết luận trên corruption hỗn hợp.

## 10. Cam kết của thành viên

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Mọi kết luận về kết quả đều có artifact hoặc metric để đối chiếu.
- [x] Tôi không ghi “đã chạy thành công” cho phần chưa được kiểm chứng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Nguyễn Hữu Thắng

**Ngày xác nhận:** 2026-08-06
