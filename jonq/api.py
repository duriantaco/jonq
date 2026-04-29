from __future__ import annotations

from dataclasses import dataclass
from os import PathLike
from typing import Any
import os
import re

from jonq.csv_utils import json_to_csv
from jonq.error_handler import ErrorAnalyzer, QuerySyntaxError, validate_query_against_schema
from jonq.executor import run_jq, run_jq_async, run_jq_streaming, run_jq_streaming_async
from jonq.generator import (
    build_jq_path as ast_build_jq_path,
    escape_string as ast_escape_string,
    generate_jq_condition,
    generate_jq_path,
)
from jonq.json_utils import dumps, loads
from jonq.parser import parse_condition_tokens, parse_path
from jonq.query_parser import parse_query as parse_query_tokens
from jonq.query_parser import tokenize_query
from jonq.jq_filter import generate_jq_filter

__all__ = [
    "CompiledQuery",
    "QueryResult",
    "compile_query",
    "execute",
    "execute_async",
    "query",
    "query_async",
    "transform_nested_array_path",
    "build_jq_path",
    "format_field_path",
    "parse_condition_for_from",
    "escape_string",
]


@dataclass(frozen=True)
class CompiledQuery:
    query: str
    fields: tuple[tuple[Any, ...], ...]
    condition: str | None
    group_by: tuple[str, ...]
    having: str | None
    order_by: str | None
    sort_direction: str
    limit: str | None
    from_path: str | None
    distinct: bool
    jq_filter: str


@dataclass(frozen=True)
class QueryResult:
    compiled: CompiledQuery
    text: str
    output_format: str
    data: Any | None = None


def compile_query(query: str) -> CompiledQuery:
    tokens = tokenize_query(query)
    (
        fields,
        condition,
        group_by,
        having,
        order_by,
        sort_direction,
        limit,
        from_path,
        distinct,
    ) = parse_query_tokens(tokens)
    jq_filter = generate_jq_filter(
        fields,
        condition,
        group_by,
        having,
        order_by,
        sort_direction,
        limit,
        from_path,
        distinct,
    )
    return CompiledQuery(
        query=query,
        fields=tuple(fields),
        condition=condition,
        group_by=tuple(group_by or ()),
        having=having,
        order_by=order_by,
        sort_direction=sort_direction,
        limit=limit,
        from_path=from_path,
        distinct=distinct,
        jq_filter=jq_filter,
    )


def execute(
    source: Any,
    query: str | CompiledQuery,
    *,
    format: str = "json",
    streaming: bool = False,
    limit: int | None = None,
    validate: bool = True,
) -> QueryResult:
    _validate_result_format(format, allowed={"json", "csv", "jsonl"})
    compiled = _coerce_compiled_query(query)
    source_info = _normalize_source(source)
    _validate_execution_args(source_info, compiled, streaming=streaming, validate=validate)

    if source_info["path"] is not None:
        if streaming:
            stdout, stderr = run_jq_streaming(source_info["path"], compiled.jq_filter)
        else:
            stdout, stderr = run_jq(source_info["path"], compiled.jq_filter)
    else:
        stdout, stderr = run_jq(compiled.jq_filter, source_info["json_text"])

    return _build_result(
        stdout,
        stderr,
        compiled,
        source_path=source_info["path"],
        output_format=format,
        limit=limit,
    )


async def execute_async(
    source: Any,
    query: str | CompiledQuery,
    *,
    format: str = "json",
    streaming: bool = False,
    limit: int | None = None,
    validate: bool = True,
) -> QueryResult:
    _validate_result_format(format, allowed={"json", "csv", "jsonl"})
    compiled = _coerce_compiled_query(query)
    source_info = _normalize_source(source)
    _validate_execution_args(source_info, compiled, streaming=streaming, validate=validate)

    if source_info["path"] is not None:
        if streaming:
            stdout, stderr = await run_jq_streaming_async(
                source_info["path"], compiled.jq_filter
            )
        else:
            stdout, stderr = await run_jq_async(source_info["path"], compiled.jq_filter)
    else:
        stdout, stderr = await run_jq_async(compiled.jq_filter, source_info["json_text"])

    return _build_result(
        stdout,
        stderr,
        compiled,
        source_path=source_info["path"],
        output_format=format,
        limit=limit,
    )


def query(
    source: Any,
    query: str | CompiledQuery,
    *,
    format: str = "python",
    streaming: bool = False,
    limit: int | None = None,
    validate: bool = True,
) -> Any:
    _validate_result_format(format, allowed={"python", "json", "csv", "jsonl"})
    result = execute(
        source,
        query,
        format=format if format in {"csv", "jsonl"} else "json",
        streaming=streaming,
        limit=limit,
        validate=validate,
    )
    return result.data if format == "python" else result.text


async def query_async(
    source: Any,
    query: str | CompiledQuery,
    *,
    format: str = "python",
    streaming: bool = False,
    limit: int | None = None,
    validate: bool = True,
) -> Any:
    _validate_result_format(format, allowed={"python", "json", "csv", "jsonl"})
    result = await execute_async(
        source,
        query,
        format=format if format in {"csv", "jsonl"} else "json",
        streaming=streaming,
        limit=limit,
        validate=validate,
    )
    return result.data if format == "python" else result.text


