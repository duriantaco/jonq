from __future__ import annotations

from collections import OrderedDict
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import json
import os
import re


MAX_SAMPLE_TEXT = 80


@dataclass
class FieldProfile:
    path: str
    present: int = 0
    null: int = 0
    types: OrderedDict[str, int] = field(default_factory=OrderedDict)
    sample: Any = None
    has_sample: bool = False

    def add_record_values(self, values: list[Any]) -> None:
        self.present += 1
        if any(value is None for value in values):
            self.null += 1

        for value in values:
            type_name = value_type(value)
            self.types[type_name] = self.types.get(type_name, 0) + 1
            if not self.has_sample and value is not None:
                self.sample = value
                self.has_sample = True

        if not self.has_sample and values:
            self.sample = values[0]
            self.has_sample = True

    def missing(self, total_records: int) -> int:
        return max(0, total_records - self.present)

    def non_null_types(self) -> set[str]:
        return {type_name for type_name in self.types if type_name != "null"}

    def to_dict(self, total_records: int) -> dict[str, Any]:
        return {
            "path": self.path,
            "types": dict(self.types),
            "present": self.present,
            "null": self.null,
            "missing": self.missing(total_records),
            "sample": self.sample if self.has_sample else None,
        }


@dataclass
class JsonProfile:
    source: str
    root: str
    records: int
    fields: OrderedDict[str, FieldProfile]

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "root": self.root,
            "records": self.records,
            "fields": [
                field.to_dict(self.records) for field in self.fields.values()
            ],
        }


@dataclass
class ProfileDiff:
    old: JsonProfile
    new: JsonProfile
    added: list[str]
    removed: list[str]
    type_changed: list[tuple[str, set[str], set[str]]]
    required_changed: list[tuple[str, int, int]]
    nullability_changed: list[tuple[str, int, int]]

    def has_changes(self) -> bool:
        return bool(
            self.added
            or self.removed
            or self.type_changed
            or self.required_changed
            or self.nullability_changed
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "old": self.old.source,
            "new": self.new.source,
            "added": self.added,
            "removed": self.removed,
            "type_changed": [
                {
                    "path": path,
                    "old": sorted(old_types),
                    "new": sorted(new_types),
                }
                for path, old_types, new_types in self.type_changed
            ],
            "required_changed": [
                {"path": path, "old_missing": old_missing, "new_missing": new_missing}
                for path, old_missing, new_missing in self.required_changed
            ],
            "nullability_changed": [
                {"path": path, "old_null": old_null, "new_null": new_null}
                for path, old_null, new_null in self.nullability_changed
            ],
            "changed": self.has_changes(),
        }


@dataclass
class CheckResult:
    name: str
    source: str
    ok: bool
    records: int
    failures: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "source": self.source,
            "ok": self.ok,
            "records": self.records,
            "failures": self.failures,
        }


def load_json_source(path: str) -> tuple[Any, str]:
    with open(path, "r", encoding="utf-8") as fp:
        text = fp.read()

    if not text.strip():
        raise ValueError(f"JSON file '{path}' is empty.")

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        records = []
        for line_no, raw_line in enumerate(text.splitlines(), start=1):
            line = raw_line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"Invalid JSON on line {line_no} in '{path}': {exc.msg}"
                ) from exc
        if not records:
            raise ValueError(f"JSON file '{path}' has no JSON records.")
        return records, "ndjson"

    if isinstance(data, list):
        return data, "array"
    if isinstance(data, dict):
        return data, "object"
    return data, "scalar"


def build_profile(path: str, *, max_records: int | None = None) -> JsonProfile:
    data, root = load_json_source(path)
    return build_profile_from_data(data, source=path, root=root, max_records=max_records)


def build_profile_from_data(
    data: Any,
    *,
    source: str = "<memory>",
    root: str | None = None,
    max_records: int | None = None,
) -> JsonProfile:
    if root is None:
        if isinstance(data, list):
            root = "array"
        elif isinstance(data, dict):
            root = "object"
        else:
            root = "scalar"

    records = data if isinstance(data, list) else [data]
    if max_records is not None:
        records = records[:max(0, max_records)]

    fields: OrderedDict[str, FieldProfile] = OrderedDict()
    for record in records:
        record_paths: OrderedDict[str, list[Any]] = OrderedDict()
        if isinstance(record, dict):
            _collect_value_paths(record, "", record_paths)
        elif isinstance(record, list):
            _collect_value_paths(record, "value", record_paths)
        else:
            record_paths["value"] = [record]

        for path, values in record_paths.items():
            field_profile = fields.setdefault(path, FieldProfile(path=path))
            field_profile.add_record_values(values)

    return JsonProfile(source=source, root=root, records=len(records), fields=fields)


