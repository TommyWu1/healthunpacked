"""Is lttb fast enough in plain python, or does it need C too?

1M points down to 2000: 0.12s. Parsing was the bottleneck, not this.
Leaving it in python.
"""

import time

import healthunpacked
from healthunpacked.downsample import lttb


def main():
    _, values = healthunpacked.read_series("data/big.xml", "HKQuantityTypeIdentifierHeartRate")
    print(f"{len(values)} points")

    start = time.perf_counter()
    lttb(values, 2000)
    print(f"downsample to 2000 points: {time.perf_counter() - start:.2f}s")


if __name__ == "__main__":
    main()
