# Member Role Report — Day 10: Data Pipeline & Data Observability

## 1. Thông tin cá nhân

| Thông tin         | Nội dung                                                      |
| :----------------- | :------------------------------------------------------------- |
| Họ và tên       | Nguyễn Hữu Hiếu                                             |
| MSSV               | 2A202601429                                                    |
| Khóa/Lớp         | K3                                                             |
| Tên nhóm         | Nhóm 3 người                                                |
| Vai trò chính    | Corruption & Integration Owner (Thành viên 3)                |
| Repository         | Local Repository (Day 10 - Data Pipeline & Data Observability) |
| Ngày hoàn thành | 2026-08-06                                                     |

---

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable                        | File/hàm phụ trách                                                   | Input nhận vào              | Output bàn giao                                                                                               | Trạng thái |
| :---------------------------------------- | :---------------------------------------------------------------------- | :---------------------------- | :------------------------------------------------------------------------------------------------------------- | :----------- |
| **Data Corruption Simulation**      | `src/ingestion/corruption.py` (`corrupt_clean_dataframe`)           | `clean_csv` (`df`)        | `corrupted_clean_csv` & `corruption_log.json`                                                              | Hoàn thành |
| **Baseline Pipeline Orchestration** | `src/pipelines/phase1.py` (`run_phase1_pipeline`)                   | Raw records & Config Settings | Baseline Collection`papers-baseline`, `baseline_metrics.json`, `phase1_report.md`                        | Hoàn thành |
| **Corruption Flow Orchestration**   | `src/pipelines/corruption_flow.py` (`run_corruption_flow_pipeline`) | Clean baseline & Raw snapshot | Corrupted/Repaired collections,`corrupted_metrics.json`, `repaired_metrics.json`, `corruption_report.md` | Hoàn thành |

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động                    | Thành viên/module được hỗ trợ                                                 | Kết quả và bằng chứng                                                                                                  |
| :------------------------------ | :----------------------------------------------------------------------------------- | :-------------------------------------------------------------------------------------------------------------------------- |
| Tích hợp & Chạy thử nghiệm | Thành viên 1 (`cleaning.py`) & Thành viên 2 (`quality.py`, `reporting.py`) | Đã ghép nối thành công toàn bộ giao tiếp giữa Ingestion, Evaluation, Observability và xuất báo cáo tự động |
| Cấu hình LLM & OpenRouter     | Cả nhóm                                                                            | Thiết lập cấu hình`.env` cho GPT-4o-mini qua OpenRouter cho LLM Judge                                                 |

---

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện                                 | File/hàm/artifact liên quan        | Kết quả bàn giao                                                                               | Cách xác minh                                |
| :---------------------------------------------------------- | :----------------------------------- | :------------------------------------------------------------------------------------------------ | :--------------------------------------------- |
| Xây dựng Baseline Pipeline Pha 1                          | `src/pipelines/phase1.py`          | Executed end-to-end; tạo 24 cleaned records, collection`papers-baseline`, `phase1_report.md` | Lệnh:`python script/run_phase1.py`          |
| Bơm lỗi dữ liệu có chủ đích                         | `src/ingestion/corruption.py`      | Tạo`papers_clean_corrupted.csv` và `corruption_log.json` (5 dạng lỗi)                     | Log:`data/results/corruption_log.json`       |
| Điều phối luồng Pha 2 (Corruption ➔ Repair ➔ Compare) | `src/pipelines/corruption_flow.py` | Tạo 3 ChromaDB collections, khôi phục từ`data/raw/`, tạo `corruption_report.md`          | Lệnh:`python script/run_corruption_flow.py` |

---

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Xây dựng bộ điều phối pipeline (Orchestrator) giúp ghép nối các module lẻ của nhóm thành luồng tự động end-to-end, đồng thời thiết kế thuật toán làm hỏng dữ liệu có chủ đích để kiểm thử khả năng phát hiện lỗi và tự phục hồi (Auto-repair) của hệ thống RAG Agent.

### Cách triển khai

1. **`src/ingestion/corruption.py`**:
   - Xóa 2 bản ghi mới nhất dựa trên `published` date.
   - Làm rỗng `summary` cho 2 bản ghi.
   - Chèn ký tự nhiễu `[corrupted_noise] lorem ipsum ###` vào `summary`.
   - Cắt ngắn `title` xuống dưới 10 ký tự.
   - Làm cũ ngày xuất bản thành năm 2020 (`age_days` = 2400 > 180).
   - Nhân bản 2 dòng ở cuối dataframe để giả lập lỗi duplicate `paper_id`.
   - Rebuild trường `text_for_embedding` và ghi nhật ký chi tiết vào `corruption_log.json`.
2. **`src/pipelines/phase1.py` & `corruption_flow.py`**:
   - Sử dụng `load_settings()` quản lý cấu hình tập trung.
   - Phân tách 3 ChromaDB collections riêng biệt: `papers-baseline`, `papers-corrupted`, `papers-repaired`.
   - Tiến hành Repair bằng cách gọi `load_raw_records()` đọc lại snapshot `data/raw/crossref_records.json` ➔ Nạp qua `build_clean_dataframe()` để tái tạo dữ liệu sạch chuẩn mà không cần can thiệp thủ công.

