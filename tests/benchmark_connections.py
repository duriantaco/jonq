"""Benchmark fresh jonq connections runs and score their windows against NDJSON labels."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
from ipaddress import ip_address, ip_network
import json
from pathlib import Path
import platform
from statistics import median
import subprocess
import sys
from time import perf_counter


ROOT = Path(__file__).resolve().parents[1]
LABELS = ("target", "benign", "other", "unlabeled")
WINDOW_RESULTS = ("target_in_window", "benign_only", "unconfirmed")


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


def index_input(path, networks, target_details, evidence_lines):
    digest = hashlib.sha256()
    total = 0
    counts = Counter(dict.fromkeys(LABELS, 0))
    labels_by_line = {}
    target_sources = set()
    with path.open("rb") as source:
        for line, raw in enumerate(source, 1):
            digest.update(raw)
            if not raw.strip(b" \t\r\n"):
                continue
            total += 1
            record = json.loads(raw)
            if "event_type" in record:
                if record["event_type"].strip().casefold() != "flow":
                    continue
                source_ip = ip_address(record["src_ip"].strip())
            else:
                source_ip = ip_address(record["id.orig_h"].strip())
            if networks and not any(source_ip in network for network in networks):
                continue

            label = record_label(record, target_details)
            counts[label] += 1
            src = str(source_ip)
            if label == "target":
                target_sources.add(src)
            if line in evidence_lines:
                labels_by_line[line] = src, label

    return total, digest.hexdigest(), dict(counts), labels_by_line, target_sources


def assess_windows(report, labels_by_line, target_sources):
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
    for peak, records in evidence_windows(report):
        src = peak["src_ip"]
        lines = [record["line"] for record in records]
        if not lines or len(set(lines)) != len(lines):
            raise ValueError(f"missing or duplicate evidence lines for {src}")
        counts = Counter(dict.fromkeys(LABELS, 0))
        for line in lines:
            evidence = labels_by_line.get(line)
            if evidence is None or evidence[0] != src:
                raise ValueError(f"invalid evidence reference for {src}, input line {line}")
            counts[evidence[1]] += 1

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
        window = {
            "src_ip": src,
            "window_start": peak["window_start"],
            "window_end": peak["window_end"],
            "unique_destinations": peak["unique_destinations"],
            "first_input_line": min(lines),
            "labels": dict(counts),
            "assessment": assessment,
            "within_baseline": suppressed,
        }
        if "dest_port" in peak:
            window["dest_port"] = peak["dest_port"]
        windows.append(window)

    return {
        "target_sources": len(target_sources),
        "target_sources_without_peak": sorted(target_sources - peak_sources),
        "target_sources_with_peak_missing_target": sorted((target_sources & peak_sources) - hit_sources),
        "review": dict(review),
        "within_baseline": dict(excluded),
        "windows": windows,
    }


def evidence_windows(report):
    if "scan_leads" in report:
        for lead in report["scan_leads"]:
            yield lead, lead["records"]
    else:
        for peak in report["fanout"]:
            yield peak, report["evidence"][peak["src_ip"]]["records"]


def benchmark(args):
    if not args.input.is_file() or (args.baseline is not None and not args.baseline.is_file()):
        raise ValueError("input and baseline must be local NDJSON files")
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
    total, digest, scoped_labels, labels_by_line, target_sources = index_input(
        args.input, networks, set(args.target_detail), evidence_lines
    )
    scoped = report["connections"]
    if total != scoped + report["out_of_scope"] + report["ignored_records"]:
        raise ValueError("jonq record counts do not match the input")
    if sum(scoped_labels.values()) != scoped:
        raise ValueError("labeled input pass and jonq disagree on the source scope")

    typical = median(times)
    result = {
        "input": str(args.input),
        "input_sha256": digest,
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
        "scoped_labels": scoped_labels,
        "assessment": assess_windows(report, labels_by_line, target_sources),
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
    if baseline is not None:
        result["baseline"] = {
            "input": str(args.baseline),
            "in_scope_connections": baseline["connections"],
            "available": baseline["available"],
        }
    if args.scan_leads:
        result["candidate_records"] = report["candidate_records"]
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=lambda value: Path(value).resolve())
    parser.add_argument("--src-cidr", action="append", default=[], metavar="HOST_OR_CIDR")
    parser.add_argument("--window", type=int, metavar="SECONDS", help="Override the jonq window")
    parser.add_argument("--min-destinations", type=int, help="Override the jonq threshold")
    parser.add_argument("--runs", type=int, default=5, help="Measured runs after one warmup (default: 5)")
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
