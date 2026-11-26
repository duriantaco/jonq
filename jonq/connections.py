from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from ipaddress import IPv4Network, IPv6Network
import math
from typing import Literal

from jonq.connection_evidence import ConnectionDetails, connection_details
from jonq.constants import _Colors
from jonq.fanout import FanoutPeak, find_fanout
from jonq.ndjson import EventReader
from jonq.networks import canonical_ip, is_in_networks
from jonq.scan_leads import ScanLead, find_scan_leads, is_scan_observation
from jonq.table_utils import render_table


DEFAULT_WINDOW_SECONDS = 60
DEFAULT_MIN_DESTINATIONS = 10
_TEXT_DESTINATIONS = 8
_TEXT_CONVERSATIONS = 12
_TEXT_SCAN_LEADS = 12
_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)
_UNKNOWN_DETAILS = ConnectionDetails(None, None, "unknown", None)
_OUTCOME_LABELS = {
    "no_reply": "no reply observed",
    "rejected": "rejected",
    "established": "established",
    "unknown": "outcome unavailable",
}


@dataclass(frozen=True)
class Conversation:
    endpoint_a: str
    endpoint_b: str
    a_to_b: int
    b_to_a: int


@dataclass(frozen=True)
class ConnectionRecord:
    timestamp: Decimal
    dest_ip: str
    line: int
    log_format: str
    details: ConnectionDetails


@dataclass(frozen=True)
class ServiceEvidence:
    protocol: str | None
    dest_port: int | None
    outcomes: dict[str, int]


@dataclass(frozen=True)
class PeakEvidence:
    services: list[ServiceEvidence]
    records: list[ConnectionRecord]


@dataclass(frozen=True)
class ConnectionReport:
    connections: int
    ignored_records: int
    out_of_scope: int
    invalid_lines: int
    window_seconds: int
    min_destinations: int
    conversations: list[Conversation]
    fanout: list[FanoutPeak]
    evidence: dict[str, PeakEvidence]


@dataclass(frozen=True)
class ScanReport:
    connections: int
    ignored_records: int
    out_of_scope: int
    invalid_lines: int
    window_seconds: int
    min_destinations: int
    candidate_records: int
    scan_leads: list[ScanLead]


@dataclass(frozen=True)
class BaselineFinding:
    src_ip: str
    status: Literal["changed", "unseen_source", "within_baseline"]
    baseline_peak: int | None
    new_destinations: list[str]


@dataclass(frozen=True)
class BaselineComparison:
    connections: int
    invalid_lines: int
    available: bool
    findings: list[BaselineFinding]


def analyze_connections(
    lines: Iterable[bytes],
    *,
    window_seconds: int,
    min_destinations: int,
    src_networks: tuple[IPv4Network | IPv6Network, ...] = (),
    dst_networks: tuple[IPv4Network | IPv6Network, ...] = (),
    report_error: Callable[[int, str], None],
    include_evidence: bool = True,
    scan_leads_only: bool = False,
) -> ConnectionReport | ScanReport:
    reader = EventReader(lines, report_error, parse_float=Decimal)
    connections = 0
    ignored_records = 0
    out_of_scope = 0
    candidate_records = 0
    directions: Counter[tuple[str, str]] = Counter()
    by_source: dict[str, list[ConnectionRecord]] = defaultdict(list)

    for line_no, event in reader:
        try:
            connection = _parse_connection(event)
        except ValueError as exc:
            reader.reject(line_no, str(exc))
            continue
        if connection is None:
            ignored_records += 1
            continue

        timestamp, src, dst = connection
        if not is_in_networks(src, src_networks) or not is_in_networks(dst, dst_networks):
            out_of_scope += 1
            continue

        connections += 1
        zeek = "event_type" not in event
        details = connection_details(event, zeek=zeek) if include_evidence or scan_leads_only else _UNKNOWN_DETAILS
        if scan_leads_only:
            if not is_scan_observation(details):
                continue
            candidate_records += 1
        else:
            directions[src, dst] += 1
        by_source[src].append(ConnectionRecord(timestamp, dst, line_no, "zeek" if zeek else "eve", details))

    scope_counts = {
        "connections": connections,
        "ignored_records": ignored_records,
        "out_of_scope": out_of_scope,
        "invalid_lines": reader.invalid_lines,
        "window_seconds": window_seconds,
        "min_destinations": min_destinations,
    }
    if scan_leads_only:
        leads = find_scan_leads(
            by_source, window_seconds=window_seconds, min_destinations=min_destinations
        )
        return ScanReport(**scope_counts, candidate_records=candidate_records, scan_leads=leads)

    pairs = {(min(src, dst), max(src, dst)) for src, dst in directions}
    conversations = [
        Conversation(a, b, directions[a, b], directions[b, a] if a != b else 0)
        for a, b in pairs
    ]
    conversations.sort(key=lambda row: (-(row.a_to_b + row.b_to_a), row.endpoint_a, row.endpoint_b))
    fanout = find_fanout(
        {src: ((record.timestamp, record.dest_ip) for record in rows) for src, rows in by_source.items()},
        window_seconds=window_seconds,
        min_destinations=min_destinations,
    )
    evidence = {}
    if include_evidence:
        evidence = {peak.src_ip: _summarize_evidence(peak, by_source[peak.src_ip]) for peak in fanout}
    return ConnectionReport(
        **scope_counts,
        conversations=conversations,
        fanout=fanout,
        evidence=evidence,
    )


