from __future__ import annotations

import json
import re
import os
import sys

from jonq.constants import (
    _Colors,
    FUZZY_MAX_DISTANCE,
    FUZZY_MAX_RESULTS,
    ERROR_SAMPLE_SIZE,
)


def _edit_distance(a: str, b: str) -> int:
    """Levenshtein distance between two strings."""
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
    """Return available field names within edit distance of `name`, sorted by distance."""
    name_lower = name.lower()
    candidates = []
    for field in available:
        d = _edit_distance(name_lower, field.lower())
        if d <= max_dist and d > 0:
            candidates.append((d, field))
    candidates.sort()
    return [c[1] for c in candidates[:FUZZY_MAX_RESULTS]]


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


def validate_query_against_schema(json_file: str, query: str) -> str | None:
    try:
        with open(json_file, "r", encoding="utf-8") as fp:
            data = json.load(fp)

        if isinstance(data, list) and data:
            sample = data[0]
        else:
            sample = data

        if not isinstance(sample, dict):
            return None

        top_keys = set(sample.keys())

        if re.search(r"\bfrom\b", query, flags=re.IGNORECASE):
            return None

        m = re.search(
            r"\bselect\s+(.*?)(?:\s+(?:from|if|group|order|sort|limit)\b|$)",
            query,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if not m:
            return None
        field_list = m.group(1)

        raw_fields = []
        split_fields = field_list.split(",")
        _skip_words = {"distinct", "as"}

        for f in split_fields:
            cleaned_field = f.strip()
            parts = cleaned_field.split(None, 1)
            if parts and parts[0].lower() in _skip_words:
                cleaned_field = parts[1] if len(parts) > 1 else ""

            as_parts = cleaned_field.rsplit(" as ", 1)
            cleaned_field = as_parts[0].strip()
            if cleaned_field and cleaned_field != "*":
                raw_fields.append(cleaned_field)

        def head_of(path):
            p = path.strip().strip('"').strip("'")
            if p.startswith("."):
                p = p[1:]
            for sep in ("[", "."):
                if sep in p:
                    return p.split(sep, 1)[0]
            return p

        bad = []
        special_chars = ["{", "}", "(", ")", "+", "-", "*", "/"]

        for f in raw_fields:
            has_special_chars = False
            for ch in special_chars:
                if ch in f:
                    has_special_chars = True
                    break

            if has_special_chars:
                continue

            h = head_of(f)

            field_exists = bool(h)
            is_new_field = h not in top_keys
            is_not_wildcard = f != "*"

            if field_exists and is_new_field and is_not_wildcard:
                bad.append(f)

        if os.environ.get("JONQ_DEBUG_SCHEMA"):
            print(
                f"[schema] fields={raw_fields} heads={[head_of(f) for f in raw_fields]} top={sorted(top_keys)}",
                file=sys.stderr,
            )

        if bad:
            avail = ", ".join(sorted(top_keys))
            suggestions = []
            for b in bad:
                h = head_of(b)
                similar = _fuzzy_suggest(h, list(top_keys))
                if similar:
                    suggestions.append(f"'{h}' -> {', '.join(similar)}")
            msg = f"Field(s) {', '.join(bad)!r} not found. Available fields: {avail}"
            if suggestions:
                msg += f". Did you mean: {'; '.join(suggestions)}?"
            return msg
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
