import json
from pathlib import Path
import subprocess
import sys

import pytest

from replay_scan_leads import check_expected, replay, write_inputs


@pytest.mark.parametrize("label_separator", ["\t", "   "])
def test_replay_preserves_timestamps_and_separates_zeek_labels(tmp_path, label_separator):
    source = tmp_path / "capture-prefix.zeek"
    source.write_text(
        "#separator \\x09\n"
        "#fields\tts\tuid\tid.orig_h\tid.orig_p\tid.resp_h\tid.resp_p\tproto\tconn_state\ttunnel_parents"
        f"{label_separator}label{label_separator}detailed-label\n"
        "1767225600.0000001\texample\t192.0.2.40\t40000\t198.51.100.1\t443\ttcp\tS0\t-"
        f"{label_separator}Malicious{label_separator}PartOfAHorizontalPortScan\n"
        "1767225600.",  # Deliberately truncated at the end of the byte range.
        encoding="utf-8",
    )
    detector = tmp_path / "detector.ndjson"
    labels = tmp_path / "labels.ndjson"

    write_inputs(source, {"format": "zeek", "prefix_bytes": source.stat().st_size}, detector, labels)

    assert detector.read_text().startswith('{"ts":1767225600.0000001,')
    assert len(detector.read_text().splitlines()) == len(labels.read_text().splitlines()) == 1
    unlabelled = json.loads(detector.read_text())
    labelled = json.loads(labels.read_text())
    assert labelled.pop("label") == "Malicious"
    assert labelled.pop("det_label") == "PartOfAHorizontalPortScan"
    assert labelled == unlabelled
    assert unlabelled["uid"] == "example"


def test_replay_rejects_inputs_whose_hash_differs(tmp_path):
    (tmp_path / "changed.zeek").write_text("not the pinned recording\n", encoding="utf-8")
    case = {"id": "changed", "filename": "changed.zeek", "sha256": "0" * 64}

    with pytest.raises(ValueError, match="input SHA-256 differs"):
        replay(case, {}, tmp_path, tmp_path, runs=1)


def test_replay_requires_the_exact_number_of_selected_windows():
    expected = {"windows": [{"first_input_line": 2}]}
    actual = {"windows": [{"first_input_line": 2}, {"first_input_line": 3}]}

    with pytest.raises(ValueError, match=r"case\.windows"):
        check_expected(expected, actual, "case")


def test_benign_retry_replay_records_the_known_false_lead():
    script = Path(__file__).with_name("replay_scan_leads.py")
    result = subprocess.run(
        [sys.executable, "-B", str(script), "--case", "benign-retries", "--runs", "1"],
        capture_output=True, text=True, timeout=20, check=True,
    )
    report = json.loads(result.stdout)["results"][0]["report"]
    assessment = report["scan_assessment"]

    assert assessment["eligible_target_group_coverage"] is None
    assert assessment["observed_scope_seconds"] == 3600
    assert assessment["benign_only_leads_per_observed_hour"] == 1
    lead, = report["assessment"]["windows"]
    assert (lead["dest_port"], lead["unique_destinations"], lead["first_input_line"]) == (443, 12, 3)
    assert lead["first_displayed_evidence_label"] == "benign"
