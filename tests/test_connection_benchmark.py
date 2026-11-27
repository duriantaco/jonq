import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest


SCRIPT = Path(__file__).with_name("benchmark_connections.py")
SOURCE = "192.0.2.10"
TARGET_DETAIL = "PartOfAHorizontalPortScan"
TARGET = {"label": "Malicious", "det_label": TARGET_DETAIL}
BENIGN = {"label": "Benign"}


def observation(port, peer, *, timestamp=0, outcome="S0", label=TARGET, proto="tcp"):
    return {
        "ts": timestamp, "id.orig_h": SOURCE, "id.resp_h": f"198.51.100.{peer}",
        "id.resp_p": port, "proto": proto, "conn_state": outcome, **label,
    }


def write_capture(path, rows):
    path.write_text("".join(json.dumps(row) + "\n" if row is not None else "\n" for row in rows))


def write_label_blind_pair(tmp_path, rows):
    detector = tmp_path / "detector.ndjson"
    labeled = tmp_path / "labeled.ndjson"
    write_capture(labeled, rows)
    write_capture(detector, [
        {key: value for key, value in row.items() if key not in {"label", "det_label"}}
        if row is not None else None
        for row in rows
    ])
    return detector, labeled


def run_benchmark(input_path, *args):
    return subprocess.run(
        [
            sys.executable, "-B", str(SCRIPT), str(input_path),
            "--runs", "1", "--src-cidr", SOURCE, "--window", "60",
            "--target-detail", TARGET_DETAIL, *args,
        ],
        capture_output=True,
        text=True,
        timeout=15,
        cwd=SCRIPT.parents[1],
    )


def test_scan_metrics_distinguish_weak_overlap_and_target_qualified_groups(tmp_path):
    rows = [
        # This group qualifies on target records, but the wider later peak has
        # only one target peer amid benign connections.
        *[observation(22, peer) for peer in range(1, 11)],
        observation(22, 1, timestamp=1000),
        *[observation(22, peer, timestamp=1001, label=BENIGN) for peer in range(2, 13)],
        None,
        # Exactly 60 seconds apart. The text prioritizes the later S0 record
        # with missing category over the earlier rejected target records.
        *[observation(443, peer, timestamp=500.125, outcome="REJ") for peer in range(1, 10)],
        observation(443, 10, timestamp=560.125, outcome="REJ"),
        observation(443, 10, timestamp=560.125, label={"label": "Malicious"}),
        observation(80, 1, timestamp=1000),
        observation(80, 2, timestamp=1000, label={}),
        *[observation(81, peer, label=BENIGN) for peer in range(1, 11)],
        *[
            observation(82, peer, label={"label": "Malicious", "det_label": "C&C"})
            for peer in range(1, 11)
        ],
        *[observation(83, peer, label={}) for peer in range(1, 11)],
        observation(5353, 1, proto="udp"),
        observation(993, 1, outcome="SF"),
        observation(None, 1),
    ]
    detector, labeled = write_label_blind_pair(tmp_path, rows)

    completed = run_benchmark(detector, "--labels", str(labeled), "--scan-leads", "--min-destinations", "10")
    assert completed.returncode == 0, completed.stderr
    result = json.loads(completed.stdout)
    assert result["input_sha256"] == hashlib.sha256(detector.read_bytes()).hexdigest()
    assert result["labels_input_sha256"] == hashlib.sha256(labeled.read_bytes()).hexdigest()
    scan = result["scan_assessment"]
    assert scan["eligible_target_groups"] == 2
    assert scan["eligible_target_groups_with_selected_target_window"] == 1
    assert scan["eligible_target_groups_with_selected_window_below_target_threshold"] == 1
    assert scan["eligible_target_groups_without_lead"] == 0
    assert scan["eligible_target_group_coverage"] == 0.5
    assert scan["known_target_groups_below_threshold"] == 1
    assert scan["candidate_groups_with_unknown_labels"] == 3
    assert scan["target_records_outside_observation_rule"] == {
        "not_tcp": 1, "missing_destination_port": 1, "no_failed_outcome": 1,
    }
    assert scan["selected_windows"] == {
        "target_threshold_met": 1, "target_present_below_threshold": 1,
        "benign_only": 1, "known_other_without_target": 1, "unconfirmed": 1,
    }
    assert result["assessment"]["review"]["target_in_window"] == 2
    windows = {window["dest_port"]: window for window in result["assessment"]["windows"]}
    assert windows[22]["distinct_target_destinations"] == 1
    winning = windows[443]
    assert winning["distinct_target_destinations"] == 10
    assert winning["first_input_line"] > winning["earliest_input_line"]
    assert winning["first_displayed_evidence_label"] == "unknown"
    assert winning["scan_labels"]["unknown"] == 1
    assert scan["first_displayed_evidence_labels"]["unknown"] == 2


def test_scan_evaluation_uses_eve_start_and_reports_undisplayed_windows(tmp_path):
    rows = [
        {
            "event_type": "flow", "src_ip": SOURCE, "dest_ip": f"198.51.100.{peer}",
            "dest_port": port, "proto": "TCP", "flow": {
                "start": f"2024-01-01T14:00:0{peer}.125+0200", "pkts_toclient": 0,
            },
            **TARGET,
        }
        for port in range(101, 116) for peer in (1, 2)
    ]
    capture = tmp_path / "eve.ndjson"
    write_capture(capture, rows)

    completed = run_benchmark(capture, "--scan-leads", "--min-destinations", "2")
    assert completed.returncode == 0, completed.stderr
    result = json.loads(completed.stdout)
    assert result["scan_assessment"]["eligible_target_group_coverage"] == 1.0
    windows = result["assessment"]["windows"]
    assert len(windows) == 15
    hidden = [window for window in windows if window["first_input_line"] is None]
    assert hidden
    assert result["scan_assessment"]["first_displayed_evidence_labels"]["not_displayed"] == len(hidden)
    assert all(window["first_displayed_evidence_label"] is None for window in hidden)


@pytest.mark.parametrize(("issue", "error"), [
    ("blank", "disagree on a blank line at line 2"),
    ("order", "different event fields at line 1"),
    ("length", "different lengths at line 3"),
    ("leaked", "detector input contains label fields at line 1"),
    ("different-type", "different event fields at line 1"),
])
def test_label_blind_mode_rejects_misaligned_events(tmp_path, issue, error):
    rows = [observation(22, 1), None, observation(22, 2)]
    detector, labeled = write_label_blind_pair(tmp_path, rows)
    if issue == "blank":
        write_capture(labeled, [rows[0], rows[0], rows[2]])
    elif issue == "order":
        write_capture(labeled, rows[::-1])
    elif issue == "length":
        write_capture(labeled, rows[:-1])
    elif issue == "leaked":
        write_capture(detector, rows)
    else:
        different = dict(rows[0], ts=False)
        write_capture(labeled, [different, None, rows[2]])

    completed = run_benchmark(detector, "--labels", str(labeled), "--scan-leads", "--min-destinations", "2")
    assert completed.returncode == 1
    assert error in completed.stderr
    assert completed.stdout == ""