def _collect_value_paths(
    value: Any,
    path: str,
    paths: OrderedDict[str, list[Any]],
) -> None:
    if path:
        paths.setdefault(path, []).append(value)

    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}" if path else str(key)
            _collect_value_paths(child, child_path, paths)
        return

    if isinstance(value, list):
        item_path = f"{path}[]" if path else "[]"
        for child in value:
            if isinstance(child, (dict, list)):
                _collect_value_paths(child, item_path, paths)
            else:
                paths.setdefault(item_path, []).append(child)


def value_type(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, dict):
        return "object"
    if isinstance(value, list):
        if not value:
            return "array[empty]"
        labels = []
        for item in value:
            label = value_type(item)
            if label not in labels:
                labels.append(label)
        return "array[" + " | ".join(labels) + "]"
    return type(value).__name__


def compare_profiles(old: JsonProfile, new: JsonProfile) -> ProfileDiff:
    old_paths = set(old.fields)
    new_paths = set(new.fields)
    shared = sorted(old_paths & new_paths)

    type_changed = []
    required_changed = []
    nullability_changed = []
    for path in shared:
        old_field = old.fields[path]
        new_field = new.fields[path]

        old_types = old_field.non_null_types()
        new_types = new_field.non_null_types()
        if old_types != new_types:
            type_changed.append((path, old_types, new_types))

        old_missing = old_field.missing(old.records)
        new_missing = new_field.missing(new.records)
        if (old_missing == 0) != (new_missing == 0):
            required_changed.append((path, old_missing, new_missing))

        if (old_field.null == 0) != (new_field.null == 0):
            nullability_changed.append((path, old_field.null, new_field.null))

    return ProfileDiff(
        old=old,
        new=new,
        added=sorted(new_paths - old_paths),
        removed=sorted(old_paths - new_paths),
        type_changed=type_changed,
        required_changed=required_changed,
        nullability_changed=nullability_changed,
    )


def run_profile_check(profile: JsonProfile, spec: dict[str, Any], name: str) -> CheckResult:
    failures = []

    min_count = spec.get("min_count")
    if min_count is not None and profile.records < int(min_count):
        failures.append(
            f"Expected at least {int(min_count)} record(s), found {profile.records}."
        )

    max_count = spec.get("max_count")
    if max_count is not None and profile.records > int(max_count):
        failures.append(
            f"Expected at most {int(max_count)} record(s), found {profile.records}."
        )

    for path in normalize_list(spec.get("require")):
        field_profile = profile.fields.get(path)
        if field_profile is None:
            failures.append(f"Required field '{path}' was not found.")
            continue
        missing = field_profile.missing(profile.records)
        if missing:
            failures.append(
                f"Required field '{path}' is missing on {missing}/{profile.records} record(s)."
            )

    for path in normalize_list(spec.get("no_null")):
        field_profile = profile.fields.get(path)
        if field_profile is None:
            failures.append(f"Field '{path}' was not found for no_null check.")
            continue
        if field_profile.null:
            failures.append(
                f"Field '{path}' is null on {field_profile.null}/{profile.records} record(s)."
            )

    types = spec.get("types") or {}
    if not isinstance(types, dict):
        raise ValueError("check 'types' must be a mapping of field path to type.")

    for path, expected in types.items():
        field_profile = profile.fields.get(path)
        if field_profile is None:
            failures.append(f"Field '{path}' was not found for type check.")
            continue
        expected_types = normalize_types(expected)
        actual_types = field_profile.non_null_types()
        if not actual_types and "null" in field_profile.types:
            actual_types = {"null"}
        unexpected = sorted(
            type_name
            for type_name in actual_types
            if not type_is_allowed(type_name, expected_types)
        )
        if unexpected:
            failures.append(
                f"Field '{path}' expected type {format_type_set(expected_types)}, "
                f"found {format_type_set(actual_types)}."
            )

    return CheckResult(
        name=name,
        source=profile.source,
        ok=not failures,
        records=profile.records,
        failures=failures,
    )


