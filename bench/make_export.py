"""Build a fake export of a given size, for testing against something
bigger than a hand-written fixture.
"""

import argparse
import random

TYPES = [
    "HKQuantityTypeIdentifierHeartRate",
    "HKQuantityTypeIdentifierStepCount",
    "HKQuantityTypeIdentifierActiveEnergyBurned",
    "HKQuantityTypeIdentifierRestingHeartRate",
    "HKCategoryTypeIdentifierSleepAnalysis",
]

ROW = (
    ' <Record type="{t}" sourceName="Apple Watch" sourceVersion="10.1"'
    ' unit="count/min" startDate="2026-{m:02d}-{d:02d} {h:02d}:00:00 -0500"'
    ' endDate="2026-{m:02d}-{d:02d} {h:02d}:05:00 -0500" value="{v}"/>\n'
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("path")
    parser.add_argument("--records", type=int, default=1_000_000)
    args = parser.parse_args()

    rng = random.Random(0)  # fixed seed - same file every time this is run
    with open(args.path, "w") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n<HealthData locale="en_CA">\n')
        for _ in range(args.records):
            f.write(ROW.format(
                t=rng.choice(TYPES),
                m=rng.randint(1, 12), d=rng.randint(1, 28), h=rng.randint(0, 23),
                v=rng.randint(40, 190),
            ))
        f.write("</HealthData>\n")


if __name__ == "__main__":
    main()
