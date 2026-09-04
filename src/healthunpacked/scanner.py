"""The plain-python version. Kept as the reference: whatever the C
extension does, it needs to agree with this on every input.

See _scan.c for the version that's actually used.
"""

import re
from collections import Counter

RECORD_TYPE = re.compile(rb'<Record [^>]*?type="([^"]+)"[^>]*>')


def scan(path):
    """Return (total_records, {type_identifier: count}) for an export file."""
    counts = Counter()
    total = 0

    with open(path, "rb") as f:
        for line in f:
            for match in RECORD_TYPE.finditer(line):
                counts[match.group(1).decode()] += 1
                total += 1

    return total, dict(counts)


# type comes first in every real export, so anchoring on it lets this be
# a plain regex instead of the general attribute lookup the C side needs
def _series_pattern(record_type):
    escaped = re.escape(record_type.encode())
    return re.compile(
        rb'<Record type="' + escaped +
        rb'"[^>]*?startDate="([^"]+)"[^>]*?value="([^"]+)"[^>]*>'
    )


def read_series(path, record_type):
    """Return (timestamps, values) for every record of one type.

    Only meaningful for numeric records - heart rate, step count, that
    kind of thing. Category records (sleep stages, etc.) don't have a
    number in `value` and aren't handled here.
    """
    pattern = _series_pattern(record_type)
    timestamps = []
    values = []

    with open(path, "rb") as f:
        for line in f:
            for match in pattern.finditer(line):
                timestamps.append(match.group(1).decode())
                values.append(float(match.group(2)))

    return timestamps, values
