from __future__ import annotations

from pathlib import Path
from typing import Any
import pandas as pd

from core.utils import write_json


def corrupt_clean_dataframe(df: pd.DataFrame, output_log_path: str | Path) -> pd.DataFrame:
    """Giả lập các dạng lỗi dữ liệu có chủ đích (Controlled Data Corruption).

    Các biến đổi:
    1. Drop một số bản ghi mới nhất (Drop latest published records).
    2. Tóm tắt bị rỗng (Blank summary).
    3. Chèn từ nhiễu (Inject text noise).
    4. Cắt ngắn tiêu đề (Truncate title).
    5. Thay đổi ngày xuất bản thành quá cũ (Stale publication date).
    6. Thêm bản ghi trùng lặp (Add duplicate paper_id rows).
    7. Rebuild trường `text_for_embedding`.
    8. Xuất file log lịch sử biến đổi vào `output_log_path`.
    """
    corrupted_df = df.copy()
    logs: list[dict[str, Any]] = []

    if len(corrupted_df) < 5:
        write_json(Path(output_log_path), {"log": "Dataset too small for corruption", "actions": []})
        return corrupted_df

    # 1. Drop latest records (Xóa 2 bản ghi mới nhất)
    corrupted_df = corrupted_df.sort_values("published", ascending=False).reset_index(drop=True)
    dropped_rows = corrupted_df.head(2)
    dropped_ids = dropped_rows["paper_id"].tolist()
    corrupted_df = corrupted_df.iloc[2:].reset_index(drop=True)
    logs.append({
        "action": "drop_latest_records",
        "count": len(dropped_ids),
        "affected_paper_ids": dropped_ids,
        "description": "Removed 2 most recently published records."
    })

    # 2. Blank summary (Làm rỗng summary cho 2 dòng đầu tiên)
    blank_ids = corrupted_df.iloc[0:2]["paper_id"].tolist()
    corrupted_df.loc[0:1, "summary"] = ""
    corrupted_df.loc[0:1, "summary_chars"] = 0
    logs.append({
        "action": "blank_summary",
        "count": len(blank_ids),
        "affected_paper_ids": blank_ids,
        "description": "Set summary to empty string for 2 records."
    })

    # 3. Add text noise & corrupt markers (Thêm nhiễu vào summary của 2 dòng tiếp theo)
    noise_ids = corrupted_df.iloc[2:4]["paper_id"].tolist()
    for idx in range(2, min(4, len(corrupted_df))):
        orig_summary = corrupted_df.at[idx, "summary"]
        corrupted_df.at[idx, "summary"] = f"[corrupted_noise] lorem ipsum ### {orig_summary}"
        corrupted_df.at[idx, "summary_chars"] = len(corrupted_df.at[idx, "summary"])
    logs.append({
        "action": "inject_noise",
        "count": len(noise_ids),
        "affected_paper_ids": noise_ids,
        "description": "Injected [corrupted_noise] markers and lorem ipsum noise into summary."
    })

    # 4. Truncate title (Cắt ngắn title dưới 10 chars cho 1 dòng)
    if len(corrupted_df) > 4:
        trunc_id = corrupted_df.at[4, "paper_id"]
        corrupted_df.at[4, "title"] = "Short"
        logs.append({
            "action": "truncate_title",
            "count": 1,
            "affected_paper_ids": [trunc_id],
            "description": "Truncated title to 'Short' (under MIN_TITLE_CHARS)."
        })

    # 5. Stale publication date (Làm cũ ngày xuất bản thành > 180 ngày cho 2 dòng)
    stale_indices = [i for i in range(5, min(7, len(corrupted_df)))]
    stale_ids = corrupted_df.iloc[stale_indices]["paper_id"].tolist()
    for idx in stale_indices:
        corrupted_df.at[idx, "published"] = "2020-01-01"
        corrupted_df.at[idx, "age_days"] = 2400
    logs.append({
        "action": "stale_published_date",
        "count": len(stale_ids),
        "affected_paper_ids": stale_ids,
        "description": "Set published date to 2020-01-01 (age_days = 2400 > 180 days threshold)."
    })

    # 6. Add duplicate rows (Nhân bản 2 dòng cuối cùng)
    dup_rows = corrupted_df.tail(2).copy()
    dup_ids = dup_rows["paper_id"].tolist()
    corrupted_df = pd.concat([corrupted_df, dup_rows], ignore_index=True)
    logs.append({
        "action": "add_duplicates",
        "count": len(dup_ids),
        "affected_paper_ids": dup_ids,
        "description": "Duplicated 2 rows at the end of the dataframe."
    })

    # 7. Rebuild `text_for_embedding`
    corrupted_df["text_for_embedding"] = (
        "Title: " + corrupted_df["title"].astype(str) +
        " | Authors: " + corrupted_df["authors_joined"].astype(str) +
        " | Summary: " + corrupted_df["summary"].astype(str)
    )

    # 8. Write corruption log
    write_json(Path(output_log_path), {
        "corrupted_at": pd.Timestamp.now().isoformat(),
        "original_rows": len(df),
        "corrupted_rows": len(corrupted_df),
        "corruption_actions": logs
    })

    return corrupted_df
