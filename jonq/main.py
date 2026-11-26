from __future__ import annotations

import argparse
import sys
import os
import json
import glob as globmod
import logging
import asyncio
import time
import subprocess
import shlex
from shutil import copyfileobj
from collections import OrderedDict
from contextlib import ExitStack, contextmanager, nullcontext
from dataclasses import asdict
from typing import TextIO

from jonq.api import _iter_stream_results, compile_query, execute_async
from jonq.ast import PathType
from jonq.error_handler import _shell_query_argument, handle_error_with_context
from jonq.parser import parse_path
from jonq.workbench import (
    build_profile,
    build_profile_from_data,
    compare_profiles,
    format_check_result,
    format_diff,
    format_profile,
    load_config,
    normalize_list,
    run_profile_check,
)
from jonq.constants import (
    _Colors,
    VERSION,
    USER_AGENT,
    URL_FETCH_TIMEOUT,
    WATCH_POLL_INTERVAL,
    WATCH_RETRY_INTERVAL,
    NDJSON_SNIFF_LINES,
    NDJSON_MIN_VALID,
    SCHEMA_SAMPLE_TRUNCATE,
    SCHEMA_PATH_SAMPLE_ROWS,
    SCHEMA_PATH_MAX_DEPTH,
    SCHEMA_PATH_PREVIEW_ITEMS,
)

_WORKBENCH_COMMANDS = {"profile", "diff", "check", "run", "triage", "connections"}
_QUERY_STRUCTURAL_WORDS = {
    "as", "distinct", "from", "group", "having", "if", "limit", "order", "select",
    "sort", "where", "case", "true", "false", "null",
}


def _looks_like_ndjson(path: str) -> bool:
    try:
        with open(path, "r", encoding="utf-8") as f:
            first = f.read(1).lstrip()
            if first in ("[", "{", ""):
                if first == "[":
                    return False
                if first == "":
                    return False
            f.seek(0)
            valid = 0
            for i, raw in enumerate(f):
                line = raw.strip()
                if not line:
                    continue
                try:
                    json.loads(line)
                    valid += 1
                except json.JSONDecodeError:
                    return False
                if i >= NDJSON_SNIFF_LINES - 1:
                    break
            return valid >= NDJSON_MIN_VALID
    except OSError:
        return False


def _slurp_ndjson(json_file, *, limit: int | None = None):
    stream = nullcontext(sys.stdin) if json_file == "-" else open(json_file, encoding="utf-8")
    with stream as src:
        parts = []
        for line_no, raw in enumerate(src, 1):
            line = raw.strip()
            if line:
                try:
                    json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ValueError(f"Invalid NDJSON at line {line_no}: {exc.msg}") from exc
                parts.append(line)
                if limit is not None and len(parts) >= limit:
                    break
        return "[" + ",".join(parts) + "]"


@contextmanager
def _prepare_query_input(
    source: str, *, ndjson: bool = False, streaming: bool = False, inspect_only: bool = False
):
    with ExitStack() as cleanup:
        json_file = source
        if source == "-":
            if streaming:
                json_file = _write_temporary_input(sys.stdin, cleanup)
            else:
                data = sys.stdin.read()
                if not data.strip():
                    raise ValueError("No JSON data on stdin.")
                json_file = _write_temporary_input(data, cleanup)
        elif source.startswith(("http://", "https://")):
            json_file = _fetch_url(source)
            cleanup.callback(os.unlink, json_file)
        elif not os.path.exists(source) and any(char in source for char in "*?"):
            json_file = _concat_glob(source)
            cleanup.callback(os.unlink, json_file)

        if os.path.isfile(json_file) and (
            ndjson or source.lower().endswith((".ndjson", ".jsonl"))
            or _looks_like_ndjson(json_file)
        ):
            if streaming:
                raise ValueError("NDJSON with --stream is not supported. Use --follow for row-wise pipes.")
            sample_limit = SCHEMA_PATH_SAMPLE_ROWS if inspect_only else None
            json_file = _write_temporary_input(_slurp_ndjson(json_file, limit=sample_limit), cleanup)
        yield json_file


def _write_temporary_input(contents: str | TextIO, cleanup: ExitStack) -> str:
    import tempfile

    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", suffix=".json", delete=False) as fp:
        cleanup.callback(os.unlink, fp.name)
        if isinstance(contents, str):
            fp.write(contents)
        else:
            copyfileobj(contents, fp)
            if not fp.tell():
                raise ValueError("No JSON data on stdin.")
        return fp.name


def _concat_glob(pattern: str) -> str:
    import tempfile

    paths = sorted(globmod.glob(pattern))
    if not paths:
        raise FileNotFoundError(f"No files matched pattern: {pattern}")
    all_items = []
    for p in paths:
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            all_items.extend(data)
        else:
            all_items.append(data)
    fd, tmp_path = tempfile.mkstemp(prefix="jonq_glob_", suffix=".json")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(all_items, f, separators=(",", ":"))
    return tmp_path


def _fetch_url(url: str) -> str:
    import tempfile
    import urllib.request
    import urllib.error

    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=URL_FETCH_TIMEOUT) as resp:
            body = resp.read()
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Failed to fetch URL: {exc}") from exc
    fd, tmp_path = tempfile.mkstemp(prefix="jonq_url_", suffix=".json")
    with os.fdopen(fd, "wb") as f:
        f.write(body)
    return tmp_path


def _type_label(v) -> str:
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "bool"
    if isinstance(v, int):
        return "int"
    if isinstance(v, float):
        return "float"
    if isinstance(v, str):
        return "str"
    if isinstance(v, list):
        return f"array[{len(v)}]"
    if isinstance(v, dict):
        return f"object{{{len(v)}}}"
    return type(v).__name__