### Input, output và contract

| Thành phần                   | Mô tả                                                                                                                                                 |
| :----------------------------- | :------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Input                          | `records` từ Crossref API, `papers_clean.csv`, `test_set.json`                                                                                   |
| Output                         | 3 ChromaDB Collections,`baseline_metrics.json`, `corrupted_metrics.json`, `repaired_metrics.json`, `phase1_report.md`, `corruption_report.md` |
| Module phụ thuộc             | `ingestion.crossref`, `ingestion.cleaning`, `evaluation.metrics`, `observability.quality`, `observability.reporting`                          |
| Module sử dụng output        | `script/run_phase1.py` và `script/run_corruption_flow.py`                                                                                          |
| Điều kiện lỗi cần xử lý | Tự động gọi`run_phase1_pipeline()` nếu chưa có baseline artifacts trước khi chạy Pha 2                                                      |

### Cách xác minh

```bash
.venv\Scripts\python.exe script/run_phase1.py
.venv\Scripts\python.exe script/run_corruption_flow.py
```

- **Kết quả mong đợi:** Cả 2 script chạy qua 100% các bước với exit code 0, hiển thị `Hit Rate` khôi phục từ 0.8750 ➔ 1.0000.
- **Kết quả thực tế:** Cả 2 script chạy thành công 100%, tất cả metrics và reports khớp 100% với JSON artifacts.
- **Artifact/log:** `data/reports/phase1_report.md` và `data/reports/corruption_report.md`.

---

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Lựa chọn phương án thực hiện bước Repair dữ liệu ở Pha 2.
- **Các phương án đã cân nhắc:**
  1. *Phương án A*: Viết script tự lọc và xóa các dòng bị lỗi trong file `papers_clean_corrupted.csv`.
  2. *Phương án B*: Đọc lại snapshot dữ liệu thô nguyên bản `data/raw/crossref_records.json` và thực thi lại luồng `build_clean_dataframe()`.
- **Phương án đã chọn:** Phương án B.
- **Lý do:** Đảm bảo nguyên tắc **Data Lineage** và **Reproducibility**. Việc sửa chữa trực tiếp trên file bị hỏng dễ bỏ sót lỗi hoặc vô tình can thiệp thủ công vào dữ liệu. Đọc lại từ `data/raw/` chứng minh rằng hệ thống có khả năng tự động khôi phục hoàn toàn (Auto-repair) khi có sự cố.
- **Bằng chứng quyết định phù hợp:** `repaired_metrics.json` cho thấy `retrieval_hit_rate` và `judge_score` phục hồi 100% về mức Baseline.

---

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi nguyên văn:** `uv run python script/run_phase1.py` chạy rất chậm và bị treo ở bước đồng bộ dependencies wheel.
- **Lệnh hoặc bước tái hiện:** `uv run python script/run_phase1.py` trên môi trường Windows PowerShell.
- **Nguyên nhân gốc:** `uv run` thực hiện bước kiểm tra và download/build lại cache các wheel nặng (`torch`, `scipy`, `onnxruntime`) do cache nằm trên ổ C: còn project nằm trên ổ D:.
- **Cách xử lý:** Gọi trực tiếp file thực thi Python trong venv đã được cài đặt đầy đủ: `.venv\Scripts\python.exe script/run_phase1.py`.
- **Cách xác minh sau khi sửa:** Tiến trình thực thi thành công chỉ trong vài giây.
- **Bài học kỹ thuật:** Nắm rõ cơ chế hoạt động của virtual environment và `uv` toolchain trên Windows khi làm việc liên ổ đĩa.

---

## 7. Hiểu biết về luồng end-to-end

**Câu trả lời:**

1. **Luồng dữ liệu từ Crossref đến Vector Index**: Dữ liệu thô JSON từ Crossref API được tải về ➔ Parse thành danh sách `PaperRecord` ➔ Lưu snapshot tại `data/raw/` ➔ Đưa qua `build_clean_dataframe()` để chuẩn hóa text, loại bỏ null/dup, tính `age_days` và tạo `text_for_embedding` ➔ Lưu `data/clean/papers_clean.csv` ➔ Đưa qua `MiniLM` đổi thành vector 384 chiều ➔ Nạp vào ChromaDB persistent collection.
2. **Evaluation set và Ground-truth document IDs**: `test_set.json` chứa các câu hỏi được sinh ra từ chính dữ liệu sạch kèm theo `ground_truth` (đáp án đúng) và `ground_truth_doc_ids` (ID tài liệu gốc). Khi RAG trả về Top-k tài liệu, ta so sánh ID tài liệu được lấy ra với `ground_truth_doc_ids` để tính `retrieval_hit_rate`.
3. **Quality checks vs Freshness monitoring**: Quality checks kiểm tra các quy tắc tính đúng đắn và toàn vẹn của dữ liệu dạng bảng (null, dup, độ dài text, marker lỗi). Freshness monitoring tập trung giám sát thuộc tính thời gian (`published`, `age_days`) để đảm bảo dữ liệu không bị lỗi thời (>180 ngày).
4. **Vì sao phải dùng cùng test set cho cả 3 trạng thái**: Để đảm bảo tính khách quan và công bằng. Chỉ khi bài thi giữ nguyên không đổi, sự sụt giảm hay phục hồi của điểm số mới phản ảnh đúng bản chất tác động của chất lượng dữ liệu.
5. **Dấu hiệu Repair thành công**: Khi `quality_report` chuyển từ `FAIL` sang `PASS` (16/16 checks), `freshness_status` là `PASS`, và `retrieval_hit_rate` phục hồi từ 0.8750 ➔ 1.0000 trên `corruption_report.md`.

