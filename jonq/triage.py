from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import datetime
import json
import re

from jonq.constants import _Colors
from jonq.ndjson import EventReader, input_line_command
from jonq.networks import canonical_ip
from jonq.table_utils import render_table


DEFAULT_MIN_DENIALS = 5
_ALERT_EXAMPLE_LIMIT = 2
_DENIAL_ACTIONS = {
    "block", "blocked", "deny", "denied", "drop", "dropped", "reject", "rejected",
}
_EVE_TIMESTAMP = re.compile(
    r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(?:\.\d{1,9})?"
    r"(?:Z|[+-](?:[01]\d|2[0-3]):?[0-5]\d)",
    re.ASCII,
)


@dataclass(frozen=True)
class AlertExample:
    line: int
    timestamp: str | None


@dataclass
class AlertGroup:
    signature_id: int | None
    signature: str | None
    count: int = 0
    examples: list[AlertExample] = field(default_factory=list)


@dataclass(frozen=True)
class DenialGroup:
    src_ip: str
    count: int


@dataclass(frozen=True)
class TriageReport:
    events: int
    invalid_lines: int
    min_denials: int
    denied_events: int
    alerts: list[AlertGroup]
    repeated_denials: list[DenialGroup]


def analyze_events(
    lines: Iterable[bytes],
    *,
    min_denials: int = DEFAULT_MIN_DENIALS,
    report_error: Callable[[int, str], None],
) -> TriageReport:
    """Read NDJSON in one pass and retain counts and examples of recorded alerts."""
    events = 0
    reader = EventReader(lines, report_error)
    alerts: dict[int | str, AlertGroup] = {}
    denials: Counter[str] = Counter()

    for line_no, event in reader:
        try:
            event_type = _required_text(
                event.get("event_type"), "expected an event_type string"
            ).casefold()
            if event_type == "alert":
                _count_alert(event, line_no, alerts)
            elif event_type == "firewall":
                action = _required_text(event.get("action"), "firewall event requires an action")
                if action.casefold() in _DENIAL_ACTIONS:
                    denials[_denial_source(event.get("src_ip"))] += 1
        except ValueError as exc:
            reader.reject(line_no, str(exc))
        else:
            events += 1

    repeated_denials = (
        DenialGroup(src_ip, count)
        for src_ip, count in denials.items()
        if count >= min_denials
    )
    return TriageReport(
        events=events,
        invalid_lines=reader.invalid_lines,
        min_denials=min_denials,
        denied_events=sum(denials.values()),
        alerts=sorted(
            alerts.values(),
            key=lambda group: (
                -group.count, group.signature_id is None,
                group.signature_id or 0, group.signature or "",
            ),
        ),
        repeated_denials=sorted(repeated_denials, key=lambda group: (-group.count, group.src_ip)),
    )


def _required_text(value: object, error: str) -> str:
    if isinstance(value, str) and value.strip():
        return value.strip()
    raise ValueError(error)


def _count_alert(event: dict, line_no: int, alerts: dict[int | str, AlertGroup]) -> None:
    value = event.get("alert")
    if not isinstance(value, dict):
        raise ValueError("alert event requires an alert object")

    signature_id = value.get("signature_id")
    if type(signature_id) is not int or signature_id < 1:
        signature_id = None

    signature = value.get("signature")
    signature = (signature.strip() or None) if isinstance(signature, str) else None
    key = signature_id if signature_id is not None else signature
    if key is None:
        raise ValueError("alert event requires an alert.signature_id or alert.signature")

    group = alerts.get(key)
    if group is None:
        group = alerts[key] = AlertGroup(signature_id, signature)
    elif group.signature is None:
        group.signature = signature
    group.count += 1
    if len(group.examples) < _ALERT_EXAMPLE_LIMIT:
        group.examples.append(AlertExample(line_no, _example_timestamp(event.get("timestamp"))))


def _example_timestamp(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    match = _EVE_TIMESTAMP.fullmatch(value)
    if not match:
        return None
    try:
        datetime.fromisoformat(match.group(1))
    except ValueError:
        return None
    return value


def _denial_source(value: object) -> str:
    try:
        return canonical_ip(value)
    except ValueError:
        raise ValueError("denied firewall event requires a valid src_ip") from None


def format_triage(report: TriageReport, *, color: bool = False, source: str | None = None) -> str:
    colors = _Colors(color)
    event_label = "event" if report.events == 1 else "events"
    invalid_label = "line" if report.invalid_lines == 1 else "lines"
    lines = [f"{colors.BOLD}{colors.CYAN}jonq // triage{colors.NC}"]
    if report.invalid_lines:
        lines.append(f"{colors.BOLD_YELLOW}Partial report. See line diagnostics on stderr.{colors.NC}")

    denials = render_table([
        {"Source IP": group.src_ip, "Denials": group.count}
        for group in report.repeated_denials
    ], color=color)
    threshold_color = colors.BOLD_YELLOW if report.repeated_denials else colors.DIM
    if report.alerts:
        alert_count = sum(group.count for group in report.alerts)
        event_noun = "event" if alert_count == 1 else "events"
        type_noun = "type" if len(report.alerts) == 1 else "types"
        alert_summary = f"{alert_count:,} recorded alert {event_noun} across {len(report.alerts):,} alert {type_noun}"
    else:
        alert_summary = "No alert events in the valid records."
    lines.extend([
        "",
        f"{colors.BOLD}{colors.CYAN}{alert_summary}{colors.NC}",
        *_format_alerts(report.alerts, colors, source=source),
        "",
        f"{colors.CYAN}Firewall denials{colors.NC}",
        f"{report.denied_events} total denials · "
        f"{threshold_color}review threshold {report.min_denials} per source{colors.NC}",
        denials or "  No sources reached the threshold.",
        "",
        f"{report.events:,} valid {event_label}, {report.invalid_lines:,} invalid {invalid_label}",
    ])
    return "\n".join(lines)


def _format_alerts(alerts: list[AlertGroup], colors: _Colors, *, source: str | None) -> list[str]:
    if not alerts:
        return []

    rows = [
        (
            str(group.count),
            str(group.signature_id) if group.signature_id is not None else "-",
            json.dumps(group.signature) if group.signature is not None else "-",
            group.examples,
        )
        for group in alerts
    ]
    count_width = max(len("Count"), max(len(count) for count, _, _, _ in rows))
    id_width = max(len("Signature ID"), max(len(signature_id) for _, signature_id, _, _ in rows))
    header = f"  {'Count':>{count_width}}  {'Signature ID':<{id_width}}  Alert name"
    lines = [f"{colors.BOLD}{colors.CYAN}{header}{colors.NC}"]
    for index, (count, signature_id, signature, examples) in enumerate(rows):
        lines.append(f"  {count:>{count_width}}  {signature_id:<{id_width}}  {signature}")
        if examples:
            example = examples[0]
            timestamp = (
                json.dumps(example.timestamp)[1:-1]
                if example.timestamp is not None
                else "timestamp unavailable"
            )
            lines.append(f"    {colors.DIM}Input line {example.line} · {timestamp}{colors.NC}")
            if index == 0:
                command = input_line_command(source, example.line)
                if command:
                    lines.append(f"    {command}")
    return lines