def _sample_json_for_schema(json_file: str):
    try:
        with open(json_file, "r", encoding="utf-8") as f:
            first = " "
            while first.isspace():
                first = f.read(1)
                if first == "":
                    return "empty", None
    except OSError as exc:
        print(f"Error reading {json_file}: {exc}", file=sys.stderr)
        sys.exit(1)

    if first == "[":
        try:
            proc = subprocess.Popen(
                ["jq", "-c", ".[]", json_file],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            samples = []
            reached_sample_limit = False
            for i, line in enumerate(proc.stdout):
                if i >= SCHEMA_PATH_SAMPLE_ROWS:
                    reached_sample_limit = True
                    break
                line = line.strip()
                if line:
                    samples.append(json.loads(line))
            if reached_sample_limit and proc.poll() is None:
                proc.terminate()
            stderr = proc.stderr.read().strip()
            proc.wait(timeout=1)
            if proc.returncode not in (0, -15):
                raise RuntimeError(stderr or "jq failed while sampling array")
            return "array", samples
        except Exception:
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except (OSError, json.JSONDecodeError) as exc:
                print(f"Error reading {json_file}: {exc}", file=sys.stderr)
                sys.exit(1)
            return "array", data[:SCHEMA_PATH_SAMPLE_ROWS] if isinstance(data, list) else []

    try:
        with open(json_file, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Error reading {json_file}: {exc}", file=sys.stderr)
        sys.exit(1)

    if isinstance(data, dict):
        return "object", data
    return "scalar", data


def _array_type_label(values: list) -> str:
    if not values:
        return "array[empty]"
    elem_types = []
    for value in values[:SCHEMA_PATH_PREVIEW_ITEMS]:
        t = _type_label(value)
        if t not in elem_types:
            elem_types.append(t)
    return f"array[{' | '.join(elem_types)}]"


def _preview_value(value) -> str:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, list) and value and all(
        isinstance(v, (str, int, float, bool)) or v is None
        for v in value[:SCHEMA_PATH_PREVIEW_ITEMS]
    ):
        preview_items = value[:SCHEMA_PATH_PREVIEW_ITEMS]
        preview = json.dumps(preview_items, ensure_ascii=False)
        if len(value) > SCHEMA_PATH_PREVIEW_ITEMS:
            preview = preview[:-1] + ", ...]"
        return preview
    return ""


def _add_path_record(path_map, path: str, value) -> None:
    if not path:
        return

    if isinstance(value, list):
        type_label = _array_type_label(value)
    elif isinstance(value, dict):
        type_label = "object"
    else:
        type_label = _type_label(value)

    entry = path_map.setdefault(path, {"types": [], "preview": ""})
    if type_label not in entry["types"]:
        entry["types"].append(type_label)

    preview = _preview_value(value)
    if preview and not entry["preview"]:
        entry["preview"] = preview


def _schema_key(key: str) -> str:
    if key.isascii() and key.isidentifier() and key.lower() not in _QUERY_STRUCTURAL_WORDS:
        return key
    return json.dumps(key, ensure_ascii=False)


def _walk_schema_paths(value, path: str, path_map, depth: int) -> None:
    if depth > SCHEMA_PATH_MAX_DEPTH:
        return

    if isinstance(value, dict):
        _add_path_record(path_map, path, value)
        for key, child in value.items():
            segment = _schema_key(key)
            child_path = f"{path}.{segment}" if path else segment
            _walk_schema_paths(child, child_path, path_map, depth + 1)
        return

    if isinstance(value, list):
        _add_path_record(path_map, path, value)
        item_path = f"{path}[]" if path else ""
        for child in value[:SCHEMA_PATH_PREVIEW_ITEMS]:
            if isinstance(child, (dict, list)):
                _walk_schema_paths(child, item_path, path_map, depth + 1)
        return

    _add_path_record(path_map, path, value)


def _collect_schema_paths(sample):
    paths = OrderedDict()
    if isinstance(sample, list):
        for item in sample:
            _walk_schema_paths(item, "", paths, 0)
    elif isinstance(sample, dict):
        _walk_schema_paths(sample, "", paths, 0)
    return paths


def _display_schema_type(type_label: str) -> str:
    if type_label.startswith("array[") and type_label.endswith("]"):
        inner = type_label[len("array[") : -1]
        if inner == "empty":
            return "array[empty]"
        parts = [part.strip() for part in inner.split("|")]
        return "array[" + " | ".join(_display_schema_type(part) for part in parts) + "]"
    if type_label.startswith("object"):
        return "object"
    return {
        "str": "string",
        "int": "number",
        "float": "number",
        "bool": "boolean",
    }.get(type_label, type_label)


def _format_schema_types(types: list[str]) -> str:
    labels = []
    for type_label in types:
        display = _display_schema_type(type_label)
        if display not in labels:
            labels.append(display)
    return " | ".join(labels)


def _root_summary(root_kind: str, sample) -> str:
    if root_kind == "empty":
        return "empty"
    if root_kind == "scalar":
        return f"scalar {_display_schema_type(_type_label(sample))}"
    if root_kind == "object":
        return "object"
    if root_kind == "array":
        sample_count = len(sample)
        if not sample:
            item_summary = "empty"
        else:
            item_types = []
            for item in sample:
                item_type = _display_schema_type(_type_label(item))
                if item_type not in item_types:
                    item_types.append(item_type)
            item_summary = " | ".join(item_types)
            if item_summary == "object":
                item_summary = "objects"
        suffix = f"sampled {sample_count} item{'s' if sample_count != 1 else ''}"
        return f"array of {item_summary} ({suffix})"
    return root_kind


def _is_scalar_schema_info(info) -> bool:
    return all(
        not type_label.startswith("object") and not type_label.startswith("array[")
        for type_label in info["types"]
    )


def _path_leaf(path: str) -> str:
    return parse_path(path).elements[-1].value.lower()


def _schema_row_fields(path_map, *, root_array: bool = False):
    scopes = {}
    for path, info in path_map.items():
        if not _is_scalar_schema_info(info):
            continue
        elements = parse_path(path).elements
        array_positions = [i for i, element in enumerate(elements) if element.type == PathType.ARRAY]
        if not array_positions:
            scopes.setdefault("", {})[path] = info
            continue

        last_array = array_positions[-1]
        scope_parts = ["[]"] if root_array else []
        for index, element in enumerate(elements[:last_array + 1]):
            name = _schema_key(element.value) if element.value else ""
            if element.type == PathType.ARRAY and (index != last_array or len(array_positions) > 1):
                name += "[]"
            scope_parts.append(name)
        scope = ".".join(scope_parts)
        field = ".".join(_schema_key(element.value) for element in elements[last_array + 1:])
        if scope and field:
            scopes.setdefault(scope, {})[field] = info
    return scopes


def _pick_select_fields(paths: list[str], limit: int = 3) -> list[str]:
    preferred_names = (
        "id",
        "name",
        "title",
        "email",
        "status",
        "type",
        "level",
        "message",
        "city",
    )
    preferred = [path for path in paths if _path_leaf(path) in preferred_names]
    selected = []
    for path in preferred + paths:
        if path not in selected:
            selected.append(path)
        if len(selected) >= limit:
            break
    return selected


def _format_suggested_command(source: str, query: str, *options: str) -> str:
    parts = ["jonq", shlex.quote(source), _shell_query_argument(query), *options]
    return " ".join(parts)


def _query_for_mixed_array(query: str, selected: list[str], mixed_array: bool) -> str:
    if not mixed_array or not selected:
        return query
    if '"' in selected[0]:
        return query
    return f"{query} where {selected[0]} is not null"


def _suggest_queries(
    source: str, path_map, *, root_kind: str = "array", mixed_array: bool = False
) -> list[str]:
    scopes = _schema_row_fields(path_map, root_array=root_kind == "array")
    if not scopes:
        return []

    ordered_scopes = sorted(scopes, key=bool, reverse=root_kind == "object")
    suggestions = []
    for scope in ordered_scopes[:3]:
        selected = _pick_select_fields(list(scopes[scope]))
        query = f"select {', '.join(selected)}"
        if scope:
            query += f" from {scope}"
        query = _query_for_mixed_array(query, selected, mixed_array and not scope)
        suggestions.append(_format_suggested_command(source, query, "-t"))

    primary_scope = ordered_scopes[0]
    from_clause = f" from {primary_scope}" if primary_scope else ""
    primary_mixed = mixed_array and not primary_scope
    primary_fields = scopes[primary_scope]
    selected = _pick_select_fields(list(primary_fields))
    raw_candidates = ("name", "title", "email", "message", "id")
    raw_field = next(
        (path for leaf in raw_candidates for path in primary_fields if _path_leaf(path) == leaf),
        next(iter(primary_fields)),
    )
    raw_query = _query_for_mixed_array(f"select {raw_field}{from_clause}", [raw_field], primary_mixed)
    suggestions.append(_format_suggested_command(source, raw_query, "-r"))

    bool_field = next((path for path, info in primary_fields.items() if info["types"] == ["bool"]), None)
    if bool_field:
        value = primary_fields[bool_field]["preview"]
        query = f"select {', '.join(selected)}{from_clause} where {bool_field} = {value}"
        suggestions.append(_format_suggested_command(source, query, "-t"))
    else:
        groupable_names = {"status", "type", "level", "city", "country", "category", "kind", "state", "plan"}
        group_field = next(
            (path for path, info in primary_fields.items() if _path_leaf(path) in groupable_names and "str" in info["types"]),
            None,
        )
        if group_field:
            query = f"select {group_field}, count(*) as count{from_clause} group by {group_field}"
            suggestions.append(_format_suggested_command(source, query, "-t"))

    deduped = []
    for suggestion in suggestions:
        if suggestion not in deduped:
            deduped.append(suggestion)
    return deduped[:3]


def _sample_for_display(sample: list):
    if not sample:
        return []
    for item in sample:
        if isinstance(item, (dict, list)):
            return item
    return sample[0]


def _print_schema(json_file: str, display_name: str | None = None, *, no_color: bool = False) -> None:
    c = _Colors(_terminal_color_enabled(no_color))
    display_name = display_name or json_file

    root_kind, sample = _sample_json_for_schema(json_file)

    if root_kind == "empty":
        print(f"{c.BOLD}{display_name}{c.NC}")
        print(f"{c.BOLD}Root:{c.NC} {c.DIM}{_root_summary(root_kind, sample)}{c.NC}")
        return

    if root_kind == "scalar":
        print(f"{c.BOLD}{display_name}{c.NC}")
        print(f"{c.BOLD}Root:{c.NC} {c.DIM}{_root_summary(root_kind, sample)}{c.NC}")
        print(f"  {sample}")
        return

    print(f"{c.BOLD}{display_name}{c.NC}")
    print(f"{c.BOLD}Root:{c.NC} {c.DIM}{_root_summary(root_kind, sample)}{c.NC}")

    mixed_array = False
    if root_kind == "array":
        sample_for_display = _sample_for_display(sample)
        mixed_array = any(not isinstance(item, dict) for item in sample)
    else:
        sample_for_display = sample

    path_map = _collect_schema_paths(sample)
    if not path_map:
        print("  No object-like paths found in sample.")
        return

    print(f"\n{c.BOLD}Fields:{c.NC}")
    max_key = max((len(k) for k in path_map), default=0)
    max_type = max(
        (len(_format_schema_types(info["types"])) for info in path_map.values()),
        default=0,
    )
    for key, info in path_map.items():
        type_label = _format_schema_types(info["types"])
        preview = f"  {c.DIM}sample: {info['preview']}{c.NC}" if info["preview"] else ""
        print(
            f"  {c.GREEN}{key:<{max_key}}{c.NC}  {c.YELLOW}{type_label:<{max_type}}{c.NC}{preview}"
        )

    print(f"\n{c.BOLD}Sample:{c.NC}")
    sample_json = json.dumps(sample_for_display, indent=2, ensure_ascii=False)
    sample_text = sample_json[:SCHEMA_SAMPLE_TRUNCATE]
    for line in sample_text.splitlines():
        print(f"  {line}")
    if len(sample_json) > SCHEMA_SAMPLE_TRUNCATE:
        print("  ...")

    suggestions = _suggest_queries(display_name, path_map, root_kind=root_kind, mixed_array=mixed_array)
    if suggestions:
        print(f"\n{c.BOLD}Suggested queries:{c.NC}")
        for suggestion in suggestions:
            print(f"  {c.DIM}{suggestion}{c.NC}")


def _colorize_json(s: str) -> str:
    import re as _re

    c = _Colors(enabled=True)
    s = _re.sub(r'"([^"]+)"(\s*:)', f'{c.CYAN}"\\1"{c.NC}\\2', s)
    s = _re.sub(r':\s*"([^"]*)"', lambda m: f': {c.GREEN}"{m.group(1)}"{c.NC}', s)
    s = _re.sub(
        r"(?<=[\s,\[:])([-]?\d+\.?\d*(?:[eE][+-]?\d+)?)(?=[\s,\]\}])",
        f"{c.YELLOW}\\1{c.NC}",
        s,
    )
    s = _re.sub(r"\b(null)\b", f"{c.DIM}\\1{c.NC}", s)
    s = _re.sub(r"\b(true|false)\b", f"{c.MAGENTA}\\1{c.NC}", s)
    return s


def _pretty_json_string(s):
    try:
        obj = json.loads(s)
        return json.dumps(obj, ensure_ascii=False, indent=2)
    except (json.JSONDecodeError, TypeError):
        return s


def _setup_repl_readline(json_file: str) -> None:
    """Set up readline with history and tab completion for field names."""
    try:
        import readline
    except ImportError:
        return

    history_file = os.path.expanduser("~/.jonq_history")
    try:
        readline.read_history_file(history_file)
        readline.set_history_length(500)
    except (FileNotFoundError, OSError):
        pass

    import atexit
    def save_history():
        try:
            readline.write_history_file(history_file)
        except OSError:
            pass

    atexit.register(save_history)

    # Build completion words from schema
    completions = _build_repl_completions(json_file)

    def completer(text, state):
        matches = [w for w in completions if w.startswith(text)]
        return matches[state] if state < len(matches) else None

    readline.set_completer(completer)
    readline.set_completer_delims(" \t\n,")
    readline.parse_and_bind("tab: complete")


def _build_repl_completions(json_file: str) -> list[str]:
    """Build completion list from JSON schema + keywords."""
    keywords = [
        "select", "if", "where", "from", "group", "by", "having", "sort", "asc", "desc",
        "limit", "distinct", "and", "or", "not", "in", "like", "between",
        "contains", "as", "case", "when", "then", "else", "end", "is", "null",
        "coalesce",
        "count", "sum", "avg", "min", "max",
        "upper", "lower", "length", "round", "abs", "ceil", "floor",
        "int", "float", "str", "type", "keys", "values", "trim",
        "todate", "fromdate", "date", "tojson", "fromjson",
    ]

    field_names = []
    try:
        with open(json_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list) and data:
            sample = data[0]
        elif isinstance(data, dict):
            sample = data
        else:
            sample = None
        if isinstance(sample, dict):
            paths = _collect_schema_paths([sample] if isinstance(data, list) else sample)
            field_names = list(paths.keys())
    except Exception:
        pass

    return keywords + field_names


async def _run_repl(json_file: str, options: dict, source_label: str) -> None:
    c = _Colors(_terminal_color_enabled(options["no_color"]))

    _setup_repl_readline(json_file)

    print(f"{c.BOLD}jonq interactive mode{c.NC} — querying {c.BOLD}{source_label}{c.NC}")
    print(f"{c.DIM}Type a query, or 'quit' to exit. Tab completes field names.{c.NC}")
    print(f"{c.DIM}Example: select name, age if age > 30{c.NC}\n")

    while True:
        try:
            query = input(f"{c.BOLD}jonq>{c.NC} ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not query or query.lower() in ("quit", "exit", "q"):
            break
        try:
            result = await _run_query(json_file, query, options, source_label=source_label)
            _write_query_output(result, options)
        except SystemExit:
            pass
        except Exception as exc:
            print(f"Error: {exc}", file=sys.stderr)


def _explain_query(compiled, *, color: bool = False) -> str:
    c = _Colors(color)
    parts = []
    parts.append(f"{c.BOLD}Query:{c.NC} {compiled.query}")
    parts.append("")

    parts.append(f"{c.BOLD}Parsed:{c.NC}")
    field_strs = []
    for tup in compiled.fields:
        ftype = tup[0]
        if ftype == "field":
            _, field, alias = tup
            field_strs.append(f"  {field}" + (f" as {alias}" if alias != field.split('.')[-1] else ""))
        elif ftype == "aggregation":
            _, func, param, alias = tup
            field_strs.append(f"  {func}({param}) as {alias}")
        elif ftype == "function":
            _, func, param, alias = tup
            field_strs.append(f"  {func}({param}) as {alias}")
        elif ftype == "expression":
            _, expr, alias = tup
            field_strs.append(f"  {expr} as {alias}")
        elif ftype == "count_distinct":
            _, param, alias = tup
            field_strs.append(f"  count(distinct {param}) as {alias}")
    parts.append(f"  {c.CYAN}Fields:{c.NC}")
    for s in field_strs:
        parts.append(f"  {s}")

    if compiled.from_path:
        parts.append(f"  {c.CYAN}From:{c.NC} {compiled.from_path}")
    if compiled.condition:
        parts.append(f"  {c.CYAN}Condition:{c.NC} {compiled.condition}")
    if compiled.group_by:
        parts.append(f"  {c.CYAN}Group by:{c.NC} {', '.join(compiled.group_by)}")
    if compiled.having:
        parts.append(f"  {c.CYAN}Having:{c.NC} {compiled.having}")
    if compiled.order_by:
        parts.append(f"  {c.CYAN}Sort:{c.NC} {compiled.order_by} {compiled.sort_direction}")
    if compiled.limit:
        parts.append(f"  {c.CYAN}Limit:{c.NC} {compiled.limit}")
    if compiled.distinct:
        parts.append(f"  {c.CYAN}Distinct:{c.NC} yes")

    parts.append("")
    parts.append(f"{c.BOLD}Generated jq:{c.NC}")
    parts.append(f"  {c.GREEN}{compiled.jq_filter}{c.NC}")
    return "\n".join(parts)


def _print_timing(t_start: float, t_parse: float, t_exec: float, t_format: float) -> None:
    parse_ms = (t_parse - t_start) * 1000
    exec_ms = (t_exec - t_parse) * 1000
    fmt_ms = (t_format - t_exec) * 1000
    total_ms = (t_format - t_start) * 1000
    print(
        f"parse: {parse_ms:.1f}ms | execute: {exec_ms:.1f}ms | format: {fmt_ms:.1f}ms | total: {total_ms:.1f}ms",
        file=sys.stderr,
    )


def _json_to_yaml(json_text: str) -> str:
    try:
        import yaml
        data = json.loads(json_text)
        return yaml.dump(data, default_flow_style=False, allow_unicode=True, sort_keys=False).rstrip()
    except ImportError:
        return _json_to_yaml_simple(json_text)
    except (json.JSONDecodeError, TypeError):
        return json_text


def _json_to_raw(json_text: str, *, terminate_lines: bool = False) -> str:
    try:
        data = json.loads(json_text)
    except (json.JSONDecodeError, TypeError):
        return json_text

    rows = data if isinstance(data, list) else [data]
    if terminate_lines:
        return "".join(f"{_raw_line(item)}\n" for item in rows)
    return "\n".join(_raw_line(item) for item in rows)


def _raw_line(value) -> str:
    if isinstance(value, dict) and len(value) == 1:
        value = next(iter(value.values()))

    if isinstance(value, str):
        return value
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return str(value)


def _json_to_yaml_simple(json_text: str) -> str:
    try:
        data = json.loads(json_text)
    except (json.JSONDecodeError, TypeError):
        return json_text

    lines = []
    _yaml_dump(data, lines, indent=0)
    return "\n".join(lines)


def _yaml_dump(obj, lines: list, indent: int) -> None:
    prefix = "  " * indent
    if isinstance(obj, dict):
        for key, val in obj.items():
            if isinstance(val, (dict, list)):
                lines.append(f"{prefix}{key}:")
                _yaml_dump(val, lines, indent + 1)
            else:
                lines.append(f"{prefix}{key}: {_yaml_scalar(val)}")
    elif isinstance(obj, list):
        for item in obj:
            if isinstance(item, dict):
                first = True
                for key, val in item.items():
                    marker = "- " if first else "  "
                    first = False
                    if isinstance(val, (dict, list)):
                        lines.append(f"{prefix}{marker}{key}:")
                        _yaml_dump(val, lines, indent + 2)
                    else:
                        lines.append(f"{prefix}{marker}{key}: {_yaml_scalar(val)}")
            else:
                lines.append(f"{prefix}- {_yaml_scalar(item)}")
    else:
        lines.append(f"{prefix}{_yaml_scalar(obj)}")


def _yaml_scalar(val) -> str:
    if val is None:
        return "null"
    if isinstance(val, bool):
        return "true" if val else "false"
    if isinstance(val, str):
        if any(c in val for c in ":#{}[]|>&*!%@`"):
            return f'"{val}"'
        return val
    return str(val)


def _generate_completions(shell: str) -> str:
    if shell == "bash":
        return '''# jonq bash completion
# Add to ~/.bashrc: eval "$(jonq --completions bash)"
_jonq_completions() {
    local cur="${COMP_WORDS[COMP_CWORD]}"
    local opts="-i -f -t -r -s -n -o -p -w --format --table --raw --raw-output --stream --ndjson --limit --out --jq --explain --time --pretty --watch --follow --no-color --version --help --completions"
    local commands="profile diff check run triage connections"
    local keywords="select if where from group by having sort asc desc limit distinct and or not in like between contains as case when then else end is null coalesce count sum avg min max upper lower length round abs ceil floor int float str type keys values trim todate fromdate date tojson fromjson"

    if [[ "${cur}" == -* ]]; then
        COMPREPLY=($(compgen -W "${opts}" -- "${cur}"))
    elif [[ "${COMP_CWORD}" == 1 ]]; then
        COMPREPLY=($(compgen -W "${commands}" -- "${cur}") $(compgen -f -X '!*.json' -- "${cur}") $(compgen -f -X '!*.jsonl' -- "${cur}"))
    else
        COMPREPLY=($(compgen -W "${keywords}" -- "${cur}"))
    fi
}
complete -F _jonq_completions jonq'''
    elif shell == "zsh":
        return '''# jonq zsh completion
# Add to ~/.zshrc: eval "$(jonq --completions zsh)"
_jonq() {
    local -a opts commands keywords
    opts=(
        '-i:Interactive mode'
        '-f:Output format'
        '-t:Table output'
        '-r:Raw scalar output'
        '-s:Streaming mode'
        '-n:Limit rows'
        '-o:Output file'
        '-p:Pretty print'
        '-w:Watch mode'
        '--follow:Follow stdin'
        '--raw:Raw scalar output'
        '--raw-output:Raw scalar output'
        '--jq:Show jq filter'
        '--explain:Explain query'
        '--time:Show timing'
        '--no-color:No color'
        '--completions:Shell completions'
    )
    commands=(profile diff check run triage connections)
    keywords=(select if where from group by having sort asc desc limit distinct and or not in like between contains as case when then else end is null coalesce count sum avg min max upper lower length round abs ceil floor int float str type keys values trim todate fromdate)

    if [[ "${words[2]}" == -* ]]; then
        _describe 'options' opts
    elif [[ ${CURRENT} -eq 2 ]]; then
        compadd "${commands[@]}"
        _files -g '*.json(|l)'
    else
        compadd "${keywords[@]}"
    fi
}
compdef _jonq jonq'''
    elif shell == "fish":
        return '''# jonq fish completion
# Add to ~/.config/fish/completions/jonq.fish
complete -c jonq -s i -l interactive -d 'Interactive mode' -r -F
complete -c jonq -s f -l format -d 'Output format' -x -a 'json jsonl csv table yaml'
complete -c jonq -s t -l table -d 'Table output'
complete -c jonq -s r -l raw -d 'Raw scalar output'
complete -c jonq -l raw-output -d 'Raw scalar output'
complete -c jonq -s s -l stream -d 'Streaming mode'
complete -c jonq -s n -l limit -d 'Limit rows' -x
complete -c jonq -s o -l out -d 'Output file' -r -F
complete -c jonq -s p -l pretty -d 'Pretty print'
complete -c jonq -s w -l watch -d 'Watch mode'
complete -c jonq -l follow -d 'Follow stdin'
complete -c jonq -l jq -d 'Show jq filter'
complete -c jonq -l explain -d 'Explain query'
complete -c jonq -l time -d 'Show timing'
complete -c jonq -l no-color -d 'No color'
complete -c jonq -l completions -d 'Shell completions' -x -a 'bash zsh fish'
complete -c jonq -n '__fish_use_subcommand' -a 'profile' -d 'Profile JSON fields'
complete -c jonq -n '__fish_use_subcommand' -a 'diff' -d 'Diff JSON profiles'
complete -c jonq -n '__fish_use_subcommand' -a 'check' -d 'Run JSON checks'
complete -c jonq -n '__fish_use_subcommand' -a 'run' -d 'Run named query'
complete -c jonq -n '__fish_use_subcommand' -a 'triage' -d 'Review network event logs'
complete -c jonq -n '__fish_use_subcommand' -a 'connections' -d 'Summarize network connections'
complete -c jonq -l version -d 'Show version\''''
    return ""


async def _follow_stdin(query: str, options: dict) -> None:
    """Stream NDJSON from stdin, applying the query to each line."""
    import csv
    import io
    import shutil

    from jonq.api import _supports_chunk_streaming

    compiled = compile_query(query)
    if options.get("show_jq") or options.get("explain"):
        output = (
            compiled.jq_filter if options.get("show_jq")
            else _explain_query(compiled, color=_query_color_enabled(options))
        )
        _write_query_output(output, options)
        return
    if not _supports_chunk_streaming(compiled):
        raise ValueError("--follow requires a row-wise query. Use a batch query for grouping, sorting, or aggregation.")
    if shutil.which("jq") is None:
        raise ValueError("jq is required. Install jq and make sure it is on PATH.")

    print("Following stdin — press Ctrl+C to stop", file=sys.stderr)
    exec_format = "json" if options["format"] in ("table", "yaml") else options["format"]
    csv_header = None
    failed = False

    try:
        for line_no, raw_line in enumerate(sys.stdin, 1):
            line = raw_line.strip()
            if not line:
                continue
            try:
                json.loads(line)
                result = await execute_async(
                    f"[{line}]", compiled, format=exec_format, limit=options["limit"], validate=False,
                )
                if not result.text or (exec_format == "json" and result.data in ([], None)):
                    continue
                if exec_format != "csv":
                    _write_query_output(_query_result_text(result.text, options), options)
                else:
                    csv_text = io.StringIO(result.text, newline="")
                    header = next(csv.reader(csv_text))
                    if csv_header is None:
                        csv_header = header
                        sys.stdout.write(result.text)
                    elif header != csv_header:
                        raise ValueError("CSV columns changed. Select explicit fields to keep columns fixed.")
                    else:
                        sys.stdout.write(csv_text.read())
                sys.stdout.flush()
            except (ValueError, RuntimeError) as exc:
                _print_log_error(line_no, str(exc))
                failed = True
    except KeyboardInterrupt:
        pass
    if failed:
        sys.exit(1)


def _query_color_enabled(options: dict) -> bool:
    return not options.get("out") and _terminal_color_enabled(options.get("no_color", False))


def _query_result_text(text: str, options: dict) -> str:
    color = _query_color_enabled(options)

    if not text:
        return ""
    if options["format"] == "table":
        from jonq.table_utils import json_to_table

        return json_to_table(text, color=color)
    if options["format"] == "yaml":
        return _json_to_yaml(text)
    if options.get("raw_output"):
        return _json_to_raw(text, terminate_lines=True)
    if options["format"] == "json":
        if options.get("pretty") or color:
            text = _pretty_json_string(text)
        if color:
            text = _colorize_json(text)
    return text


def _write_query_output(text: str, options: dict) -> None:
    if text and not text.endswith("\n"):
        text += "\n"
    out_path = options.get("out")
    if out_path:
        with open(out_path, "w", encoding="utf-8", newline="") as fp:
            fp.write(text)
    elif text:
        sys.stdout.write(text)


async def _run_query(
    json_file: str, query: str, options: dict, *, source_label: str | None = None
) -> str:
    t_start = time.monotonic()
    compiled = compile_query(query)
    t_parse = time.monotonic()

    if options.get("show_jq"):
        return compiled.jq_filter

    if options.get("explain"):
        return _explain_query(compiled, color=_query_color_enabled(options))

    exec_format = "json" if options["format"] in ("table", "yaml") else options["format"]

    result = await execute_async(
        json_file,
        compiled,
        format=exec_format,
        streaming=options["streaming"],
        limit=options.get("limit"),
        validate=True,
        source_label=source_label,
    )
    t_exec = time.monotonic()

    out_text = _query_result_text(result.text, options)
    if options.get("show_time"):
        _print_timing(t_start, t_parse, t_exec, time.monotonic())

    return out_text


async def _write_streaming_query(json_file: str, query: str, options: dict, *, source_label: str) -> None:
    from tempfile import TemporaryFile

    t_start = time.monotonic()
    compiled = compile_query(query)
    t_parse = time.monotonic()
    raw = options["raw_output"]
    json_array = options["format"] == "json" and not raw
    color = json_array and _query_color_enabled(options)
    pretty = json_array and (options["pretty"] or color)
    limit = options["limit"]
    count = 0

    # Publish only after the input and all jq chunks succeed.
    with TemporaryFile(mode="w+t", encoding="utf-8", newline="") as output:
        if json_array:
            output.write("[")
        results = _iter_stream_results(json_file, compiled, source_label=source_label)
        try:
            async for rows in results:
                if limit is not None:
                    rows = rows[:max(0, limit - count)]
                for row in rows:
                    if raw:
                        output.write(_raw_line(row) + "\n")
                    elif pretty:
                        rendered = json.dumps(row, ensure_ascii=False, indent=2)
                        if color:
                            rendered = _colorize_json(rendered)
                        output.write((",\n  " if count else "\n  ") + rendered.replace("\n", "\n  "))
                    else:
                        rendered = json.dumps(row, ensure_ascii=False, separators=(",", ":"))
                        if json_array:
                            output.write(("," if count else "") + rendered)
                        else:
                            output.write(rendered + "\n")
                    count += 1
        finally:
            await results.aclose()
        if json_array:
            output.write("\n]\n" if pretty and count else "]\n")
        t_exec = time.monotonic()

        output.seek(0)
        if options["out"]:
            with open(options["out"], "w", encoding="utf-8", newline="") as destination:
                copyfileobj(output, destination)
        else:
            copyfileobj(output, sys.stdout)

    if options["show_time"]:
        _print_timing(t_start, t_parse, t_exec, time.monotonic())


async def _watch_loop(json_file: str, query: str, options: dict) -> None:
    is_tty = hasattr(sys.stdout, "isatty") and sys.stdout.isatty()
    c = _Colors(is_tty)

    last_mtime = 0.0
    last_output = None
    print(f"{c.DIM}Watching {json_file} — press Ctrl+C to stop{c.NC}")

    try:
        while True:
            try:
                mtime = os.path.getmtime(json_file)
            except OSError:
                await asyncio.sleep(WATCH_RETRY_INTERVAL)
                continue

            if mtime != last_mtime:
                last_mtime = mtime
                try:
                    with _prepare_query_input(
                        json_file, ndjson=options["ndjson"], streaming=options["streaming"]
                    ) as prepared_file:
                        output = await _run_query(prepared_file, query, options, source_label=json_file)
                except Exception as exc:
                    handle_error_with_context(exc, json_file, query)
                    await asyncio.sleep(WATCH_POLL_INTERVAL)
                    continue

                if output != last_output:
                    last_output = output
                    if is_tty:
                        sys.stdout.write(c.CLEAR_SCREEN)
                    print(f"{c.DIM}[{time.strftime('%H:%M:%S')}] {json_file}{c.NC}")
                    _write_query_output(output, options)

            await asyncio.sleep(WATCH_POLL_INTERVAL)
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass


async def _amain(argv: list[str] | None = None):
    logging.basicConfig(
        format="%(levelname)s:%(name)s:%(message)s", level=logging.WARNING
    )

    raw_argv = list(sys.argv[1:] if argv is None else argv)
    if raw_argv and raw_argv[0] in _WORKBENCH_COMMANDS:
        await _run_workbench_command(raw_argv)
        return

    parser = _build_parser()
    args = parser.parse_args(raw_argv)

    if getattr(args, "completions", None):
        print(_generate_completions(args.completions))
        return

    if args.interactive and (args.source is not None or args.query is not None):
        parser.error("--interactive does not accept positional source/query arguments.")

    options = _options_from_args(args)

    if options.get("raw_output") and options["format"] != "json":
        parser.error("--raw/--raw-output can only be used with JSON output.")

    stdin_is_pipe = not sys.stdin.isatty()
    source = args.interactive or args.source
    query = args.query
    if source is None and stdin_is_pipe:
        source = "-"
    if source is None:
        parser.print_usage(sys.stderr)
        print("Try 'jonq --help' for more information.", file=sys.stderr)
        sys.exit(1)

    if (
        stdin_is_pipe and not args.interactive and query is None
        and source.lower().split(maxsplit=1)[:1] == ["select"]
        and not os.path.exists(source)
    ):
        query, source = source, "-"

    json_file = source
    try:
        if args.follow:
            if source != "-" or not stdin_is_pipe or query is None:
                parser.error('--follow requires piped stdin and a query, such as --follow "select *"')
            if args.watch or args.streaming or args.out or args.interactive:
                parser.error("--follow cannot be combined with --watch, --stream, --out or --interactive")
            await _follow_stdin(query, options)
            return

        if args.watch and not args.interactive:
            if query is None:
                parser.error("--watch requires a query")
            validate_input_file(source)
            await _watch_loop(source, query, options)
            return

        inspect_only = query is None and not args.interactive
        with _prepare_query_input(
            source, ndjson=args.ndjson, streaming=args.streaming, inspect_only=inspect_only
        ) as json_file:
            if inspect_only:
                _print_schema(json_file, display_name=source, no_color=args.no_color)
                return

            validate_input_file(json_file)
            if args.interactive:
                await _run_repl(json_file, options, source)
            elif (
                args.streaming and options["format"] in {"json", "jsonl"}
                and not options["explain"] and not options["show_jq"]
                and (options["limit"] is None or options["limit"] >= 0)
            ):
                await _write_streaming_query(json_file, query, options, source_label=source)
            else:
                result = await _run_query(json_file, query, options, source_label=source)
                _write_query_output(result, options)
    except Exception as exc:
        handle_error_with_context(exc, json_file, query)
        sys.exit(1)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="jonq",
        description="Inspect JSON, run readable queries powered by jq, and review saved network logs.",
        epilog=(
            "Common workflows\n"
            "  jonq data.json\n"
            '  jonq response.json "select name, age from users" -t\n'
            '  jonq data.json "select name, age if age > 30"\n'
            "  cat data.json | jonq\n"
            "  jonq profile data.json\n"
            "  jonq diff old.json new.json\n"
            "  jonq check user_contract\n"
            "  jonq run active_users\n"
            "  jonq triage eve.ndjson\n"
            "  jonq connections conn.ndjson --scan-leads\n"
            "  jonq -i data.json\n"
            '  curl api.example.com/data | jonq "select id, name"\n'
            "  tail -f app.log | jonq --follow \"select level, msg if level = 'error'\"\n"
            '  jonq data.json "select *" --watch\n'
            "  jonq 'logs/*.json' \"select * if level = 'error'\""
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "source",
        nargs="?",
        help="Local JSON file, URL, glob, or '-' for stdin",
    )
    parser.add_argument("query", nargs="?", help="jonq query string")
    parser.add_argument(
        "-i",
        "--interactive",
        metavar="FILE",
        help="Interactive query mode (REPL)",
    )
    parser.add_argument(
        "-f",
        "--format",
        choices=("json", "jsonl", "csv", "table", "yaml"),
        default="json",
        help="Output format (json, jsonl, csv, table, yaml)",
    )
    parser.add_argument(
        "-t",
        "--table",
        action="store_true",
        help="Shorthand for --format table",
    )
    parser.add_argument(
        "-r",
        "--raw",
        "--raw-output",
        dest="raw_output",
        action="store_true",
        help="Print scalar values without JSON quoting (one value per line)",
    )
    parser.add_argument(
        "-s",
        "--stream",
        dest="streaming",
        action="store_true",
        help="Process row-wise root-array queries in streaming mode",
    )
    parser.add_argument(
        "--ndjson",
        action="store_true",
        help="Force NDJSON mode (auto-detected by default)",
    )
    parser.add_argument(
        "-n",
        "--limit",
        type=int,
        help="Limit rows/items after the query runs",
    )
    parser.add_argument("-o", "--out", help="Write output to file")
    parser.add_argument(
        "--jq",
        dest="show_jq",
        action="store_true",
        help="Print generated jq and exit",
    )
    parser.add_argument(
        "--explain",
        action="store_true",
        help="Show parsed query breakdown and generated jq filter",
    )
    parser.add_argument(
        "--time",
        dest="show_time",
        action="store_true",
        help="Print execution timing to stderr",
    )
    parser.add_argument(
        "-p",
        "--pretty",
        action="store_true",
        help="Pretty-print JSON output",
    )
    parser.add_argument(
        "-w",
        "--watch",
        action="store_true",
        help="Re-run query when the file changes",
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="Disable colorized output",
    )
    parser.add_argument(
        "--follow",
        action="store_true",
        help="Stream NDJSON from stdin line-by-line, applying the query to each object",
    )
    parser.add_argument(
        "--completions",
        choices=("bash", "zsh", "fish"),
        metavar="SHELL",
        help="Print shell completion script and exit",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {VERSION}",
    )
    return parser


def _options_from_args(args: argparse.Namespace) -> dict:
    fmt = args.format
    if getattr(args, "table", False):
        fmt = "table"
    return {
        "format": fmt,
        "streaming": args.streaming,
        "ndjson": args.ndjson,
        "limit": args.limit,
        "out": args.out,
        "show_jq": args.show_jq,
        "explain": getattr(args, "explain", False),
        "show_time": getattr(args, "show_time", False),
        "pretty": args.pretty,
        "raw_output": getattr(args, "raw_output", False),
        "watch": args.watch,
        "no_color": args.no_color,
        "follow": getattr(args, "follow", False),
    }


async def _run_workbench_command(argv: list[str]) -> None:
    command = argv[0]
    try:
        if command == "profile":
            _run_profile_command(argv[1:])
        elif command == "diff":
            _run_diff_command(argv[1:])
        elif command == "check":
            await _run_check_command(argv[1:])
        elif command == "run":
            await _run_named_query_command(argv[1:])
        elif command == "triage":
            _run_triage_command(argv[1:])
        elif command == "connections":
            _run_connections_command(argv[1:])
        else:
            raise ValueError(f"Unknown command: {command}")
    except SystemExit:
        raise
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


def _run_triage_command(argv: list[str]) -> None:
    from jonq.triage import DEFAULT_MIN_DENIALS, analyze_events, format_triage

    parser = argparse.ArgumentParser(
        prog="jonq triage",
        description="Summarize recorded Suricata EVE alerts and repeated firewall denials from NDJSON.",
        epilog=(
            "Input records\n"
            "  Use one JSON object per line.\n"
            "  EVE alerts use event_type=alert with alert.signature_id or alert.signature.\n"
            "  Firewall records use event_type=firewall, src_ip, and an action such as deny.\n"
            "\n"
            "Examples\n"
            "  jonq triage eve.ndjson\n"
            "  jonq triage - --format json < firewall.ndjson"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "source", nargs="?", default="-",
        help="Local NDJSON file or '-' for stdin (piped stdin by default)",
    )
    parser.add_argument(
        "-f", "--format", choices=("text", "json"), default="text",
        help="Report format (text by default)",
    )
    parser.add_argument("--no-color", action="store_true", help="Disable terminal colors")
    parser.add_argument(
        "--min-denials", type=int, default=DEFAULT_MIN_DENIALS,
        help=f"Minimum denials per source IP across the input (default: {DEFAULT_MIN_DENIALS})",
    )
    args = parser.parse_args(argv)
    if args.min_denials < 1:
        parser.error("--min-denials must be positive")

    with _open_log_input(args.source, parser) as lines:
        report = analyze_events(
            lines, min_denials=args.min_denials, report_error=_print_log_error
        )

    if args.format == "json":
        print(json.dumps(asdict(report), indent=2))
    else:
        print(format_triage(report, color=_terminal_color_enabled(args.no_color), source=args.source))
    if report.invalid_lines:
        sys.exit(1)


def _run_connections_command(argv: list[str]) -> None:
    from jonq.connections import (
        DEFAULT_MIN_DESTINATIONS, DEFAULT_WINDOW_SECONDS, analyze_connections, compare_baseline,
        format_connections, format_scan_report,
    )
    from jonq.networks import parse_networks

    parser = argparse.ArgumentParser(
        prog="jonq connections",
        description="Summarize IP conversations and rolling destination counts from Zeek JSON or Suricata EVE.",
        epilog=(
            "Input records\n"
            "  Use one JSON object per line.\n"
            "  Zeek conn.log in JSON mode uses ts (Unix seconds), id.orig_h, and id.resp_h.\n"
            "  EVE uses event_type=flow, src_ip, dest_ip, and flow.start or timestamp\n"
            "  with a time zone.\n"
            "\n"
            "Examples\n"
            "  jonq connections conn.ndjson --scan-leads\n"
            "  From the Jonq repository root, try the fixture and inspect its cited line.\n"
            "  jonq connections tests/json_test_files/zeek_conn.ndjson --scan-leads --min-destinations 2\n"
            "  sed -n '1p' tests/json_test_files/zeek_conn.ndjson"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "source", nargs="?", default="-",
        help="Local NDJSON file or '-' for stdin (piped stdin by default)",
    )
    parser.add_argument(
        "-f", "--format", choices=("text", "json"), default="text",
        help="Report format (text by default)",
    )
    parser.add_argument("--no-color", action="store_true", help="Disable terminal colors")
    parser.add_argument(
        "--window", type=int, default=DEFAULT_WINDOW_SECONDS, metavar="SECONDS",
        help=f"Rolling interval in seconds (default: {DEFAULT_WINDOW_SECONDS})",
    )
    parser.add_argument(
        "--min-destinations", type=int, default=DEFAULT_MIN_DESTINATIONS, metavar="N",
        help=(
            "Minimum distinct destination IPs per source, or per source and TCP port "
            f"with --scan-leads (default: {DEFAULT_MIN_DESTINATIONS})"
        ),
    )
    parser.add_argument(
        "--src-cidr", action="append", default=[], metavar="IP_OR_CIDR",
        help="Keep connections from any specified source network or IP. Repeatable.",
    )
    parser.add_argument(
        "--dst-cidr", action="append", default=[], metavar="IP_OR_CIDR",
        help="Keep connections to any specified destination network or IP. Repeatable.",
    )
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument(
        "--baseline", metavar="FILE",
        help="Compare qualifying sources with a reference NDJSON export.",
    )
    modes.add_argument(
        "--scan-leads", action="store_true",
        help="Review same-port TCP attempts with rejection or no reply observed.",
    )
    args = parser.parse_args(argv)
    if args.window < 1:
        parser.error("--window must be a positive number of seconds")
    if args.min_destinations < 2:
        parser.error("--min-destinations must be at least 2")
    if args.baseline == "-":
        parser.error("--baseline requires a local NDJSON file")
    try:
        src_networks = parse_networks(args.src_cidr)
        dst_networks = parse_networks(args.dst_cidr)
    except ValueError as exc:
        parser.error(f"invalid IP or CIDR filter: {exc}")

    scope = {
        "window_seconds": args.window,
        "src_networks": src_networks,
        "dst_networks": dst_networks,
    }
    with _open_log_input(args.source, parser) as lines:
        report = analyze_connections(
            lines,
            min_destinations=args.min_destinations,
            report_error=_print_log_error,
            scan_leads_only=args.scan_leads,
            **scope,
        )

    comparison = None
    if args.baseline is not None:
        with open(args.baseline, "rb") as lines:
            reference = analyze_connections(
                lines,
                min_destinations=1,
                include_evidence=False,
                report_error=lambda line, message: print(
                    f"Baseline line {line}: {message}", file=sys.stderr
                ),
                **scope,
            )
        comparison = compare_baseline(report, reference)

    if args.format == "json":
        payload = asdict(report)
        if comparison is not None:
            payload["baseline"] = asdict(comparison)
        print(json.dumps(payload, indent=2, default=float))
    elif args.scan_leads:
        print(format_scan_report(report, color=_terminal_color_enabled(args.no_color), source=args.source))
    else:
        print(format_connections(report, comparison, color=_terminal_color_enabled(args.no_color)))
    if report.invalid_lines or (comparison and comparison.invalid_lines):
        sys.exit(1)


def _open_log_input(source: str, parser: argparse.ArgumentParser):
    if source != "-":
        return open(source, "rb")
    if sys.stdin.isatty():
        parser.error("provide a file or pipe NDJSON to stdin")
    return nullcontext(sys.stdin.buffer)


def _terminal_color_enabled(no_color: bool) -> bool:
    return (
        not no_color
        and "NO_COLOR" not in os.environ
        and os.environ.get("TERM") != "dumb"
        and sys.stdout.isatty()
    )


def _print_log_error(line_no: int, message: str) -> None:
    print(f"Line {line_no}: {message}", file=sys.stderr)


def _run_profile_command(argv: list[str]) -> None:
    parser = argparse.ArgumentParser(
        prog="jonq profile",
        description="Profile JSON fields, types, nulls, and missing values.",
    )
    parser.add_argument("source", help="Local JSON or NDJSON file")
    parser.add_argument(
        "-f",
        "--format",
        choices=("text", "json"),
        default="text",
        help="Output format",
    )
    parser.add_argument(
        "--max-records",
        type=int,
        help="Profile only the first N records",
    )
    args = parser.parse_args(argv)

    validate_input_file(args.source)
    profile = build_profile(args.source, max_records=args.max_records)
    if args.format == "json":
        print(json.dumps(profile.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(format_profile(profile))


def _run_diff_command(argv: list[str]) -> None:
    parser = argparse.ArgumentParser(
        prog="jonq diff",
        description="Compare JSON profiles and show shape drift.",
    )
    parser.add_argument("old", help="Old/baseline JSON or NDJSON file")
    parser.add_argument("new", help="New/current JSON or NDJSON file")
    parser.add_argument(
        "-f",
        "--format",
        choices=("text", "json"),
        default="text",
        help="Output format",
    )
    parser.add_argument(
        "--fail-on-change",
        action="store_true",
        help="Exit with status 1 when profile changes are found",
    )
    args = parser.parse_args(argv)

    validate_input_file(args.old)
    validate_input_file(args.new)
    diff = compare_profiles(build_profile(args.old), build_profile(args.new))
    if args.format == "json":
        print(json.dumps(diff.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(format_diff(diff))
    if args.fail_on_change and diff.has_changes():
        sys.exit(1)


async def _run_check_command(argv: list[str]) -> None:
    parser = argparse.ArgumentParser(
        prog="jonq check",
        description="Run JSON contract checks from flags or jonq.yaml.",
    )
    parser.add_argument("target", nargs="?", help="Check name or source file")
    parser.add_argument(
        "-c",
        "--config",
        default="jonq.yaml",
        help="Path to jonq.yaml",
    )
    parser.add_argument("--all", action="store_true", help="Run all configured checks")
    parser.add_argument("--source", help="Source file for an inline check")
    parser.add_argument(
        "--require",
        action="append",
        help="Required field path; repeat or pass comma-separated values",
    )
    parser.add_argument(
        "--no-null",
        action="append",
        help="Field path that must not contain null; repeat or comma-separate",
    )
    parser.add_argument(
        "--type",
        dest="types",
        action="append",
        help="Type expectation such as field:string or field=number|string",
    )
    parser.add_argument("--min-count", type=int, help="Minimum record count")
    parser.add_argument("--max-count", type=int, help="Maximum record count")
    parser.add_argument(
        "-f",
        "--format",
        choices=("text", "json"),
        default="text",
        help="Output format",
    )
    args = parser.parse_args(argv)

    inline_requested = any(
        (
            args.source,
            args.require,
            args.no_null,
            args.types,
            args.min_count is not None,
            args.max_count is not None,
        )
    )

    specs: list[tuple[str, dict]] = []
    if args.all or (not args.target and not inline_requested):
        config = load_config(args.config)
        checks = config.get("checks") or {}
        if not isinstance(checks, dict) or not checks:
            raise ValueError(f"No checks found in {args.config}.")
        specs.extend((name, spec) for name, spec in checks.items())
    elif inline_requested:
        specs.append(("inline", _inline_check_spec(args)))
    else:
        config = load_config(args.config)
        checks = config.get("checks") or {}
        if not isinstance(checks, dict) or args.target not in checks:
            raise ValueError(f"Check '{args.target}' was not found in {args.config}.")
        specs.append((args.target, checks[args.target]))

    results = []
    for name, spec in specs:
        if not isinstance(spec, dict):
            raise ValueError(f"Check '{name}' must be a mapping.")
        profile = await _profile_for_check_spec(name, spec)
        results.append(run_profile_check(profile, spec, name))

    if args.format == "json":
        payload = [result.to_dict() for result in results]
        if len(payload) == 1:
            print(json.dumps(payload[0], ensure_ascii=False, indent=2))
        else:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print("\n\n".join(format_check_result(result) for result in results))

    if any(not result.ok for result in results):
        sys.exit(1)


def _inline_check_spec(args: argparse.Namespace) -> dict:
    source = args.source or args.target
    if not source:
        raise ValueError("Inline checks need a source file.")
    spec: dict[str, object] = {"source": source}
    if args.require:
        spec["require"] = normalize_list(args.require)
    if args.no_null:
        spec["no_null"] = normalize_list(args.no_null)
    if args.types:
        spec["types"] = _parse_type_expectations(args.types)
    if args.min_count is not None:
        spec["min_count"] = args.min_count
    if args.max_count is not None:
        spec["max_count"] = args.max_count
    if len(spec) == 1:
        raise ValueError("Inline checks need at least one assertion.")
    return spec


def _parse_type_expectations(values: list[str]) -> dict[str, str]:
    expectations = {}
    for raw in values:
        for item in normalize_list(raw):
            if ":" in item:
                path, expected = item.split(":", 1)
            elif "=" in item:
                path, expected = item.split("=", 1)
            else:
                raise ValueError(
                    "--type expects field:type or field=type, for example id:number"
                )
            expectations[path.strip()] = expected.strip()
    return expectations


async def _profile_for_check_spec(name: str, spec: dict) -> object:
    source = spec.get("source")
    if not source:
        raise ValueError(f"Check '{name}' needs a source.")
    validate_input_file(source)

    query = spec.get("query")
    if query:
        result = await execute_async(source, query, format="json", validate=True)
        return build_profile_from_data(
            result.data,
            source=f"{source} | {query}",
            root="query",
        )

    return build_profile(source)


async def _run_named_query_command(argv: list[str]) -> None:
    parser = argparse.ArgumentParser(
        prog="jonq run",
        description="Run a named query from jonq.yaml.",
    )
    parser.add_argument("name", help="Named query from jonq.yaml")
    parser.add_argument(
        "-c",
        "--config",
        default="jonq.yaml",
        help="Path to jonq.yaml",
    )
    parser.add_argument(
        "-f",
        "--format",
        choices=("json", "jsonl", "csv", "table", "yaml"),
        help="Override configured output format",
    )
    parser.add_argument("-r", "--raw", "--raw-output", dest="raw_output", action="store_true")
    parser.add_argument("-p", "--pretty", action="store_true", help="Pretty-print JSON")
    parser.add_argument("-o", "--out", help="Write output to file")
    parser.add_argument("--jq", dest="show_jq", action="store_true", help="Print jq")
    parser.add_argument("--explain", action="store_true", help="Explain query")
    parser.add_argument("--no-color", action="store_true", help="Disable color")
    args = parser.parse_args(argv)

    config = load_config(args.config)
    queries = config.get("queries") or {}
    if not isinstance(queries, dict) or args.name not in queries:
        raise ValueError(f"Query '{args.name}' was not found in {args.config}.")

    spec = queries[args.name]
    if not isinstance(spec, dict):
        raise ValueError(f"Query '{args.name}' must be a mapping.")
    source = spec.get("source")
    query = spec.get("query")
    if not source or not query:
        raise ValueError(f"Query '{args.name}' needs source and query.")

    fmt = args.format or spec.get("format") or "json"
    options = {
        "format": fmt,
        "streaming": False,
        "ndjson": False,
        "limit": spec.get("limit"),
        "out": args.out or spec.get("out"),
        "show_jq": args.show_jq,
        "explain": args.explain,
        "show_time": False,
        "pretty": args.pretty,
        "raw_output": args.raw_output,
        "watch": False,
        "no_color": args.no_color,
        "follow": False,
    }
    if options.get("raw_output") and options["format"] != "json":
        raise ValueError("--raw/--raw-output can only be used with JSON output.")

    with _prepare_query_input(source) as json_file:
        validate_input_file(json_file)
        result = await _run_query(json_file, query, options, source_label=source)
        _write_query_output(result, options)


def print_help():
    _build_parser().print_help()


def parse_options(args: list[str]) -> dict:
    parsed = _build_parser().parse_args(["placeholder.json", "select *", *args])
    return _options_from_args(parsed)


def validate_input_file(json_file: str) -> None:
    if not os.path.exists(json_file):
        raise FileNotFoundError(f"JSON file '{json_file}' not found.")
    if not os.path.isfile(json_file):
        raise FileNotFoundError(f"'{json_file}' is not a file.")
    if not os.access(json_file, os.R_OK):
        raise PermissionError(f"Cannot read JSON file '{json_file}'.")
    if os.path.getsize(json_file) == 0:
        raise ValueError(f"JSON file '{json_file}' is empty.")


def main(argv: list[str] | None = None):
    asyncio.run(_amain(argv))


def entrypoint():
    main()


if __name__ == "__main__":
    main()
