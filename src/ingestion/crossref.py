from __future__ import annotations

from dataclasses import dataclass
from dataclasses import asdict
from datetime import datetime
from html import unescape
import re
from pathlib import Path
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from core.config import Settings
from core.utils import normalize_whitespace, read_json, write_json


@dataclass(frozen=True)
class PaperRecord:
    paper_id: str
    title: str
    summary: str
    authors: list[str]
    categories: list[str]
    primary_category: str
    published: str
    updated: str
    abs_url: str
    pdf_url: str
    comment: str


def parse_crossref_payload(payload: dict) -> list[PaperRecord]:
    """TODO(student): parse Crossref payload thanh list PaperRecord.

    Pseudo-code:
    1. Duyet `payload["message"]["items"]`.
    2. Lay DOI, title, abstract, authors, subject, dates, URLs.
    3. Chuan hoa text va bo record khong hop le.
    4. Tra ve list `PaperRecord`.
    """
    items = payload.get("message", {}).get("items", [])
    if not isinstance(items, list):
        raise ValueError("Invalid Crossref response: message.items must be a list.")

    records: list[PaperRecord] = []
    for item in items:
        if not isinstance(item, dict):
            continue

        doi = _text(item.get("DOI")).lower()
        title = _first_text(item.get("title"))
        if not doi or not title:
            continue

        summary = _strip_markup(_text(item.get("abstract")))
        authors = _parse_authors(item.get("author"))
        categories = _unique_texts(item.get("subject"))
        published = _extract_date(item, ("published-print", "published-online", "published", "issued", "created"))
        updated = _extract_date(item, ("indexed", "deposited", "created"))
        abs_url = _text(item.get("URL")) or f"https://doi.org/{doi}"
        pdf_url = _extract_pdf_url(item)

        records.append(
            PaperRecord(
                paper_id=doi,
                title=title,
                summary=summary,
                authors=authors,
                categories=categories,
                primary_category=categories[0] if categories else "",
                published=published,
                updated=updated,
                abs_url=abs_url,
                pdf_url=pdf_url,
                comment=_text(item.get("publisher")),
            )
        )
    return records


def fetch_source_records(settings: Settings) -> list[PaperRecord]:
    """TODO(student): goi source API, luu raw response, parse thanh records.

    Pseudo-code:
    1. Tao params tu `settings.source_query`, `settings.source_filter`, `settings.max_results`.
    2. Goi API voi retry cho cac status code nhu 429/503.
    3. Luu raw response vao `settings.paths.raw_api_response`.
    4. Parse payload bang `parse_crossref_payload`.
    5. Luu records vao `settings.paths.raw_records_json`.
    """
    retry = Retry(
        total=4,
        connect=4,
        read=4,
        status=4,
        backoff_factor=1.0,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET"}),
        respect_retry_after_header=True,
    )
    session = requests.Session()
    session.mount("https://", HTTPAdapter(max_retries=retry))
    params = {
        "query": settings.source_query,
        "filter": settings.source_filter,
        "rows": settings.max_results,
        "select": "DOI,title,abstract,author,subject,published,published-print,published-online,issued,created,indexed,deposited,URL,link,publisher",
    }
    headers = {"User-Agent": "day10-data-observability-lab/0.1 (Crossref educational client)"}

    response = session.get("https://api.crossref.org/works", params=params, headers=headers, timeout=(10, 45))
    response.raise_for_status()
    payload = response.json()
    write_json(settings.paths.raw_api_response, payload)

    records = parse_crossref_payload(payload)
    write_json(settings.paths.raw_records_json, [asdict(record) for record in records])
    return records


def load_raw_records(path: Path) -> list[PaperRecord]:
    """TODO(student): doc JSON snapshot va map thanh `PaperRecord`."""
    payload = read_json(path)
    if isinstance(payload, dict):
        payload = payload.get("records", [])
    if not isinstance(payload, list):
        raise ValueError(f"Invalid raw records snapshot at {path}: expected a JSON list.")

    records: list[PaperRecord] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        records.append(
            PaperRecord(
                paper_id=_text(item.get("paper_id")),
                title=_text(item.get("title")),
                summary=_text(item.get("summary")),
                authors=_unique_texts(item.get("authors")),
                categories=_unique_texts(item.get("categories")),
                primary_category=_text(item.get("primary_category")),
                published=_text(item.get("published")),
                updated=_text(item.get("updated")),
                abs_url=_text(item.get("abs_url")),
                pdf_url=_text(item.get("pdf_url")),
                comment=_text(item.get("comment")),
            )
        )
    return records


def _text(value: Any) -> str:
    if value is None:
        return ""
    return normalize_whitespace(unescape(str(value)))


def _first_text(value: Any) -> str:
    if isinstance(value, list):
        return _text(value[0]) if value else ""
    return _text(value)


def _strip_markup(value: str) -> str:
    # Crossref abstracts commonly contain JATS/XML tags.
    return normalize_whitespace(unescape(re.sub(r"<[^>]+>", " ", value)))


def _unique_texts(value: Any) -> list[str]:
    values = value if isinstance(value, list) else ([] if value is None else [value])
    result: list[str] = []
    seen: set[str] = set()
    for item in values:
        text = _text(item)
        key = text.casefold()
        if text and key not in seen:
            seen.add(key)
            result.append(text)
    return result


def _parse_authors(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    authors: list[str] = []
    for author in value:
        if not isinstance(author, dict):
            continue
        name = normalize_whitespace(" ".join(filter(None, (_text(author.get("given")), _text(author.get("family"))))))
        name = name or _text(author.get("name"))
        if name and name.casefold() not in {item.casefold() for item in authors}:
            authors.append(name)
    return authors


def _extract_date(item: dict[str, Any], fields: tuple[str, ...]) -> str:
    for field in fields:
        date_value = item.get(field)
        if not isinstance(date_value, dict):
            continue
        parts_list = date_value.get("date-parts")
        if isinstance(parts_list, list) and parts_list and isinstance(parts_list[0], list):
            parts = parts_list[0]
            try:
                year = int(parts[0])
                month = int(parts[1]) if len(parts) > 1 else 1
                day = int(parts[2]) if len(parts) > 2 else 1
                return datetime(year, month, day).date().isoformat()
            except (TypeError, ValueError, IndexError):
                continue
    return ""


def _extract_pdf_url(item: dict[str, Any]) -> str:
    links = item.get("link")
    if not isinstance(links, list):
        return ""
    for link in links:
        if not isinstance(link, dict):
            continue
        content_type = _text(link.get("content-type")).lower()
        url = _text(link.get("URL"))
        if url and ("pdf" in content_type or url.lower().endswith(".pdf")):
            return url
    return ""
