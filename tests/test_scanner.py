"""Pin down what "correct" means before anything gets optimized.

These run against healthunpacked.scan, whatever implementation that
currently points at. The plan is: pure python now, a C extension later,
same tests the whole way, so a passing suite means the swap was safe.
"""

import pytest

import healthunpacked

FIXTURES = "tests/fixtures"


def test_counts_by_type():
    total, counts = healthunpacked.scan(f"{FIXTURES}/sample_export.xml")

    assert total == 5
    assert counts == {
        "HKQuantityTypeIdentifierHeartRate": 2,
        "HKQuantityTypeIdentifierStepCount": 2,
        "HKCategoryTypeIdentifierSleepAnalysis": 1,
    }


def test_record_with_a_child_element_counts_once():
    # the sleep record above wraps a <MetadataEntry> instead of
    # self-closing - easy to accidentally double count if you're not
    # careful about where a record "ends"
    _, counts = healthunpacked.scan(f"{FIXTURES}/sample_export.xml")

    assert counts["HKCategoryTypeIdentifierSleepAnalysis"] == 1


def test_missing_file_raises():
    with pytest.raises(OSError):
        healthunpacked.scan(f"{FIXTURES}/does_not_exist.xml")


def test_empty_file(tmp_path):
    empty = tmp_path / "empty.xml"
    empty.write_text("")

    assert healthunpacked.scan(str(empty)) == (0, {})
