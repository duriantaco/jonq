from __future__ import annotations

import json
import os
from jonq.constants import _Colors


def json_to_table(json_text, *, color=False, max_width=None):
    try:
        data = json.loads(json_text)
    except (json.JSONDecodeError, TypeError):
        return json_text

    if isinstance(data, dict):
        data = [data]

    if not isinstance(data, list) or not data:
        return json_text

    if not isinstance(data[0], dict):
        return json_text

    return render_table(data, color=color, max_width=max_width)


def _format_value(val):
    if val is None:
        return "null"
    if isinstance(val, bool):
        if val:
            return "true"
        return "false"
    if isinstance(val, (dict, list)):
        return json.dumps(val, ensure_ascii=False)
    return str(val)


def _truncate(text, width):
    if len(text) <= width:
        return text
    return text[: width - 1] + "\u2026"


def _collect_headers(rows):
    seen = {}
    for row in rows:
        for key in row:
            if key not in seen:
                seen[key] = True
    return list(seen.keys())


def _rows_to_strings(rows, headers):
    result = []
    for row in rows:
        cells = []
        for header in headers:
            val = row.get(header)
            cells.append(_format_value(val))
        result.append(cells)
    return result


def _compute_col_widths(headers, str_rows):
    widths = []
    for header in headers:
        widths.append(len(header))

    for row in str_rows:
        for col_index, cell in enumerate(row):
            if len(cell) > widths[col_index]:
                widths[col_index] = len(cell)

    return widths


def _shrink_columns_if_needed(col_widths, max_width):
    padding_per_col = 3  # " cell " + "|"
    total = sum(col_widths) + padding_per_col * len(col_widths) + 1

    if total <= max_width or len(col_widths) <= 1:
        return col_widths

    available = max_width - padding_per_col * len(col_widths) - 1
    avg_per_col = available // len(col_widths)
    min_col_width = 10

    shrunk = []
    for width in col_widths:
        cap = max(avg_per_col, min_col_width)
        shrunk.append(min(width, cap))
    return shrunk


def _build_row_line(cells, col_widths):
    parts = []
    for cell, width in zip(cells, col_widths):
        padded = f" {_truncate(cell, width):<{width}} "
        parts.append(padded)
    return "|".join(parts)


def render_table(rows, *, color=False, max_width=None):
    if not rows:
        return ""

    headers = _collect_headers(rows)
    if not headers:
        return ""

    if max_width is None:
        try:
            max_width = os.get_terminal_size().columns
        except (OSError, ValueError):
            max_width = 120

    str_rows = _rows_to_strings(rows, headers)
    col_widths = _compute_col_widths(headers, str_rows)
    col_widths = _shrink_columns_if_needed(col_widths, max_width)

    colors = _Colors(color)
    lines = []

    # header
    header_line = _build_row_line(headers, col_widths)
    lines.append(f"{colors.BOLD}{colors.CYAN}{header_line}{colors.NC}")

    # separator
    sep_parts = []
    for width in col_widths:
        sep_parts.append("-" * (width + 2))
    lines.append("|".join(sep_parts))

    # data rows
    for row in str_rows:
        lines.append(_build_row_line(row, col_widths))

    return "\n".join(lines)