def normalize_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    if isinstance(value, (list, tuple)):
        items: list[str] = []
        for item in value:
            items.extend(normalize_list(item))
        return items
    return [str(value)]


def normalize_types(value: Any) -> set[str]:
    if isinstance(value, (list, tuple, set)):
        raw = []
        for item in value:
            raw.extend(normalize_list(str(item).replace("|", ",")))
    else:
        raw = normalize_list(str(value).replace("|", ","))
    aliases = {
        "bool": "boolean",
        "int": "number",
        "float": "number",
        "num": "number",
        "str": "string",
        "dict": "object",
        "list": "array",
    }
    return {aliases.get(item.strip().lower(), item.strip().lower()) for item in raw}


def type_is_allowed(actual: str, expected: set[str]) -> bool:
    if actual in expected:
        return True
    if actual.startswith("array[") and "array" in expected:
        return True
    return False


def format_type_set(types: set[str]) -> str:
    if not types:
        return "<none>"
    return " | ".join(sorted(types))


def format_profile(profile: JsonProfile) -> str:
    lines = [
        profile.source,
        f"Root: {profile.root} ({profile.records} record{'s' if profile.records != 1 else ''})",
    ]
    if not profile.fields:
        lines.append("No fields found.")
        return "\n".join(lines)

    rows = []
    for field_profile in profile.fields.values():
        rows.append(
            {
                "path": field_profile.path,
                "types": " | ".join(field_profile.types.keys()),
                "present": str(field_profile.present),
                "null": str(field_profile.null),
                "missing": str(field_profile.missing(profile.records)),
                "sample": preview_value(field_profile.sample)
                if field_profile.has_sample
                else "",
            }
        )

    lines.append("")
    lines.append("Fields:")
    lines.append(render_table(rows, ["path", "types", "present", "null", "missing", "sample"]))
    return "\n".join(lines)


def format_diff(diff: ProfileDiff) -> str:
    lines = [
        f"Schema diff: {diff.old.source} -> {diff.new.source}",
    ]
    if not diff.has_changes():
        lines.append("No profile changes found.")
        return "\n".join(lines)

    if diff.added:
        lines.append("")
        lines.append("Added fields:")
        for path in diff.added:
            field_profile = diff.new.fields[path]
            lines.append(f"  + {path} ({' | '.join(field_profile.types.keys())})")

    if diff.removed:
        lines.append("")
        lines.append("Removed fields:")
        for path in diff.removed:
            field_profile = diff.old.fields[path]
            lines.append(f"  - {path} ({' | '.join(field_profile.types.keys())})")

    if diff.type_changed:
        lines.append("")
        lines.append("Type changes:")
        for path, old_types, new_types in diff.type_changed:
            lines.append(
                f"  * {path}: {format_type_set(old_types)} -> {format_type_set(new_types)}"
            )

    if diff.required_changed:
        lines.append("")
        lines.append("Presence changes:")
        for path, old_missing, new_missing in diff.required_changed:
            lines.append(f"  * {path}: missing {old_missing} -> {new_missing}")

    if diff.nullability_changed:
        lines.append("")
        lines.append("Nullability changes:")
        for path, old_null, new_null in diff.nullability_changed:
            lines.append(f"  * {path}: null {old_null} -> {new_null}")

    return "\n".join(lines)


def format_check_result(result: CheckResult) -> str:
    status = "PASS" if result.ok else "FAIL"
    lines = [
        f"Check {result.name}: {status}",
        f"Source: {result.source}",
        f"Records: {result.records}",
    ]
    if result.failures:
        lines.append("Failures:")
        lines.extend(f"  - {failure}" for failure in result.failures)
    return "\n".join(lines)


def preview_value(value: Any) -> str:
    text = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    if len(text) > MAX_SAMPLE_TEXT:
        return text[: MAX_SAMPLE_TEXT - 1] + "..."
    return text


def render_table(rows: list[dict[str, str]], headers: list[str]) -> str:
    widths = {header: len(header) for header in headers}
    for row in rows:
        for header in headers:
            widths[header] = max(widths[header], len(row.get(header, "")))

    def line_for(row: dict[str, str]) -> str:
        return "  ".join(row.get(header, "").ljust(widths[header]) for header in headers)

    header_row = {header: header for header in headers}
    separator = {header: "-" * widths[header] for header in headers}
    return "\n".join([line_for(header_row), line_for(separator)] + [line_for(row) for row in rows])


