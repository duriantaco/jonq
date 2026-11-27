from jonq.fanout import FanoutPeak, find_fanout


def test_fanout_peak_keeps_repeated_destination_after_first_event_expires():
    by_source = {
        "192.0.2.1": [
            (16.0, "198.51.100.3"),
            (0.0, "198.51.100.1"),
            (11.0, "198.51.100.3"),
            (7.0, "198.51.100.2"),
            (1.0, "198.51.100.1"),
            (16.0, "198.51.100.4"),
        ],
    }

    peaks = find_fanout(by_source, window_seconds=10, min_destinations=3)

    assert peaks == [
        FanoutPeak(
            src_ip="192.0.2.1",
            unique_destinations=3,
            window_start=1.0,
            window_end=11.0,
            destinations=["198.51.100.1", "198.51.100.2", "198.51.100.3"],
        ),
    ]


def test_fanout_peaks_sort_by_count_then_source_and_exclude_below_threshold():
    by_source = {
        "192.0.2.3": [(4.0, "198.51.100.2"), (4.0, "198.51.100.1")],
        "192.0.2.1": [(5.0, "198.51.100.2"), (6.0, "198.51.100.1")],
        "192.0.2.2": [
            (10.0, "198.51.100.1"),
            (10.0, "198.51.100.2"),
            (11.0, "198.51.100.3"),
        ],
        "192.0.2.4": [(0.0, "198.51.100.1"), (2.0, "198.51.100.2")],
    }

    peaks = find_fanout(by_source, window_seconds=1, min_destinations=2)

    assert [(peak.src_ip, peak.unique_destinations) for peak in peaks] == [
        ("192.0.2.2", 3),
        ("192.0.2.1", 2),
        ("192.0.2.3", 2),
    ]
