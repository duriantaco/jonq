from __future__ import annotations

import json
import re
import os
import sys
import shlex

from jonq.ast import AndCondition, BetweenCondition, Condition, Expression, ExprType, InCondition, NotCondition, OrCondition, PathType
from jonq.constants import (
    _Colors,
    FUZZY_MAX_DISTANCE,
    FUZZY_MAX_RESULTS,
    ERROR_SAMPLE_SIZE,
)
from jonq.parser import _QUOTED_KEY, decode_quoted_key, parse_expression, parse_path, resolve_from_path
from jonq.query_parser import parse_condition_string
from jonq.tokenizer import TokenType, tokenize_with_lexer


_ARRAY_SELECTOR = r"\[\d*\]"
_SIMPLE_FIELD_SEGMENT = rf"[A-Za-z_]\w*(?:{_ARRAY_SELECTOR})*"
_SIMPLE_FIELD_PATH = rf"{_SIMPLE_FIELD_SEGMENT}(?:\.{_SIMPLE_FIELD_SEGMENT})*"


def _edit_distance(a: str, b: str) -> int:
    la, lb = len(a), len(b)
    if la == 0:
        return lb
    if lb == 0:
        return la
    prev = list(range(lb + 1))
    for i in range(1, la + 1):
        curr = [i] + [0] * lb
        for j in range(1, lb + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            curr[j] = min(curr[j - 1] + 1, prev[j] + 1, prev[j - 1] + cost)
        prev = curr
    return prev[lb]


def _fuzzy_suggest(
    name: str, available: list[str], max_dist: int = FUZZY_MAX_DISTANCE
) -> list[str]:
    name_lower = name.lower()
    candidates = []
    for field in available:
        d = _edit_distance(name_lower, field.lower())
        if d <= max_dist and d > 0:
            candidates.append((d, field))
    candidates.sort()
    return [c[1] for c in candidates[:FUZZY_MAX_RESULTS]]


def _format_query_field(path: str) -> str:
    if _is_simple_field_ref(path):
        return path
    escaped = path.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _path_key(name: str) -> str:
    return name if re.fullmatch(r"[A-Za-z_]\w*", name) else json.dumps(name, ensure_ascii=False)


def _path_text(elements, *, selectors=None) -> str:
    result = ""
    for element in elements:
        if element.type != PathType.ARRAY_INDEX and (element.value or element.type == PathType.FIELD):
            if result:
                result += "."
            result += _path_key(element.value)
        if element.type != PathType.FIELD:
            index = next(selectors) if selectors is not None else ""
            result += f"[{index}]"
    return result


def _shell_query_argument(query: str) -> str:
    if any(char in query for char in ('"', "\\", "$", "`", "!")):
        return shlex.quote(query)
    return f'"{query}"'


def _available_fields(data, prefix: str = "", depth: int = 0):
    if depth > 5:
        return

    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                yield from _available_fields(item, prefix, depth)
            elif isinstance(item, list) and prefix:
                array_field = f"{prefix}[]"
                yield array_field
                yield from _available_fields(item, array_field, depth + 1)
        return

    if not isinstance(data, dict):
        return

    for key, value in data.items():
        segment = _path_key(key)
        field = f"{prefix}.{segment}" if prefix else segment
        yield field

        if isinstance(value, dict):
            yield from _available_fields(value, field, depth + 1)
        elif isinstance(value, list):
            array_field = f"{field}[]"
            yield array_field
            yield from _available_fields(value, array_field, depth + 1)


def _contains_field(data, elements) -> bool:
    if not elements:
        return True
    element, *remaining = elements
    if element.type == PathType.FIELD or (element.type == PathType.ARRAY and element.value):
        if not isinstance(data, dict) or element.value not in data:
            return False
        data = data[element.value]
    if element.type == PathType.FIELD:
        return _contains_field(data, remaining)
    # Validate the array's shape even if the queried index is absent in this row.
    return isinstance(data, list) and (
        not remaining or any(_contains_field(item, remaining) for item in data)
    )


def _best_field_suggestion(
    name: str, available: list[str], *, preferred: set[str] | None = None
) -> str | None:
    name_leaf = _field_leaf(name)
    leaf_matches = []
    for field in available:
        field_leaf = _field_leaf(field)
        if name_leaf == field_leaf:
            leaf_matches.append((0, _edit_distance(name, field), field))
            continue
        leaf_distance = _edit_distance(name_leaf.lower(), field_leaf.lower())
        if leaf_distance <= 2:
            leaf_matches.append((leaf_distance, _edit_distance(name, field), field))
    if preferred:
        leaf_matches.sort(key=lambda match: (match[0], match[2] not in preferred, match[1], match[2]))
    else:
        leaf_matches.sort()
    if leaf_matches:
        return leaf_matches[0][2]

    direct = _fuzzy_suggest(name, available)
    if direct:
        return direct[0]

    return None


def _field_leaf(path: str) -> str:
    return next((element.value for element in reversed(parse_path(path).elements) if element.value), path)


def _replace_field_references(
    query: str, replacements: dict[str, str], having_replacements: dict[str, str], aliases: set[str],
) -> str:
    if not replacements and not having_replacements:
        return query
    tokens = tokenize_with_lexer(query, with_positions=True)
    pieces = []
    offset = 0
    active_replacements = replacements
    for index, token in enumerate(tokens):
        if token.type == TokenType.KEYWORD:
            if token.value == "having":
                active_replacements = having_replacements
            elif token.value in {"sort", "from", "limit"}:
                active_replacements = replacements
        if token.type != TokenType.IDENTIFIER or token.value not in active_replacements:
            continue
        preceding = tokens[index - 1].value.lower() if index else ""
        if preceding in {"as", "from", "contains", "like"}:
            continue
        if preceding == "sort" and token.value in aliases:
            continue
        if index + 1 < len(tokens) and tokens[index + 1].value == "(":
            continue
        pieces.extend((query[offset:token.position], active_replacements[token.value]))
        offset = token.position + len(token.value)
    pieces.append(query[offset:])
    return "".join(pieces)


def _is_simple_field_ref(value: str | None) -> bool:
    return bool(value and re.fullmatch(_SIMPLE_FIELD_PATH, value))


def _rows_at_path(data, elements):
    if not elements:
        yield data
        return
    element, *remaining = elements
    if element.type == PathType.FIELD or (element.type == PathType.ARRAY and element.value):
        if not isinstance(data, dict) or element.value not in data:
            return
        data = data[element.value]
    if element.type == PathType.ARRAY:
        if isinstance(data, list):
            for item in data:
                yield from _rows_at_path(item, remaining)
    elif element.type == PathType.ARRAY_INDEX:
        index = int(element.value)
        if isinstance(data, list) and index < len(data):
            yield from _rows_at_path(data[index], remaining)
    else:
        yield from _rows_at_path(data, remaining)


def _predicate_fields(predicate):
    if isinstance(predicate, (AndCondition, OrCondition)):
        yield from _predicate_fields(predicate.left)
        yield from _predicate_fields(predicate.right)
    elif isinstance(predicate, NotCondition):
        yield from _predicate_fields(predicate.condition)
    elif isinstance(predicate, (BetweenCondition, InCondition)):
        yield predicate.field
    elif isinstance(predicate, Condition):
        yield from _expression_fields(predicate.expr)


def _expression_fields(expression):
    if expression.type == ExprType.FIELD:
        if expression.value:
            yield expression.value
    elif expression.type == ExprType.CASE:
        for condition, value in expression.args or ():
            yield from _predicate_fields(parse_condition_string(condition))
            yield from _expression_fields(parse_expression(value))
        if expression.value:
            yield from _expression_fields(parse_expression(expression.value))
    elif expression.type == ExprType.AGGREGATION:
        for argument in expression.args or ():
            if argument != "*":
                yield from _expression_fields(parse_expression(argument))
    else:
        for argument in expression.args or ():
            if isinstance(argument, Expression):
                yield from _expression_fields(argument)


def _field_refs_from_compiled(compiled) -> tuple[list[str], list[str], dict[str, bool]]:
    refs: list[str] = []
    aliases: dict[str, bool] = {}
    for kind, *parts in compiled.fields:
        *values, alias = parts
        aliases[alias] = kind != "field" or alias != values[0]
        if kind == "field":
            refs.append(values[0])
        elif kind in {"count_distinct", "aggregation", "function"}:
            refs.append(values[-1])
        elif kind == "expression":
            refs.extend(_expression_fields(parse_expression(values[0])))

    refs.extend(compiled.group_by or ())
    if compiled.order_by and compiled.order_by not in aliases:
        refs.append(compiled.order_by)
    refs.extend(_predicate_fields(compiled.predicate))
    bad_having = []
    if compiled.having:
        having = parse_condition_string(compiled.having, allow_alias_arithmetic=True)
        bad_having = list(dict.fromkeys(ref for ref in _predicate_fields(having) if ref not in aliases))

    return list(dict.fromkeys(ref for ref in refs if ref and ref != "*")), bad_having, aliases


def _format_query_repair_message(
    *,
    query: str,
    json_file: str,
    bad_refs: list[str],
    available: list[str],
    replacements: dict[str, str],
    having_replacements: dict[str, str],
    aliases: set[str],
    command_options: tuple[str, ...] = (),
) -> str:
    repaired = _replace_field_references(query, replacements, having_replacements, aliases)

    lines = [f"Unknown field(s): {', '.join(bad_refs)}"]
    nearby = []
    for old, new in {**replacements, **having_replacements}.items():
        label = decode_quoted_key(new) if _QUOTED_KEY.fullmatch(new) and " " in new else new
        nearby.append(f"{old} -> {label}")
    if nearby:
        lines.append(f"Did you mean: {'; '.join(nearby)}?")

    available_preview = ", ".join(available[:12])
    if len(available) > 12:
        available_preview += ", ..."
    lines.append(f"Available fields: {available_preview}")

    if repaired != query:
        query_arg = _shell_query_argument(repaired)
        words = ["jonq", shlex.quote(json_file), query_arg, *command_options]
        lines.append("Try: " + " ".join(words))
    else:
        lines.append(f"Run `jonq {shlex.quote(json_file)}` to inspect fields and samples.")

    return "\n".join(lines)


class JonqError(Exception):
    def __init__(self, message, suggestion=None, context=None):
        super().__init__(message)
        self.suggestion = suggestion
        self.context = context or {}

    def format_error(self):
        is_tty = hasattr(sys.stderr, "isatty") and sys.stderr.isatty()
        c = _Colors(is_tty)

        output = [f"{c.RED}Error: {self.args[0]}{c.NC}"]

        if self.context:
            output.append(f"\n{c.BOLD_YELLOW}Context:{c.NC}")
            for key, value in self.context.items():
                output.append(f"  {key}: {value}")

        if self.suggestion:
            output.append(f"\n{c.GREEN}Suggestion: {self.suggestion}{c.NC}")

        return "\n".join(output)


class QuerySyntaxError(JonqError):
    pass


class FieldNotFoundError(JonqError):
    pass


class AggregationError(JonqError):
    pass


class ErrorAnalyzer:
    def __init__(self, json_file, query, jq_filter):
        self.json_file = json_file
        self.query = query
        self.jq_filter = jq_filter
        self.data = self._load_json_sample()

    def _load_json_sample(self):
        try:
            with open(self.json_file, "r") as f:
                sample = f.read(ERROR_SAMPLE_SIZE)
                return json.loads(sample)
        except (OSError, json.JSONDecodeError, ValueError):
            return None

    def analyze_jq_error(self, stderr):
        if "Cannot iterate over null" in stderr:
            return self._analyze_null_iteration_error(stderr)

        if "Cannot index array with string" in stderr:
            field = self._extract_field_from_error(stderr)
            suggestion = f"Use array index like [0].{field} or iterate with []"
            if self.data:
                available = self._get_available_fields(self.data)
                similar = _fuzzy_suggest(field, available)
                if similar:
                    suggestion += f". Did you mean: {', '.join(similar)}?"
            return FieldNotFoundError(
                f"Trying to access field '{field}' on an array",
                suggestion=suggestion,
                context={"query": self.query, "field": field},
            )

        if "is not defined" in stderr:
            return self._analyze_undefined_error(stderr)

        if "syntax error" in stderr:
            return QuerySyntaxError(
                "Invalid jq syntax generated",
                suggestion="This might be a bug in jonq. Please report it.",
                context={"query": self.query, "jq_filter": self.jq_filter},
            )

        return JonqError(
            stderr.strip(), context={"query": self.query, "jq_filter": self.jq_filter}
        )

    def _analyze_null_iteration_error(self, stderr):
        fields = re.findall(r"\.(\w+)", self.query)

        if self.data:
            null_fields = self._find_null_fields(self.data, fields)
            if null_fields:
                available = self._get_available_fields(self.data)
                suggestion = f"Check if '{null_fields[0]}' exists in your JSON. Use 'select *' to see available fields."
                similar = _fuzzy_suggest(null_fields[0], available)
                if similar:
                    suggestion += f" Did you mean: {', '.join(similar)}?"
                return FieldNotFoundError(
                    f"Field '{null_fields[0]}' is null or doesn't exist",
                    suggestion=suggestion,
                    context={
                        "query": self.query,
                        "missing_field": null_fields[0],
                        "available_fields": available,
                    },
                )

        return JonqError(
            "Cannot iterate over null values in your JSON",
            suggestion="Check if the field exists and contains data",
            context={"query": self.query},
        )

    def _analyze_undefined_error(self, stderr):
        if any(func in stderr for func in ["avg/1", "max/1", "min/1", "sum/1"]):
            return AggregationError(
                "Aggregation function failed - field might not exist or contain non-numeric values",
                suggestion="Make sure the field exists and contains numbers",
                context={"query": self.query},
            )

        return JonqError(
            "Undefined function or operator",
            context={"query": self.query, "error": stderr},
        )

    def _find_null_fields(self, data, fields):
        null_fields = []

        if isinstance(data, list) and data:
            data = data[0]

        for field in fields:
            parts = field.split(".")
            current = data
            field_exists = True

            for part in parts:
                if isinstance(current, dict) and part in current:
                    current = current[part]
                else:
                    field_exists = False
                    break

            if not field_exists or current is None:
                null_fields.append(field)

        return null_fields

    def _get_available_fields(self, data, prefix=""):
        fields = []

        if isinstance(data, list) and data:
            data = data[0]

        if isinstance(data, dict):
            for key, value in data.items():
                if prefix:
                    full_key = f"{prefix}.{key}"
                else:
                    full_key = key

                fields.append(full_key)

                if isinstance(value, dict) and len(full_key.split(".")) < 3:
                    fields.extend(self._get_available_fields(value, full_key))

        return fields

    def _extract_field_from_error(self, stderr):
        match = re.search(r'"(\w+)"', stderr)

        if match:
            return match.group(1)
        else:
            return "unknown"


def validate_query_against_batches(
    batches, query, *, source_label: str, command_options: tuple[str, ...] = ()
) -> str | None:
    # A batch is either a complete JSON document or a list of root-array rows.
    if isinstance(query, str) or (query.condition and query.predicate is None):
        from jonq.api import compile_query

        query = compile_query(getattr(query, "query", query))

    refs, bad_having, projected_aliases = _field_refs_from_compiled(query)
    aliases = set(projected_aliases)
    expected = {ref: parse_path(ref).elements for ref in refs}
    if not expected and not bad_having:
        return None
    source = resolve_from_path(query.from_path) if query.from_path else None
    available: dict[str, None] = {}
    for data in batches:
        if not expected:
            break
        if source is not None:
            rows = list(_rows_at_path(data, source.elements))
        else:
            rows = data if isinstance(data, list) else [data]
        for ref, elements in list(expected.items()):
            if not elements:
                del expected[ref]
                continue
            first = elements[0]
            root_selector = first.type == PathType.ARRAY_INDEX or (
                first.type == PathType.ARRAY and not first.value
            )
            candidates = [rows] if root_selector else rows
            if any(_contains_field(row, elements) for row in candidates):
                del expected[ref]
        if not expected:
            break
        if len(available) < 120:
            for field in _available_fields(rows):
                available.setdefault(field, None)
                if len(available) == 120:
                    break

    if not available:
        expected.clear()
    if not expected and not bad_having:
        return None

    replacements = {}
    for ref, elements in expected.items():
        schema_ref = _path_text(elements)
        suggestion = _best_field_suggestion(schema_ref, list(available))
        if suggestion:
            selectors = [
                element.value if element.type == PathType.ARRAY_INDEX else ""
                for element in elements if element.type != PathType.FIELD
            ]
            suggested_elements = parse_path(suggestion).elements
            if len(selectors) == sum(element.type != PathType.FIELD for element in suggested_elements):
                suggestion = _path_text(suggested_elements, selectors=iter(selectors))
            replacements[ref] = suggestion
    preferred_aliases = {alias for alias, declared in projected_aliases.items() if declared}
    having_replacements = {
        ref: suggestion for ref in bad_having
        if (suggestion := _best_field_suggestion(ref, sorted(aliases), preferred=preferred_aliases)) is not None
    }
    if os.environ.get("JONQ_DEBUG_SCHEMA"):
        print(
            f"[schema] refs={refs} aliases={sorted(aliases)} available={list(available)}",
            file=sys.stderr,
        )
    return _format_query_repair_message(
        query=query.query,
        json_file=source_label,
        bad_refs=list(dict.fromkeys([*expected, *bad_having])),
        available=list(available) or sorted(aliases),
        replacements=replacements,
        having_replacements=having_replacements,
        aliases=aliases,
        command_options=command_options,
    )


def validate_query_against_schema(
    json_file: str | os.PathLike[str], query, *, source_label: str | None = None
) -> str | None:
    try:
        with open(json_file, "r", encoding="utf-8") as fp:
            data = json.load(fp)
        return validate_query_against_batches(
            (data,), query, source_label=source_label if source_label is not None else os.fspath(json_file)
        )
    except (OSError, ValueError, KeyError):
        return None


def handle_error_with_context(error, json_file=None, query=None, jq_filter=None):
    if isinstance(error, JonqError):
        print(error.format_error(), file=sys.stderr)
    elif isinstance(error, (RuntimeError, ValueError)) and "Error in jq filter:" in str(
        error
    ):
        stderr = str(error).replace("Error in jq filter:", "").strip()
        analyzer = ErrorAnalyzer(json_file, query, jq_filter)
        jonq_error = analyzer.analyze_jq_error(stderr)
        print(jonq_error.format_error(), file=sys.stderr)
    else:
        print(f"Error: {error}", file=sys.stderr)
