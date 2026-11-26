"""Benchmark fresh jonq connections runs and score their windows against NDJSON labels."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from contextlib import nullcontext
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
from heapq import heappop, heappush
from ipaddress import ip_address, ip_network
from itertools import zip_longest
import json
from pathlib import Path
import platform
import re
from statistics import median
import subprocess
import sys
from time import perf_counter


ROOT = Path(__file__).resolve().parents[1]
LABELS = ("target", "benign", "other", "unlabeled")
WINDOW_RESULTS = ("target_in_window", "benign_only", "unconfirmed")
SCAN_LABELS = ("target", "benign", "other", "unknown")
SCAN_WINDOW_RESULTS = (
    "target_threshold_met",
    "target_present_below_threshold",
    "benign_only",
    "known_other_without_target",
    "unconfirmed",
)
OUTSIDE_OBSERVATION_RULE = ("not_tcp", "missing_destination_port", "no_failed_outcome")
DISPLAYED_EVIDENCE = re.compile(r"^ +Input line ([0-9]+) · ", re.MULTILINE)
EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)
LABEL_KEYS = {"label", "det_label"}


@dataclass(frozen=True)
class EvidenceLabel:
    source: str
    label: str
    destination: str | None = None
    scan_port: int | None = None
    scan_label: str | None = None
    timestamp: Decimal | None = None


@dataclass
class ScanIndex:
    candidate_labels: Counter[str] = field(default_factory=lambda: Counter(dict.fromkeys(SCAN_LABELS, 0)))
    unknown_by_group: Counter[tuple[str, int]] = field(default_factory=Counter)
    target_events: dict[tuple[str, int], list[tuple[Decimal, str]]] = field(
        default_factory=lambda: defaultdict(list)
    )
    excluded_targets: Counter[str] = field(
        default_factory=lambda: Counter(dict.fromkeys(OUTSIDE_OBSERVATION_RULE, 0))
    )
    first_seen: Decimal | None = None
    last_seen: Decimal | None = None


@dataclass
class CaptureIndex:
    records: int
    sha256: str
    labels: dict[str, int]
    evidence: dict[int, EvidenceLabel]
    target_sources: set[str]
    scan: ScanIndex | None
    labels_sha256: str | None


def run_connections(command):
    started = perf_counter()
    result = subprocess.run(command, cwd=ROOT, stdin=subprocess.DEVNULL, capture_output=True)
    elapsed = perf_counter() - started
    if result.returncode:
        diagnostics = result.stderr.decode(errors="replace").strip()
        raise ValueError(f"jonq exited with status {result.returncode}. {diagnostics[:1000]}")
    return elapsed, result.stdout


def peak_child_rss_bytes():
    if sys.platform not in {"darwin", "linux"}:
        return None
    import resource

    peak = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    return peak if sys.platform == "darwin" else peak * 1024


def record_label(record, target_details):
    label = record.get("label")
    label = label.strip().casefold() if isinstance(label, str) else ""
    if label in {"", "-"}:
        return "unlabeled"
    if label == "benign":
        return "benign"
    if label == "malicious":
        detail = record.get("det_label")
        if not target_details or (isinstance(detail, str) and detail in target_details):
            return "target"
    return "other"


def scan_label(record, label):
    if label == "unlabeled":
        return "unknown"
    if label != "other":
        return label
    # An explicit, different malicious category is known. A missing detail or
    # unfamiliar source label cannot establish that a record is out of scope.
    detail = record.get("det_label")
    if record["label"].strip().casefold() == "malicious" and isinstance(detail, str):
        if detail.strip() not in {"", "-"}:
            return "other"
    return "unknown"


def scan_observation_port(record, *, zeek):
    """Apply the documented observation rule independently of the analyzer."""
    proto = record.get("proto")
    if not isinstance(proto, str) or proto.strip().lower() != "tcp":
        return None, "not_tcp"
    port = record.get("id.resp_p" if zeek else "dest_port")
    if type(port) is not int or not 0 <= port <= 65535:
        return None, "missing_destination_port"

    if zeek:
        state = record.get("conn_state")
        failed = isinstance(state, str) and state.isascii() and state.strip().upper() in {"S0", "REJ"}
    else:
        flow = record.get("flow") or {}
        state = flow.get("state")
        state = state.strip().lower() if isinstance(state, str) and state.isascii() else None
        packets = flow.get("pkts_toclient")
        failed = type(packets) is int and packets == 0 and state not in {"established", "bypassed"}
    return (port, None) if failed else (None, "no_failed_outcome")


def observation_time(record, *, zeek):
    if zeek:
        return Decimal(record["ts"])
    timestamp = (record.get("flow") or {}).get("start", record.get("timestamp"))
    if timestamp.endswith("Z"):
        timestamp = timestamp[:-1] + "+00:00"
    elif len(timestamp) >= 5 and timestamp[-5] in "+-" and timestamp[-4:].isdigit():
        timestamp = timestamp[:-2] + ":" + timestamp[-2:]
    delta = datetime.fromisoformat(timestamp) - EPOCH
    seconds = delta.days * 86_400 + delta.seconds
    return Decimal(seconds) + Decimal(delta.microseconds).scaleb(-6)


def same_json_values(left, right):
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return left.keys() == right.keys() and all(
            same_json_values(value, right[key]) for key, value in left.items()
        )
    if isinstance(left, list):
        return len(left) == len(right) and all(
            same_json_values(item, other) for item, other in zip(left, right)
        )
    return left == right


def input_records(source, labels_source, digest, labels_digest, *, scan_leads):
    if labels_source is not None:
        pairs = zip_longest(source, labels_source)
    else:
        pairs = ((raw, raw) for raw in source)
    for line, (raw, labeled) in enumerate(pairs, 1):
        if raw is None or labeled is None:
            raise ValueError(f"input and labeled copy have different lengths at line {line}")
        digest.update(raw)
        if labels_digest is not None:
            labels_digest.update(labeled)
        is_blank = not raw.strip(b" \t\r\n")
        if is_blank != (not labeled.strip(b" \t\r\n")):
            raise ValueError(f"input and labeled copy disagree on a blank line at line {line}")
        if is_blank:
            continue

        record = json.loads(labeled, parse_float=Decimal if scan_leads or labels_source is not None else float)
        if labels_source is not None:
            detector_record = json.loads(raw, parse_float=Decimal)
            if not isinstance(record, dict) or not isinstance(detector_record, dict):
                raise ValueError(f"input and labeled copy must contain JSON objects at line {line}")
            non_label_fields = {key: value for key, value in record.items() if key not in LABEL_KEYS}
            if LABEL_KEYS.intersection(detector_record):
                raise ValueError(f"detector input contains label fields at line {line}")
            if not same_json_values(detector_record, non_label_fields):
                raise ValueError(f"input and labeled copy have different event fields at line {line}")
        yield line, record


def index_input(path, networks, target_details, evidence_lines, *, scan_leads=False, labels_path=None):
    digest = hashlib.sha256()
    labels_digest = hashlib.sha256() if labels_path is not None else None
    total = 0
    counts = Counter(dict.fromkeys(LABELS, 0))
    labels_by_line = {}
    target_sources = set()
    scan = ScanIndex() if scan_leads else None
    labels_context = labels_path.open("rb") if labels_path is not None else nullcontext()
    with labels_context as labels_source, path.open("rb") as source:
        for line, record in input_records(source, labels_source, digest, labels_digest, scan_leads=scan_leads):
            total += 1
            zeek = "event_type" not in record
            if not zeek and record["event_type"].strip().casefold() != "flow":
                continue
            source_ip = ip_address(record["id.orig_h" if zeek else "src_ip"].strip())
            if networks and not any(source_ip in network for network in networks):
                continue

            label = record_label(record, target_details)
            counts[label] += 1
            src = str(source_ip)
            if label == "target":
                target_sources.add(src)
            port, candidate_label, destination, timestamp = None, None, None, None
            if scan is not None:
                observed_at = observation_time(record, zeek=zeek)
                if scan.first_seen is None or observed_at < scan.first_seen:
                    scan.first_seen = observed_at
                if scan.last_seen is None or observed_at > scan.last_seen:
                    scan.last_seen = observed_at
                port, excluded_reason = scan_observation_port(record, zeek=zeek)
                if port is None:
                    if label == "target":
                        scan.excluded_targets[excluded_reason] += 1
                else:
                    candidate_label = scan_label(record, label)
                    scan.candidate_labels[candidate_label] += 1
                    group = (src, port)
                    if candidate_label == "unknown":
                        scan.unknown_by_group[group] += 1
                    if candidate_label == "target" or line in evidence_lines:
                        destination = str(ip_address(record["id.resp_h" if zeek else "dest_ip"].strip()))
                        timestamp = observed_at
                    if candidate_label == "target":
                        scan.target_events[group].append((timestamp, destination))
            if line in evidence_lines:
                labels_by_line[line] = EvidenceLabel(src, label, destination, port, candidate_label, timestamp)

    return CaptureIndex(
        total, digest.hexdigest(), dict(counts), labels_by_line, target_sources, scan,
        labels_digest.hexdigest() if labels_digest is not None else None,
    )


def displayed_evidence_lines(command, evidence_lines):
    if not evidence_lines:
        return set()
    command = command.copy()
    command[command.index("--format") + 1] = "text"
    _, output = run_connections([*command, "--no-color"])
    displayed = [int(line) for line in DISPLAYED_EVIDENCE.findall(output.decode("utf-8"))]
    if not displayed or len(displayed) != len(set(displayed)) or set(displayed) - evidence_lines:
        raise ValueError("jonq text showed missing, repeated, or unknown evidence lines")
    return set(displayed)


def scan_window_details(peak, evidence, report):
    if any(item.scan_port != peak["dest_port"] for item in evidence):
        raise ValueError("scan lead refers to an input line outside its TCP observation group")
    peers = {item.destination for item in evidence}
    if peers != set(peak["destinations"]) or len(peers) != peak["unique_destinations"]:
        raise ValueError("scan lead destinations do not match the input evidence")
    start = min(item.timestamp for item in evidence)
    end = max(item.timestamp for item in evidence)
    if end - start > report["window_seconds"] or (float(start), float(end)) != (
        peak["window_start"], peak["window_end"]
    ):
        raise ValueError("scan lead window does not match the original timestamps")

    counts = Counter(dict.fromkeys(SCAN_LABELS, 0))
    counts.update(item.scan_label for item in evidence)
    target_peers = {item.destination for item in evidence if item.scan_label == "target"}
    if len(target_peers) >= report["min_destinations"]:
        outcome = "target_threshold_met"
    elif target_peers:
        outcome = "target_present_below_threshold"
    elif counts["benign"] == len(evidence):
        outcome = "benign_only"
    elif counts["unknown"]:
        outcome = "unconfirmed"
    else:
        outcome = "known_other_without_target"
    return {
        "scan_labels": dict(counts),
        "distinct_target_destinations": len(target_peers),
        "scan_assessment": outcome,
    }


def assess_windows(report, labels_by_line, target_sources, displayed_lines):
    baseline = report.get("baseline")
    within_baseline = set()
    if baseline and baseline["available"]:
        within_baseline = {
            finding["src_ip"] for finding in baseline["findings"]
            if finding["status"] == "within_baseline"
        }

    review = Counter(dict.fromkeys(WINDOW_RESULTS, 0))
    excluded = Counter(dict.fromkeys(WINDOW_RESULTS, 0))
    peak_sources = set()
    hit_sources = set()
    windows = []
    remaining_displayed = displayed_lines.copy()
    for peak, records in evidence_windows(report):
        src = peak["src_ip"]
        lines = [record["line"] for record in records]
        if not lines or len(set(lines)) != len(lines):
            raise ValueError(f"missing or duplicate evidence lines for {src}")
        counts = Counter(dict.fromkeys(LABELS, 0))
        labeled_evidence = []
        for line in lines:
            evidence = labels_by_line.get(line)
            if evidence is None or evidence.source != src:
                raise ValueError(f"invalid evidence reference for {src}, input line {line}")
            counts[evidence.label] += 1
            labeled_evidence.append(evidence)

        peak_sources.add(src)
        if counts["target"]:
            hit_sources.add(src)
            assessment = "target_in_window"
        elif counts["benign"] == len(lines):
            assessment = "benign_only"
        else:
            assessment = "unconfirmed"
        suppressed = src in within_baseline
        (excluded if suppressed else review)[assessment] += 1
        shown = remaining_displayed.intersection(lines)
        if len(shown) > 1:
            raise ValueError(f"jonq text displayed multiple first evidence lines for {src}")
        first_line = next(iter(shown), None)
        remaining_displayed.difference_update(shown)
        first_label = None
        if first_line is not None:
            first = labels_by_line[first_line]
            first_label = first.scan_label if "dest_port" in peak else first.label
        window = {
            "src_ip": src,
            "window_start": peak["window_start"],
            "window_end": peak["window_end"],
            "unique_destinations": peak["unique_destinations"],
            "first_input_line": first_line,
            "first_displayed_evidence_label": first_label,
            "earliest_input_line": min(lines),
            "labels": dict(counts),
            "assessment": assessment,
            "within_baseline": suppressed,
        }
        if "dest_port" in peak:
            window["dest_port"] = peak["dest_port"]
            window.update(scan_window_details(peak, labeled_evidence, report))
        windows.append(window)

    if remaining_displayed:
        raise ValueError("jonq text displayed evidence outside the reported windows")
    return {
        "target_sources": len(target_sources),
        "target_sources_without_peak": sorted(target_sources - peak_sources),
        "target_sources_with_peak_missing_target": sorted((target_sources & peak_sources) - hit_sources),
        "review": dict(review),
        "within_baseline": dict(excluded),
        "windows": windows,
    }


def peak_distinct_targets(events, window_seconds):
    """Compute target-only breadth by tracking the latest live event for each peer."""
    latest = {}
    expiration = []
    peak = 0
    for timestamp, destination in sorted(events):
        while expiration and timestamp - expiration[0][0] > window_seconds:
            expired_time, expired_peer = heappop(expiration)
            if latest.get(expired_peer) == expired_time:
                del latest[expired_peer]
        latest[destination] = timestamp
        heappush(expiration, (timestamp, destination))
        peak = max(peak, len(latest))
    return peak


def assess_scan_groups(report, index, windows):
    if sum(index.candidate_labels.values()) != report["candidate_records"]:
        raise ValueError("labeled input pass and jonq disagree on eligible scan observations")
    selected = {(window["src_ip"], window["dest_port"]): window for window in windows}
    if len(selected) != len(windows):
        raise ValueError("jonq reported duplicate scan groups")

    threshold = report["min_destinations"]
    group_outcomes = Counter()
    target_groups = []
    for group, events in sorted(index.target_events.items()):
        peak = peak_distinct_targets(events, report["window_seconds"])
        window = selected.get(group)
        selected_breadth = window["distinct_target_destinations"] if window else None
        if selected_breadth is not None and selected_breadth > peak:
            raise ValueError("selected scan evidence exceeds the independent target peak")
        if peak < threshold:
            outcome = "known_targets_below_threshold"
        elif window is None:
            outcome = "eligible_without_lead"
        elif selected_breadth < threshold:
            outcome = "eligible_selected_window_below_target_threshold"
        else:
            outcome = "eligible_selected_target_window"
        group_outcomes[outcome] += 1
        target_groups.append({
            "src_ip": group[0],
            "dest_port": group[1],
            "target_observations": len(events),
            "unknown_label_observations": index.unknown_by_group[group],
            "peak_distinct_target_destinations": peak,
            "selected_window_distinct_target_destinations": selected_breadth,
            "outcome": outcome,
        })

    hits = group_outcomes["eligible_selected_target_window"]
    missing = group_outcomes["eligible_without_lead"]
    wrong_window = group_outcomes["eligible_selected_window_below_target_threshold"]
    eligible = hits + missing + wrong_window
    findings = Counter(dict.fromkeys(SCAN_WINDOW_RESULTS, 0))
    displayed_labels = Counter(dict.fromkeys((*SCAN_LABELS, "not_displayed"), 0))
    for window in windows:
        findings[window["scan_assessment"]] += 1
        displayed_labels[window["first_displayed_evidence_label"] or "not_displayed"] += 1
    duration = 0.0
    if index.first_seen is not None and index.last_seen is not None:
        duration = float(index.last_seen - index.first_seen)
    return {
        "candidate_labels": dict(index.candidate_labels),
        "candidate_groups_with_unknown_labels": len(index.unknown_by_group),
        "target_records_outside_observation_rule": dict(index.excluded_targets),
        "eligible_target_groups": eligible,
        "eligible_target_groups_with_selected_target_window": hits,
        "eligible_target_groups_without_lead": missing,
        "eligible_target_groups_with_selected_window_below_target_threshold": wrong_window,
        "eligible_target_group_coverage": hits / eligible if eligible else None,
        "known_target_groups_below_threshold": group_outcomes["known_targets_below_threshold"],
        "selected_windows": dict(findings),
        "observed_scope_seconds": duration,
        "benign_only_leads_per_observed_hour": findings["benign_only"] * 3600 / duration if duration else None,
        "first_displayed_evidence_labels": dict(displayed_labels),
        "target_groups": target_groups,
    }


def evidence_windows(report):
    if "scan_leads" in report:
        for lead in report["scan_leads"]:
            yield lead, lead["records"]
    else:
        for peak in report["fanout"]:
            yield peak, report["evidence"][peak["src_ip"]]["records"]


def benchmark(args):
    if any(path is not None and not path.is_file() for path in (args.input, args.baseline, args.labels)):
        raise ValueError("input, baseline, and labels must be local NDJSON files")
    networks = [ip_network(value.strip(), strict=True) for value in args.src_cidr]
    command = [sys.executable, "-B", "-m", "jonq", "connections", str(args.input), "--format", "json"]
    if args.scan_leads:
        command.append("--scan-leads")
    for value in args.src_cidr:
        command.extend(["--src-cidr", value])
    for flag, value in (
        ("--window", args.window), ("--min-destinations", args.min_destinations),
        ("--baseline", args.baseline),
    ):
        if value is not None:
            command.extend([flag, str(value)])

    _, output = run_connections(command)
    output_bytes = len(output)
    expected = hashlib.sha256(output).digest()
    del output

    times = []
    for _ in range(args.runs):
        elapsed, output = run_connections(command)
        if hashlib.sha256(output).digest() != expected:
            raise ValueError("jonq returned different JSON across benchmark runs")
        times.append(elapsed)
    peak_rss = peak_child_rss_bytes()

    report = json.loads(output)
    del output
    baseline = report.get("baseline")
    if report["invalid_lines"] or (baseline and baseline["invalid_lines"]):
        raise ValueError("jonq reported invalid input lines")

    evidence_lines = {record["line"] for _, records in evidence_windows(report) for record in records}
    displayed = displayed_evidence_lines(command, evidence_lines)
    index = index_input(
        args.input, networks, set(args.target_detail), evidence_lines,
        scan_leads=args.scan_leads, labels_path=args.labels,
    )
    total = index.records
    scoped = report["connections"]
    if total != scoped + report["out_of_scope"] + report["ignored_records"]:
        raise ValueError("jonq record counts do not match the input")
    if sum(index.labels.values()) != scoped:
        raise ValueError("labeled input pass and jonq disagree on the source scope")

    typical = median(times)
    assessment = assess_windows(report, index.evidence, index.target_sources, displayed)
    result = {
        "input": str(args.input),
        "input_sha256": index.sha256,
        "input_bytes": args.input.stat().st_size,
        "accepted_records": total,
        "in_scope_connections": scoped,
        "out_of_scope_connections": report["out_of_scope"],
        "ignored_records": report["ignored_records"],
        "src_cidr": args.src_cidr,
        "window_seconds": report["window_seconds"],
        "min_destinations": report["min_destinations"],
        "target_label": "Malicious",
        "target_detail": args.target_detail,
        "scoped_labels": index.labels,
        "assessment": assessment,
        "performance": {
            "python_version": platform.python_version(),
            "platform": platform.platform(),
            "runs": args.runs,
            "median_seconds": typical,
            "min_seconds": min(times),
            "max_seconds": max(times),
            "current_records_per_second": total / typical,
            "json_output_bytes": output_bytes,
            "peak_child_rss_bytes_including_warmup": peak_rss,
        },
    }
    if args.labels is not None:
        result["labels_input"] = str(args.labels)
        result["labels_input_sha256"] = index.labels_sha256
    if baseline is not None:
        result["baseline"] = {
            "input": str(args.baseline),
            "in_scope_connections": baseline["connections"],
            "available": baseline["available"],
        }
    if args.scan_leads:
        result["candidate_records"] = report["candidate_records"]
        result["scan_assessment"] = assess_scan_groups(report, index.scan, assessment["windows"])
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=lambda value: Path(value).resolve())
    parser.add_argument("--src-cidr", action="append", default=[], metavar="HOST_OR_CIDR")
    parser.add_argument("--window", type=int, metavar="SECONDS", help="Override the jonq window")
    parser.add_argument("--min-destinations", type=int, help="Override the jonq threshold")
    parser.add_argument("--runs", type=int, default=5, help="Measured runs after one warmup (default: 5)")
    parser.add_argument(
        "--labels", type=lambda value: Path(value).resolve(), metavar="FILE",
        help="Use an aligned labeled NDJSON copy for scoring and send only unlabeled input to jonq.",
    )
    parser.add_argument(
        "--target-detail", action="append", default=[], metavar="LABEL",
        help="Only target malicious records with this exact det_label. Repeat to match more labels.",
    )
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--baseline", type=lambda value: Path(value).resolve())
    modes.add_argument("--scan-leads", action="store_true", help="Benchmark scan-specific windows")
    args = parser.parse_args()
    if args.runs < 1:
        parser.error("--runs must be positive")
    try:
        result = benchmark(args)
    except (ValueError, OSError, LookupError) as exc:
        parser.exit(1, f"Benchmark failed. {exc}\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
