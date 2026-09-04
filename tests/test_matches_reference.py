"""The one test that actually matters for the C version: does it agree
with the plain-python reference on the same input?

That's a more useful check than a handful of examples I thought up,
because it doesn't depend on me having imagined the right edge case.
The "big" fixture is built long enough to force several read-window
boundaries inside the C scanner, which is where a bug would show up:
a record split across two 1 MiB reads.
"""

import healthunpacked
from healthunpacked import scanner


def test_c_extension_agrees_with_reference(big_export):
    assert healthunpacked.scan(str(big_export)) == scanner.scan(str(big_export))


def test_agree_on_a_truncated_record(tmp_path):
    # caught this one by hand: the naive regex counted a half-written
    # record (file cut off mid-attribute, as happens if an export gets
    # interrupted) while the C scanner correctly refused to, since it
    # never found a closing tag. fixed the reference to require a
    # closing ">" too, so this needs to stay pinned down.
    path = tmp_path / "truncated.xml"
    path.write_text(
        '<HealthData>\n <Record type="HKQuantityTypeIdentifierHeartRate" value="7'
    )

    assert healthunpacked.scan(str(path)) == scanner.scan(str(path)) == (0, {})


def test_read_series_agrees_with_reference(big_export):
    for record_type in ["HeartRate", "StepCount", "RestingHeartRate"]:
        full_type = f"HKQuantityTypeIdentifier{record_type}"
        assert healthunpacked.read_series(str(big_export), full_type) == \
            scanner.read_series(str(big_export), full_type)
