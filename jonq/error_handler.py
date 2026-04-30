from __future__ import annotations

import json
import re
import os
import sys
import shlex

from jonq.constants import (
    _Colors,
    FUZZY_MAX_DISTANCE,
    FUZZY_MAX_RESULTS,
    ERROR_SAMPLE_SIZE,
)


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


def _collect_available_fields(data, prefix: str = "", depth: int = 0) -> list[str]:
    if depth > 5:
        return []

    if isinstance(data, list):
        fields = []
        for item in data[:5]:
            if isinstance(item, dict):
                for field in _collect_available_fields(item, prefix, depth):
                    if field not in fields:
                        fields.append(field)
        return fields

    if not isinstance(data, dict):
        return []

    fields = []
    for key, value in data.items():
        field = f"{prefix}.{key}" if prefix else key
        fields.append(field)

        if isinstance(value, dict):
            fields.extend(_collect_available_fields(value, field, depth + 1))
        elif isinstance(value, list):
            array_field = f"{field}[]"
            fields.append(array_field)
            fields.extend(_collect_available_fields(value, array_field, depth + 1))

    deduped = []
    for field in fields:
        if field not in deduped:
            deduped.append(field)
    return deduped


def _best_field_suggestion(name: str, available: list[str]) -> str | None:
    direct = _fuzzy_suggest(name, available)
    if direct:
        return direct[0]

    name_leaf = name.replace("[]", "").split(".")[-1]
    leaf_matches = [
        field
        for field in available
        if _fuzzy_suggest(name_leaf, [field.replace("[]", "").split(".")[-1]], max_dist=2)
    ]
    if leaf_matches:
        return leaf_matches[0]

    return None


def _replace_field_reference(query: str, old: str, new: str) -> str:
    pattern = re.compile(rf"(?<![\w.]){re.escape(old)}(?![\w.])")
    return pattern.sub(new, query)


def _is_simple_field_ref(value: str | None) -> bool:
    if not value or value == "*":
        return False
    return bool(re.fullmatch(r"[A-Za-z_][\w]*(?:\[\])?(?:\.[A-Za-z_][\w]*(?:\[\])?)*", value))


def _field_refs_from_compiled(compiled) -> tuple[list[str], set[str]]:
    refs = []
    aliases = set()

    for field in getattr(compiled, "fields", ()) or ():
        if not field:
            continue
        kind = field[0]
        if kind == "field":
            _, path, alias = field
            refs.append(path)
            if alias != path:
                aliases.add(alias)
        elif kind == "aggregation":
            _, _, param, alias = field
            if param != "*":
                refs.append(param)
            aliases.add(alias)
        elif kind == "function":
            _, _, param, alias = field
            if _is_simple_field_ref(param):
                refs.append(param)
            aliases.add(alias)
        elif kind == "count_distinct":
            _, param, alias = field
            refs.append(param)
            aliases.add(alias)

    refs.extend(getattr(compiled, "group_by", ()) or ())

    order_by = getattr(compiled, "order_by", None)
    if order_by:
        refs.append(order_by)

    for expr in (getattr(compiled, "condition", None), getattr(compiled, "having", None)):
        refs.extend(_field_refs_from_expression(expr))

    deduped = []
    for ref in refs:
        if ref and ref not in deduped:
            deduped.append(ref)
    return deduped, aliases


def _field_refs_from_expression(expr: str | None) -> list[str]:
    if not expr:
        return []

    refs = []
    for match in re.finditer(r"\.([A-Za-z_][\w]*(?:\?\.[A-Za-z_][\w]*)*)\??", expr):
        refs.append(match.group(1).replace("?.", ".").rstrip("?"))

    if refs:
        return refs

    cleaned = re.sub(r"(['\"]).*?\1", " ", expr)
    skip = {
        "and",
        "or",
        "not",
        "null",
        "true",
        "false",
        "contains",
        "in",
        "like",
        "between",
        "is",
    }
    for token in re.findall(r"\b[A-Za-z_][\w]*(?:\.[A-Za-z_][\w]*)*\b", cleaned):
        if token.lower() not in skip:
            refs.append(token)
    return refs