---

## 8. Phân tích kết quả

### Metrics chính

| Metric/signal          |               Baseline |                Corrupted |               Repaired | Nhận xét của cá nhân                                                                       |
| :--------------------- | ---------------------: | -----------------------: | ---------------------: | :---------------------------------------------------------------------------------------------- |
| `retrieval_hit_rate` |       **1.0000** |         **0.8750** |       **1.0000** | Sụt giảm -12.5% do bị xóa bài báo mới và chèn nhiễu; khôi phục 100% sau repair      |
| `mean_token_f1`      |       **0.6667** |         **0.5475** |       **0.6667** | Tụt giảm do câu trả lời bị thiếu ngữ cảnh; phục hồi hoàn toàn sau repair           |
| `judge_accuracy`     |       **0.6667** |         **0.5417** |       **0.6667** | GPT-4o-mini đánh giá sai nhiều hơn khi context bị hỏng; phục hồi hoàn toàn           |
| `mean_judge_score`   |       **3.6667** |         **3.1667** |       **3.6667** | Điểm số trung bình giảm 0.5★ khi dữ liệu lỗi và khôi phục lại 3.6667★             |
| Quality checks         | **PASS (16/16)** |  **FAIL (7 Fail)** | **PASS (16/16)** | Phát hiện chính xác 7 quy tắc dữ liệu bị vi phạm khi corrupt và đạt 100% sau repair |
| Freshness status       |         **PASS** | **FAIL (2 Stale)** |         **PASS** | Phát hiện 2 bài báo bị đổi ngày về năm 2020 và khôi phục thành công              |

### Kết luận từ số liệu

1. **[Data corruption] ➔ [quality/freshness signal thay đổi] ➔ [agent metric thay đổi]**:
   Khi chèn noise, rỗng summary và làm cũ ngày xuất bản, `quality_report` lập tức báo `FAIL` (7 checks thất bại), dẫn đến `retrieval_hit_rate` sụt giảm từ 1.0000 xuống 0.8750 và `mean_judge_score` tụt từ 3.6667 xuống 3.1667.
2. **[Repair action] ➔ [quality/freshness signal phục hồi] ➔ [agent metric phục hồi hoặc chưa phục hồi]**:
   Khi chạy lại luồng cleaning từ `data/raw/crossref_records.json`, `quality_report` phục hồi về `PASS` (16/16 checks), kéo theo `retrieval_hit_rate` và `mean_judge_score` phục hồi 100% về mức Baseline ban đầu.

**Corruption ảnh hưởng rõ nhất:**
Việc **rỗng summary** và **chèn noise `[corrupted_noise]`** ảnh hưởng nghiêm trọng nhất vì làm thay đổi hoàn toàn vector embedding của tài liệu, khiến tầng vector search tìm nhầm tài liệu khác.

---

## 9. Điều học được và hướng cải thiện

### Ba điều quan trọng nhất

1. **Chất lượng dữ liệu quyết định chất lượng AI**: Dù mô hình LLM có mạnh đến đâu (GPT-4o-mini), dữ liệu nạp vào RAG bị lỗi thì câu trả lời vẫn bị sai lệch.
2. **Sức mạnh của Data Observability**: Việc xây dựng bộ cảnh báo Data Quality & Freshness tự động giúp phát hiện sự cố dữ liệu trước khi người dùng cuối nhận câu trả lời sai.
3. **Tầm quan trọng của Raw Data Lineage**: Việc bảo tồn dữ liệu thô nguyên bản (`data/raw/`) là chìa khóa để triển khai cơ chế tự động khôi phục dữ liệu (Auto-repair).

### Nếu có thêm thời gian

Tôi sẽ cài đặt thêm công cụ **Great Expectations (GX)** để tự động hóa việc validate dữ liệu theo schema và tích hợp thông báo qua Webhook khi phát hiện Data Pipeline bị lỗi.

---

## 10. Cam kết của thành viên

- [X] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [X] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [X] Mọi kết luận về kết quả đều có artifact hoặc metric để đối chiếu.
- [X] Tôi không ghi “đã chạy thành công” cho phần chưa được kiểm chứng.
- [X] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [X] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Thành viên 3 (User)
**Ngày xác nhận:** 2026-08-06
