from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Iterable
from dataclasses import dataclass
import json

from jonq.constants import _Colors
from jonq.ndjson import EventReader
from jonq.networks import canonical_ip
from jonq.table_utils import render_table


DEFAULT_MIN_DENIALS = 5
_DENIAL_ACTIONS = {
    "block", "blocked", "deny", "denied", "drop", "dropped", "reject", "rejected",
}


@dataclass
class AlertGroup:
    signature_id: int | None
    signature: str | None
    count: int = 0


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
    """Read NDJSON in one pass and retain counts by signature and source IP."""
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
                _count_alert(event.get("alert"), alerts)
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


def _count_alert(value: object, alerts: dict[int | str, AlertGroup]) -> None:
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


def _denial_source(value: object) -> str:
    try:
        return canonical_ip(value)
    except ValueError:
        raise ValueError("denied firewall event requires a valid src_ip") from None


def format_triage(report: TriageReport, *, color: bool = False) -> str:
    colors = _Colors(color)
    event_label = "event" if report.events == 1 else "events"
    invalid_label = "line" if report.invalid_lines == 1 else "lines"
    lines = [
        f"{colors.BOLD}{colors.CYAN}jonq // triage{colors.NC}",
        f"{report.events} valid {event_label}, {report.invalid_lines} invalid {invalid_label}",
    ]
    if report.invalid_lines:
        lines.append(f"{colors.BOLD_YELLOW}Partial report. See line diagnostics on stderr.{colors.NC}")

    denials = render_table([
        {"Source IP": group.src_ip, "Denials": group.count}
        for group in report.repeated_denials
    ], color=color)
    threshold_color = colors.BOLD_YELLOW if report.repeated_denials else colors.DIM
    lines.extend([
        "",
        f"{colors.CYAN}Recorded alert signatures{colors.NC}",
        *_format_alerts(report.alerts, colors),
        "",
        f"{colors.CYAN}Firewall denials{colors.NC}",
        f"{report.denied_events} total denials · "
        f"{threshold_color}review threshold {report.min_denials} per source{colors.NC}",
        denials or "  No sources reached the threshold.",
    ])
    return "\n".join(lines)


def _format_alerts(alerts: list[AlertGroup], colors: _Colors) -> list[str]:
    if not alerts:
        return ["  No alerts in valid records."]

    rows = [
        (
            str(group.count),
            str(group.signature_id) if group.signature_id is not None else "-",
            json.dumps(group.signature) if group.signature is not None else "-",
        )
        for group in alerts
    ]
    count_width = max(len("Count"), max(len(count) for count, _, _ in rows))
    id_width = max(len("Signature ID"), max(len(signature_id) for _, signature_id, _ in rows))
    header = f"  {'Count':>{count_width}}  {'Signature ID':<{id_width}}  Signature"
    return [
        f"{colors.BOLD}{colors.CYAN}{header}{colors.NC}",
        *(
            f"  {count:>{count_width}}  {signature_id:<{id_width}}  {signature}"
            for count, signature_id, signature in rows
        ),
    ]
