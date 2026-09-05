"""Small helper shared by the benchmark scripts, not the library itself.

Both anomaly_bench.py and downsample_bench.py want the same 5M-record
heart rate series from data/big.xml. Kept in one place so there's a
single spot to fix if that path or record type ever changes.
"""

import os

import healthunpacked

BIG_EXPORT = "data/big.xml"
HEART_RATE = "HKQuantityTypeIdentifierHeartRate"


def load_heart_rate(limit=None):
    if not os.path.exists(BIG_EXPORT):
        raise FileNotFoundError(
            f"{BIG_EXPORT} not found - generate it first with:\n"
            f"  python bench/make_export.py {BIG_EXPORT} --records 5000000"
        )
    _, values = healthunpacked.read_series(BIG_EXPORT, HEART_RATE)
    return values[:limit] if limit else values
