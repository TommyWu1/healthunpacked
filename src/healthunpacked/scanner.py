"""Count records in an Apple Health export by type.

This is the plain version: read the file line by line, pull out anything
that looks like a <Record type="..."> tag with a regex. It is not fast,
but it is easy to read, and it is what the C version has to agree with.
"""

import re
from collections import Counter

RECORD_TYPE = re.compile(rb'<Record [^>]*?type="([^"]+)"')


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