def _summarize_evidence(peak: FanoutPeak, connections: list[ConnectionRecord]) -> PeakEvidence:
    records = [
        record for record in connections if peak.window_start <= record.timestamp <= peak.window_end
    ]
    services: dict[tuple[str | None, int | None], Counter[str]] = defaultdict(Counter)
    for record in records:
        key = record.details.protocol, record.details.dest_port
        services[key][record.details.outcome] += 1
    summaries = [
        ServiceEvidence(protocol, port, dict(outcomes))
        for (protocol, port), outcomes in services.items()
    ]
    summaries.sort(key=lambda row: (
        -(row.outcomes.get("no_reply", 0) + row.outcomes.get("rejected", 0)),
        -sum(row.outcomes.values()), row.protocol or "", row.dest_port or 0,
    ))
    return PeakEvidence(summaries, records)


def compare_baseline(report: ConnectionReport, reference: ConnectionReport) -> BaselineComparison:
    available = reference.connections > 0 and not (report.invalid_lines or reference.invalid_lines)
    findings: list[BaselineFinding] = []
    if not available:
        return BaselineComparison(reference.connections, reference.invalid_lines, available, findings)

    unseen_destinations = {peak.src_ip: set(peak.destinations) for peak in report.fanout}
    for pair in reference.conversations:
        if pair.a_to_b and pair.endpoint_a in unseen_destinations:
            unseen_destinations[pair.endpoint_a].discard(pair.endpoint_b)
        if pair.b_to_a and pair.endpoint_b in unseen_destinations:
            unseen_destinations[pair.endpoint_b].discard(pair.endpoint_a)

    observed_peaks = {peak.src_ip: peak.unique_destinations for peak in reference.fanout}
    for peak in report.fanout:
        baseline_peak = observed_peaks.get(peak.src_ip)
        new_destinations = sorted(unseen_destinations[peak.src_ip])
        if baseline_peak is None:
            status = "unseen_source"
        elif peak.unique_destinations > baseline_peak or new_destinations:
            status = "changed"
        else:
            status = "within_baseline"
        findings.append(BaselineFinding(peak.src_ip, status, baseline_peak, new_destinations))

    return BaselineComparison(reference.connections, reference.invalid_lines, available, findings)


def _parse_connection(event: dict) -> tuple[Decimal, str, str] | None:
    if "event_type" not in event:
        src = _endpoint(event, "id.orig_h")
        dst = _endpoint(event, "id.resp_h")
        return _zeek_timestamp(event.get("ts")), src, dst

    event_type = event["event_type"]
    if not isinstance(event_type, str) or not event_type.strip():
        raise ValueError("expected an event_type string")
    if event_type.strip().casefold() != "flow":
        return None

    src = _endpoint(event, "src_ip")
    dst = _endpoint(event, "dest_ip")
    flow = event.get("flow")
    if flow is not None and not isinstance(flow, dict):
        raise ValueError("flow must be a JSON object")
    timestamp = event.get("timestamp")
    if flow is not None:
        timestamp = flow.get("start", timestamp)
    return _eve_timestamp(timestamp), src, dst


def _endpoint(event: dict, key: str) -> str:
    try:
        return canonical_ip(event.get(key))
    except ValueError:
        raise ValueError(f"expected a valid IP address in {key}") from None


def _zeek_timestamp(value: object) -> Decimal:
    if type(value) is int:
        value = Decimal(value)
    if isinstance(value, Decimal) and value.is_finite() and math.isfinite(float(value)):
        return value
    raise ValueError("expected a finite Zeek ts in Unix seconds")