def _field_refs_from_query(query: str) -> tuple[list[str], set[str]]:
    refs = []
    aliases = set()

    m = re.search(
        r"\bselect\s+(.*?)(?:\s+(?:from|if|where|group|order|sort|limit)\b|$)",
        query,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if m:
        for raw in m.group(1).split(","):
            part = raw.strip()
            if not part or part == "*":
                continue
            if part.lower().startswith("distinct "):
                part = part.split(None, 1)[1].strip()
            alias_match = re.search(r"\s+as\s+([A-Za-z_]\w*)$", part, flags=re.IGNORECASE)
            if alias_match:
                aliases.add(alias_match.group(1))
                part = part[: alias_match.start()].strip()
            if _is_simple_field_ref(part):
                refs.append(part)

    for pattern in (
        r"\b(?:if|where)\s+(.*?)(?:\s+(?:group|order|sort|limit)\b|$)",
        r"\bhaving\s+(.*?)(?:\s+(?:order|sort|limit)\b|$)",
    ):
        m = re.search(pattern, query, flags=re.IGNORECASE | re.DOTALL)
        if m:
            refs.extend(_field_refs_from_expression(m.group(1)))

    m = re.search(r"\bgroup\s+by\s+(.*?)(?:\s+(?:having|order|sort|limit)\b|$)", query, flags=re.IGNORECASE | re.DOTALL)
    if m:
        refs.extend(part.strip() for part in m.group(1).split(",") if part.strip())

    m = re.search(r"\b(?:order\s+by|sort)\s+([A-Za-z_][\w.]*)", query, flags=re.IGNORECASE)
    if m:
        refs.append(m.group(1))

    deduped = []
    for ref in refs:
        if ref and ref not in deduped:
            deduped.append(ref)
    return deduped, aliases


def _format_query_repair_message(
    *,
    query: str,
    json_file: str,
    bad_refs: list[str],
    available: list[str],
    replacements: dict[str, str],
) -> str:
    repaired = query
    for old, new in replacements.items():
        repaired = _replace_field_reference(repaired, old, new)

    lines = [f"Unknown field(s): {', '.join(bad_refs)}"]
    nearby = []
    for old, new in replacements.items():
        nearby.append(f"{old} -> {new}")
    if nearby:
        lines.append(f"Did you mean: {'; '.join(nearby)}?")

    available_preview = ", ".join(available[:12])
    if len(available) > 12:
        available_preview += ", ..."
    lines.append(f"Available fields: {available_preview}")

    if repaired != query:
        query_arg = f'"{repaired}"' if '"' not in repaired else shlex.quote(repaired)
        lines.append(f"Try: jonq {shlex.quote(json_file)} {query_arg}")
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


def validate_query_against_schema(json_file: str, query) -> str | None:
    try:
        query_text = getattr(query, "query", query)
        with open(json_file, "r", encoding="utf-8") as fp:
            data = json.load(fp)

        if isinstance(data, list) and data:
            sample = next((item for item in data if isinstance(item, dict)), data[0])
        else:
            sample = data

        if not isinstance(sample, dict):
            return None

        available = _collect_available_fields(sample)
        available_set = set(available)

        if re.search(r"\bfrom\b", query_text, flags=re.IGNORECASE):
            return None

        if hasattr(query, "fields"):
            refs, aliases = _field_refs_from_compiled(query)
        else:
            refs, aliases = _field_refs_from_query(query_text)

        bad = []
        replacements = {}
        for ref in refs:
            if not _is_simple_field_ref(ref):
                continue
            if ref in aliases or ref in available_set:
                continue
            if ref.split(".", 1)[0] in available_set and ref not in available_set:
                bad.append(ref)
            elif ref not in available_set:
                bad.append(ref)

            suggestion = _best_field_suggestion(ref, available)
            if suggestion:
                replacements[ref] = suggestion

        if os.environ.get("JONQ_DEBUG_SCHEMA"):
            print(
                f"[schema] refs={refs} aliases={sorted(aliases)} available={available}",
                file=sys.stderr,
            )

        if bad:
            deduped_bad = []
            for ref in bad:
                if ref not in deduped_bad:
                    deduped_bad.append(ref)
            return _format_query_repair_message(
                query=query_text,
                json_file=json_file,
                bad_refs=deduped_bad,
                available=available,
                replacements=replacements,
            )
        return None
    except (OSError, json.JSONDecodeError, ValueError, KeyError):
        return None


def handle_error_with_context(error, json_file=None, query=None, jq_filter=None):
    if isinstance(error, JonqError):
        print(error.format_error())
    elif isinstance(error, (RuntimeError, ValueError)) and "Error in jq filter:" in str(
        error
    ):
        stderr = str(error).replace("Error in jq filter:", "").strip()
        analyzer = ErrorAnalyzer(json_file, query, jq_filter)
        jonq_error = analyzer.analyze_jq_error(stderr)
        print(jonq_error.format_error())
    else:
        print(f"Error: {error}")
