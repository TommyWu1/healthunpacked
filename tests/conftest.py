import pytest

HEADER = '<?xml version="1.0" encoding="UTF-8"?>\n<HealthData locale="en_CA">\n'
FOOTER = "</HealthData>\n"
ROW = (
    ' <Record type="HKQuantityTypeIdentifier{t}" sourceName="Apple Watch"'
    ' unit="count/min" startDate="2026-01-01 08:00:00 -0500"'
    ' endDate="2026-01-01 08:00:00 -0500" value="{v}"/>\n'
)
TYPES = ["HeartRate", "StepCount", "RestingHeartRate"]


@pytest.fixture
def big_export(tmp_path):
    """Long enough (tens of thousands of records) to cross the C
    scanner's 1 MiB read window more than once. Anything shorter than
    that window wouldn't actually test the carry-over logic.
    """
    path = tmp_path / "big_export.xml"
    with open(path, "w") as f:
        f.write(HEADER)
        for i in range(60_000):
            f.write(ROW.format(t=TYPES[i % len(TYPES)], v=i % 200))
        f.write(FOOTER)
    return path