def _coerce_compiled_query(query: str | CompiledQuery) -> CompiledQuery:
    if isinstance(query, CompiledQuery):
        return query
    return compile_query(query)


def _normalize_source(source: Any) -> dict[str, str | None]:
    if isinstance(source, PathLike):
        return {"path": os.fspath(source), "json_text": None}
    if isinstance(source, str):
        if os.path.exists(source):
            return {"path": source, "json_text": None}
        if _looks_like_json_text(source):
            return {"path": None, "json_text": source}
        if _looks_like_path(source):
            return {"path": source, "json_text": None}
        return {"path": None, "json_text": source}
    if isinstance(source, (bytes, bytearray)):
        return {"path": None, "json_text": bytes(source).decode("utf-8")}
    return {"path": None, "json_text": dumps(source)}


def _validate_execution_args(
    source_info: dict[str, str | None],
    compiled: CompiledQuery,
    *,
    streaming: bool,
    validate: bool,
) -> None:
    if streaming and source_info["path"] is None:
        raise ValueError("Streaming mode requires a filesystem path.")

    if streaming and not _supports_chunk_streaming(compiled):
        raise ValueError(
            "Streaming mode does not support aggregations, group by, sort, "
            "distinct, or limit because those require global query state."
        )

    if source_info["path"] is not None:
        if not os.path.exists(source_info["path"]):
            raise FileNotFoundError(f"JSON file '{source_info['path']}' not found.")
        if not os.path.isfile(source_info["path"]):
            raise FileNotFoundError(f"'{source_info['path']}' is not a file.")

    if not validate or source_info["path"] is None:
        return

    validation_error = validate_query_against_schema(source_info["path"], compiled.query)
    if validation_error:
        raise QuerySyntaxError(
            validation_error, suggestion="Use 'select *' to see available fields"
        )


def _build_result(
    stdout: str,
    stderr: str,
    compiled: CompiledQuery,
    *,
    source_path: str | None,
    output_format: str,
    limit: int | None,
) -> QueryResult:
    if stderr:
        if source_path is not None:
            analyzer = ErrorAnalyzer(source_path, compiled.query, compiled.jq_filter)
            raise analyzer.analyze_jq_error(stderr)
        raise ValueError(stderr.strip())

    text = stdout or ""

    if limit is not None and text and output_format != "csv":
        text = _apply_limit_to_json_string(text, limit)

    if output_format == "csv" and text:
        text = json_to_csv(text)
        if limit is not None:
            text = _apply_limit_to_csv_string(text, limit)
    elif output_format == "jsonl" and text:
        text = _json_to_jsonl(text)

    data = None
    if output_format == "json" and text:
        data = loads(text)

    return QueryResult(
        compiled=compiled,
        text=text,
        output_format=output_format,
        data=data,
    )


def _apply_limit_to_json_string(s: str, n: int) -> str:
    try:
        data = loads(s)
    except (TypeError, ValueError):
        return s

    if isinstance(data, list):
        return dumps(data[:n])
    return s


def _apply_limit_to_csv_string(s: str, n: int) -> str:
    lines = s.splitlines()
    if not lines:
        return s
    return "\n".join(lines[:1] + lines[1 : 1 + max(0, n)])


def _json_to_jsonl(s: str) -> str:
    try:
        data = loads(s)
    except (TypeError, ValueError):
        return s

    if isinstance(data, list):
        return "\n".join(dumps(item) for item in data)
    return dumps(data)


def transform_nested_array_path(field_path):
    path = parse_path(field_path)
    return generate_jq_path(path)


def build_jq_path(field_path):
    return ast_build_jq_path(field_path)


def format_field_path(field):
    path = parse_path(field)
    return generate_jq_path(path)


def parse_condition_for_from(tokens):
    condition = parse_condition_tokens(tokens)
    return generate_jq_condition(condition, "array") if condition else None


def escape_string(s):
    return ast_escape_string(s)


def _looks_like_path(source: str) -> bool:
    return source == "-" or source.startswith((".", "~")) or os.sep in source or source.endswith(
        (".json", ".jsonl", ".ndjson")
    )


def _looks_like_json_text(source: str) -> bool:
    stripped = source.lstrip()
    if not stripped:
        return False
    if stripped[0] in "[{":
        return True
    if stripped[0] == '"' and len(stripped) >= 2:
        return True
    if stripped.startswith(("true", "false", "null")):
        return True
    return bool(
        re.match(r"^[+-]?((\d+(\.\d*)?)|(\.\d+))([eE][+-]?\d+)?\s*$", stripped)
    )


def _supports_chunk_streaming(compiled: CompiledQuery) -> bool:
    if compiled.group_by or compiled.order_by or compiled.limit or compiled.distinct:
        return False
    for field in compiled.fields:
        if field[0] in {"aggregation", "count_distinct"}:
            return False
    return True


def _validate_result_format(format: str, *, allowed: set[str]) -> None:
    if format not in allowed:
        allowed_list = ", ".join(sorted(allowed))
        raise ValueError(f"Unsupported format '{format}'. Expected one of: {allowed_list}.")