def _eve_timestamp(value: object) -> Decimal:
    if isinstance(value, str):
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"
        elif len(value) >= 5 and value[-5] in "+-" and value[-4:].isdigit():
            value = value[:-2] + ":" + value[-2:]
        try:
            instant = datetime.fromisoformat(value)
            if instant.tzinfo is not None:
                delta = instant - _EPOCH
                seconds = delta.days * 86_400 + delta.seconds
                return Decimal(seconds) + Decimal(delta.microseconds).scaleb(-6)
        except (ValueError, OverflowError):
            pass
    raise ValueError("expected an EVE flow start or timestamp with a time zone")


def format_connections(
    report: ConnectionReport,
    baseline: BaselineComparison | None = None,
    *,
    color: bool = False,
) -> str:
    colors = _Colors(color)
    lines = [
        f"{colors.BOLD}jonq{colors.NC} {colors.CYAN}// connections{colors.NC}",
        f"{report.connections} connections, {report.out_of_scope} out of scope, "
        f"{report.ignored_records} other records, {report.invalid_lines} invalid lines",
    ]
    if report.invalid_lines or (baseline and baseline.invalid_lines):
        lines.append("Partial report. See line diagnostics on stderr.")
    if baseline:
        if baseline.available:
            lines.append(f"Compared with {baseline.connections} in-scope baseline connections.")
        elif report.invalid_lines or baseline.invalid_lines:
            if baseline.invalid_lines:
                lines.append(f"Baseline invalid lines {baseline.invalid_lines}")
            lines.append("Baseline comparison skipped because the input is incomplete.")
        else:
            lines.append("Baseline comparison unavailable. No baseline connections matched the scope.")

    lines.extend([
        "",
        *_format_findings(report, baseline, colors),
        "",
        f"{colors.BOLD}{colors.CYAN}IP conversations{colors.NC}",
    ])
    table = render_table(
        [
            {"Endpoint A": row.endpoint_a, "Endpoint B": row.endpoint_b,
             "A → B": row.a_to_b, "B → A": row.b_to_a}
            for row in report.conversations[:_TEXT_CONVERSATIONS]
        ],
        color=color,
    )
    lines.append(table or "  None")
    remaining = len(report.conversations) - _TEXT_CONVERSATIONS
    if remaining > 0:
        lines.append(f"  {remaining} more conversations in --format json.")
    return "\n".join(lines)


def format_scan_report(report: ScanReport, *, color: bool = False) -> str:
    colors = _Colors(color)
    lines = [
        f"{colors.BOLD}jonq{colors.NC} {colors.CYAN}// scan leads{colors.NC}",
        f"{report.connections} connections, {report.out_of_scope} out of scope, "
        f"{report.ignored_records} other records, {report.invalid_lines} invalid lines",
        f"{report.candidate_records} TCP records with rejection or no reply observed",
    ]
    if report.invalid_lines:
        lines.append("Partial report. See line diagnostics on stderr.")

    threshold = (
        f"{report.min_destinations} distinct destinations on the same TCP port "
        f"in {report.window_seconds} seconds"
    )
    if not report.scan_leads:
        return "\n".join([*lines, "", f"No scan leads reached {threshold} in the valid records."])

    lines.extend([
        "",
        f"{colors.BOLD}{colors.CYAN}Scan leads to review ({len(report.scan_leads)}){colors.NC}",
        f"Review threshold {threshold}",
    ])
    for lead in report.scan_leads[:_TEXT_SCAN_LEADS]:
        lines.extend([
            "",
            f"  {colors.BOLD_YELLOW}Review {lead.src_ip}{colors.NC} · TCP/{lead.dest_port} · "
            f"{lead.unique_destinations} distinct destinations",
            f"    {_format_time(lead.window_start)} to {_format_time(lead.window_end)}",
        ])
        service = ServiceEvidence("tcp", lead.dest_port, lead.outcomes)
        lines.extend(_format_evidence(PeakEvidence([service], lead.records), set(), colors))
        lines.append("    Destinations " + _preview_destinations(lead.destinations))
    remaining = len(report.scan_leads) - _TEXT_SCAN_LEADS
    if remaining > 0:
        lines.append(f"  {remaining} more scan leads in --format json.")
    return "\n".join(lines)


