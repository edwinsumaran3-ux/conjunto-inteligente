"""Deterministic COBie-style CSV parsing helpers for the digital-twin domain.

This parser intentionally handles CSV only. XLSX workbooks are handled by
cobie_xlsx.py. It does not claim full COBie schema certification.
"""
from __future__ import annotations

import csv
import io
from typing import Any


def parse_cobie_asset_csv(content: str) -> list[dict[str, Any]]:
    """Parse asset/component rows from a CSV string in a deterministic way.

    - Accepts UTF-8 text (a leading BOM is ignored).
    - Requires a header row and rejects duplicate non-empty column names.
    - Preserves header spelling and cell values as strings.
    - Skips fully empty rows and rejects rows with more cells than headers.
    """
    if not isinstance(content, str) or not content.strip():
        raise ValueError("COBie CSV is empty")
    stream = io.StringIO(content.lstrip("\ufeff"), newline="")
    reader = csv.DictReader(stream, skipinitialspace=True)
    headers = reader.fieldnames
    if not headers:
        raise ValueError("COBie CSV requires a header row")
    cleaned = [h.strip() if h else "" for h in headers]
    if any(not h for h in cleaned):
        raise ValueError("COBie CSV contains an empty column name")
    if len(set(cleaned)) != len(cleaned):
        raise ValueError("COBie CSV contains duplicate column names")
    reader.fieldnames = cleaned
    rows: list[dict[str, Any]] = []
    for line_number, row in enumerate(reader, start=2):
        if None in row and any(v not in (None, "") for v in row[None]):
            raise ValueError(f"COBie CSV row {line_number} has more cells than headers")
        row.pop(None, None)
        normalized = {k: (v.strip() if isinstance(v, str) else v) for k, v in row.items()}
        if not any(v not in (None, "") for v in normalized.values()):
            continue
        rows.append(normalized)
    return rows