def load_config(path: str = "jonq.yaml") -> dict[str, Any]:
    if not os.path.exists(path):
        raise FileNotFoundError(f"Config file '{path}' was not found.")

    with open(path, "r", encoding="utf-8") as fp:
        text = fp.read()

    data = parse_config_text(text)
    if data is None:
        data = {}
    if not isinstance(data, dict):
        raise ValueError(f"Config file '{path}' must contain a mapping.")
    return resolve_config_paths(data, path)


def parse_config_text(text: str) -> Any:
    stripped = text.strip()
    if not stripped:
        return {}

    if stripped[0] in "[{":
        return json.loads(stripped)

    try:
        import yaml

        return yaml.safe_load(text)
    except ImportError:
        return parse_simple_yaml(text)


def resolve_config_paths(config: dict[str, Any], config_path: str) -> dict[str, Any]:
    resolved = deepcopy(config)
    base_dir = Path(config_path).resolve().parent
    for section in ("queries", "checks"):
        entries = resolved.get(section)
        if not isinstance(entries, dict):
            continue
        for spec in entries.values():
            if not isinstance(spec, dict):
                continue
            source = spec.get("source")
            if isinstance(source, str) and source != "-" and not os.path.isabs(source):
                spec["source"] = str(base_dir / source)
    return resolved


def parse_simple_yaml(text: str) -> Any:
    lines = []
    for raw_line in text.splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        lines.append((indent, raw_line.strip()))

    if not lines:
        return {}

    value, index = _parse_yaml_block(lines, 0, lines[0][0])
    if index != len(lines):
        raise ValueError("Could not parse jonq.yaml.")
    return value


def _parse_yaml_block(
    lines: list[tuple[int, str]],
    index: int,
    indent: int,
) -> tuple[Any, int]:
    container: dict[str, Any] | list[Any] | None = None

    while index < len(lines):
        current_indent, content = lines[index]
        if current_indent < indent:
            break
        if current_indent > indent:
            raise ValueError(f"Unexpected indentation near: {content}")

        if content.startswith("- "):
            if container is None:
                container = []
            if not isinstance(container, list):
                raise ValueError("Cannot mix YAML lists and mappings at one level.")
            item_text = content[2:].strip()
            if item_text:
                container.append(_parse_yaml_scalar(item_text))
                index += 1
            else:
                child, index = _parse_yaml_child(lines, index, indent)
                container.append(child)
            continue

        if container is None:
            container = {}
        if not isinstance(container, dict):
            raise ValueError("Cannot mix YAML lists and mappings at one level.")

        if ":" not in content:
            raise ValueError(f"Expected key/value pair near: {content}")
        key, raw_value = content.split(":", 1)
        key = key.strip()
        raw_value = raw_value.strip()
        if raw_value:
            container[key] = _parse_yaml_scalar(raw_value)
            index += 1
        else:
            child, index = _parse_yaml_child(lines, index, indent)
            container[key] = child

    return container if container is not None else {}, index


def _parse_yaml_child(
    lines: list[tuple[int, str]],
    index: int,
    parent_indent: int,
) -> tuple[Any, int]:
    index += 1
    if index >= len(lines) or lines[index][0] <= parent_indent:
        return {}, index
    return _parse_yaml_block(lines, index, lines[index][0])


def _parse_yaml_scalar(value: str) -> Any:
    value = value.strip()
    if not value:
        return ""
    if (value[0], value[-1]) in {('"', '"'), ("'", "'")}:
        return value[1:-1]
    lowered = value.lower()
    if lowered in ("true", "false"):
        return lowered == "true"
    if lowered in ("null", "none", "~"):
        return None
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        return [_parse_yaml_scalar(part) for part in _split_inline_list(inner)]
    if re.fullmatch(r"-?\d+", value):
        return int(value)
    if re.fullmatch(r"-?\d+\.\d+", value):
        return float(value)
    return value


def _split_inline_list(value: str) -> list[str]:
    parts = []
    current = []
    quote = None
    for char in value:
        if quote:
            current.append(char)
            if char == quote:
                quote = None
            continue
        if char in ("'", '"'):
            quote = char
            current.append(char)
            continue
        if char == ",":
            parts.append("".join(current).strip())
            current = []
            continue
        current.append(char)
    parts.append("".join(current).strip())
    return parts