def _format_findings(
    report: ConnectionReport, baseline: BaselineComparison | None, colors: _Colors
) -> list[str]:
    if not report.connections:
        return ["No in-scope connections to assess."]

    threshold = f"{report.min_destinations} distinct destinations in {report.window_seconds} seconds"
    if not report.fanout:
        return [f"No source reached {threshold} in the valid records."]

    findings = {finding.src_ip: finding for finding in baseline.findings} if baseline else {}
    within_baseline = {
        finding.src_ip for finding in findings.values() if finding.status == "within_baseline"
    }
    review_count = len(report.fanout) - len(within_baseline)
    if review_count:
        heading = f"Sources to review ({review_count})"
    else:
        heading = "No qualifying sources differed from the baseline on these measures."
    lines = [f"{colors.BOLD}{colors.CYAN}{heading}{colors.NC}", f"Review threshold {threshold}"]

    for peak in sorted(report.fanout, key=lambda item: item.src_ip in within_baseline):
        finding = findings.get(peak.src_ip)
        if peak.src_ip in within_baseline:
            title = f"Within reference for breadth and peers {peak.src_ip}"
        else:
            title = f"{colors.BOLD_YELLOW}Review {peak.src_ip}{colors.NC}"
        lines.extend([
            "",
            f"  {title} · {peak.unique_destinations} distinct destinations",
            f"    {_format_time(peak.window_start)} to {_format_time(peak.window_end)}",
        ])
        if finding:
            lines.append(_format_baseline_finding(finding, peak.unique_destinations))
        evidence = report.evidence.get(peak.src_ip)
        if evidence and evidence.records:
            new_destinations = set(finding.new_destinations) if finding else set()
            lines.extend(_format_evidence(evidence, new_destinations, colors))
        lines.append("    Destinations " + _preview_destinations(peak.destinations))
        if finding and finding.new_destinations and finding.baseline_peak is not None:
            lines.append("    Absent from baseline " + _preview_destinations(finding.new_destinations))
    if review_count:
        lines.append("  Open the input lines above to inspect the recorded connections.")
    return lines


def _preview_destinations(destinations: list[str]) -> str:
    preview = ", ".join(destinations[:_TEXT_DESTINATIONS])
    remaining = len(destinations) - _TEXT_DESTINATIONS
    if remaining > 0:
        preview += f" (+{remaining} more in --format json)"
    return preview


def _format_evidence(
    evidence: PeakEvidence, new_destinations: set[str], colors: _Colors
) -> list[str]:
    priority = {"no_reply": 0, "rejected": 1, "established": 2, "unknown": 3}
    record = min(evidence.records, key=lambda row: (
        row.dest_ip not in new_destinations, priority[row.details.outcome], row.line,
    ))
    details = record.details
    outcome = _OUTCOME_LABELS[details.outcome]
    if details.state:
        log_format = "Zeek" if record.log_format == "zeek" else "EVE"
        outcome += f" ({log_format} {details.state})"
    lines = [
        f"    {colors.BOLD_YELLOW}Input line {record.line}{colors.NC} · {record.dest_ip} · "
        f"{_service_label(details.protocol, details.dest_port)} · {outcome}"
    ]
    displayed_services = 3
    for service in evidence.services[:displayed_services]:
        label = _service_label(service.protocol, service.dest_port)
        outcomes = ", ".join(
            f"{service.outcomes[outcome]} {_OUTCOME_LABELS[outcome]}"
            for outcome in _OUTCOME_LABELS
            if service.outcomes.get(outcome)
        )
        lines.append(
            f"    {colors.CYAN}{label}{colors.NC} · "
            f"{sum(service.outcomes.values())} records · {outcomes}"
        )
    if len(evidence.services) > displayed_services:
        remaining = len(evidence.services) - displayed_services
        lines.append(f"    {remaining} more transport and port groups in --format json.")

    return lines


def _service_label(protocol: str | None, port: int | None) -> str:
    transport = protocol.upper() if protocol else "Unknown transport"
    return f"{transport}/{port}" if port is not None else transport


def _format_baseline_finding(finding: BaselineFinding, current_peak: int) -> str:
    if finding.baseline_peak is None:
        return "    Baseline has no connections from this source."
    delta = current_peak - finding.baseline_peak
    change = f" ({delta:+d})" if delta else ""
    summary = f"    Baseline peak {finding.baseline_peak}{change}."
    if finding.status == "within_baseline":
        summary += " The baseline contains all shown destinations."
    return summary


def _format_time(seconds: Decimal) -> str:
    try:
        instant = datetime.fromtimestamp(float(seconds), tz=timezone.utc)
        return f"{instant.replace(tzinfo=None).isoformat(sep=' ')} UTC"
    except (ValueError, OverflowError, OSError):
        return f"{seconds} Unix seconds"
