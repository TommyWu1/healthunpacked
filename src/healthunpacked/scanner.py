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
