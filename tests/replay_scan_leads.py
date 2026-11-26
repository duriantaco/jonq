"""Replay a fixed set of local scan-lead evaluation cases."""

from __future__ import annotations

import argparse
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from tempfile import TemporaryDirectory


TESTS = Path(__file__).resolve().parent
MANIFEST = TESTS / "scan_lead_replay_cases.json"
LABEL_KEYS = ("label", "det_label")
ZEEK_FIELDS = ("uid", "id.orig_h", "id.resp_h", "proto", "conn_state")
PORT_FIELDS = ("id.orig_p", "id.resp_p")
JSON_NUMBER = re.compile(r"-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?", re.ASCII)


def file_sha256(path):
    checksum = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(65536), b""):
            checksum.update(block)
    return checksum.hexdigest()


def zeek_rows(path, *, prefix_bytes=None):
    """Read IoT-23 tab-separated rows and retain the input timestamp and UID."""
    with path.open("rb") as stream:
        fields = []
        combined_labels = False
        for line_no, raw in enumerate(stream, 1):
            if prefix_bytes is not None and not raw.endswith(b"\n"):
                break  # A byte range can end inside a record.
            if raw.startswith(b"#separator ") and raw.strip() != b"#separator \\x09":
                raise ValueError(f"{path.name}: only tab-separated Zeek files are supported")
            if raw.startswith(b"#fields\t"):
                fields = raw.decode("utf-8").rstrip("\r\n").split("\t")[1:]
                if not fields:
                    raise ValueError(f"{path.name}:{line_no}: empty Zeek field header")
                combined_labels = fields[-1].split() == ["tunnel_parents", "label", "detailed-label"]
                if combined_labels:
                    fields[-1:] = ["tunnel_parents", "label", "detailed-label"]
            if not raw.strip() or raw.startswith(b"#"):
                continue

            columns = raw.decode("utf-8").rstrip("\r\n").split("\t")
            if combined_labels:
                columns[-1:] = columns[-1].split(None, 2)
            if not fields or len(fields) != len(columns):
                raise ValueError(f"{path.name}:{line_no}: row does not match the Zeek field header")
            data = dict(zip(fields, columns))
            if "label" not in data or not ("det_label" in data or "detailed-label" in data):
                raise ValueError(f"{path.name}:{line_no}: expected IoT-23 label columns")
            record = {key: data[key] for key in ZEEK_FIELDS}
            record.update({key: int(data[key]) for key in PORT_FIELDS if data[key] != "-"})
            record["label"] = data["label"]
            record["det_label"] = data.get("det_label", data.get("detailed-label"))
            yield data["ts"], record


def ndjson_rows(path):
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            if line.strip():
                record = json.loads(line, parse_float=Decimal)
                yield str(record.pop("ts")), record


def write_inputs(source, case, detector_input, label_input):
    rows = (
        ndjson_rows(source) if case["format"] == "ndjson"
        else zeek_rows(source, prefix_bytes=case.get("prefix_bytes"))
    )
    with detector_input.open("w", encoding="utf-8", newline="\n") as detector:
        with label_input.open("w", encoding="utf-8", newline="\n") as labels:
            for timestamp, record in rows:
                if not JSON_NUMBER.fullmatch(timestamp):
                    raise ValueError(f"{source.name}: invalid Zeek timestamp {timestamp!r}")
                for output, values in (
                    (detector, {key: value for key, value in record.items() if key not in LABEL_KEYS}),
                    (labels, record),
                ):
                    fields = json.dumps(values, separators=(",", ":"), sort_keys=True)
                    output.write(f'{{"ts":{timestamp}' + ("," if values else "") + fields[1:] + "\n")


def check_expected(expected, actual, path):
    if isinstance(expected, dict) and isinstance(actual, dict):
        for key, value in expected.items():
            if key not in actual:
                raise ValueError(f"{path}.{key}: missing from the report")
            check_expected(value, actual[key], f"{path}.{key}")
    elif isinstance(expected, list) and isinstance(actual, list) and len(expected) == len(actual):
        for index, (want, found) in enumerate(zip(expected, actual)):
            check_expected(want, found, f"{path}[{index}]")
    elif expected != actual:
        raise ValueError(f"{path}: expected {expected!r}, got {actual!r}")


def replay(case, profile, captures, work, runs):
    source = TESTS / case["fixture"] if "fixture" in case else captures / case["filename"]
    if not source.is_file():
        raise ValueError(f"missing {source}. See {MANIFEST.name} for the source URL and range.")
    if "prefix_bytes" in case and source.stat().st_size != case["prefix_bytes"]:
        raise ValueError(f"{source.name}: expected exactly {case['prefix_bytes']} bytes")
    if file_sha256(source) != case["sha256"]:
        raise ValueError(f"{source.name}: input SHA-256 differs from the manifest")
    detector_input = work / "input.ndjson"
    label_input = work / "labels.ndjson"
    write_inputs(source, case, detector_input, label_input)
    command = [
        sys.executable, "-B", str(TESTS / "benchmark_connections.py"), str(detector_input),
        "--labels", str(label_input), "--scan-leads", "--window", str(profile["window_seconds"]),
        "--min-destinations", str(profile["min_destinations"]), "--runs", str(runs),
        "--target-detail", profile["target_detail"],
    ]
    for cidr in case["src_cidr"]:
        command.extend(("--src-cidr", cidr))
    completed = subprocess.run(command, capture_output=True, text=True)
    if completed.returncode:
        raise ValueError(f"{case['id']}: {completed.stderr.strip()}")
    report = json.loads(completed.stdout)
    check_expected(case["expected"], report, case["id"])
    report["input"] = source.name
    report.pop("labels_input", None)
    return {
        "case": case["id"],
        "dataset": case["dataset"],
        "source_sha256": case["sha256"],
        "report": report,
    }


def main():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    cases = {case["id"]: case for case in manifest["cases"]}
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--captures", type=Path, default=Path.cwd(), help="Directory with public log files")
    parser.add_argument("--case", action="append", choices=cases, help="Run only these cases")
    parser.add_argument("--runs", type=int, default=5, help="Timed runs after a warmup (default: 5)")
    args = parser.parse_args()
    if args.runs < 1:
        parser.error("--runs must be positive")

    try:
        with TemporaryDirectory(prefix="jonq-replay-") as temporary:
            results = [
                replay(cases[case], manifest["profile"], args.captures.resolve(), Path(temporary), args.runs)
                for case in dict.fromkeys(args.case or cases)
            ]
    except (ValueError, OSError, KeyError) as exc:
        parser.exit(1, f"Replay failed. {exc}\n")
    print(json.dumps({"profile": manifest["profile"], "results": results}, indent=2))


if __name__ == "__main__":
    main()
