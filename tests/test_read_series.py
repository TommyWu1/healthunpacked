"""read_series pulls out (timestamp, value) pairs for one record type at
a time - what's actually needed to plot a chart. scan() only ever
answers "how many," never "what were they."
"""

from healthunpacked import scanner

FIXTURE = "tests/fixtures/sample_export.xml"


def test_returns_timestamp_and_value_pairs():
    timestamps, values = scanner.read_series(FIXTURE, "HKQuantityTypeIdentifierHeartRate")

    assert timestamps == ["2026-01-01 08:00:00 -0500", "2026-01-01 08:05:00 -0500"]
    assert values == [72.0, 75.0]


def test_ignores_other_types():
    _, values = scanner.read_series(FIXTURE, "HKQuantityTypeIdentifierStepCount")

    assert values == [431.0, 1024.0]


def test_unknown_type_returns_empty():
    timestamps, values = scanner.read_series(FIXTURE, "HKQuantityTypeIdentifierNonsense")

    assert timestamps == []
    assert values == []
