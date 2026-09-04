"""Build a fake export of a given size, for testing against something
bigger than a hand-written fixture.

Each type does a small mean-reverting random walk instead of picking
an independent random value per record - actual heart rate drifts, it
doesn't teleport between 40 and 190 bpm from one sample to the next.

First version of this used an unbounded walk clamped to a range, which
seemed fine until the anomaly-detection benchmark came back with a
precision that wouldn't improve no matter how the threshold was
tuned. Turned out the unbounded walk drifts into the clamp and sits
there - 3.5% of a 50k-point run was pinned at the boundary - and every
escape from that plateau reads as a huge jump to a difference-based
detector, whether or not anything is actually wrong. Pulling the walk
back toward its baseline each step keeps it away from the boundary
almost entirely, which is also just a more realistic model of resting
heart rate than an unbounded walk was.
"""

import argparse
import random

# baseline, low clamp, high clamp, per-step wobble
TYPES = {
    "HKQuantityTypeIdentifierHeartRate": (70.0, 40.0, 190.0, 3.0),
    "HKQuantityTypeIdentifierStepCount": (20.0, 0.0, 300.0, 25.0),
    "HKQuantityTypeIdentifierActiveEnergyBurned": (5.0, 0.0, 40.0, 3.0),
    "HKQuantityTypeIdentifierRestingHeartRate": (62.0, 45.0, 90.0, 1.0),
}
SLEEP_TYPE = "HKCategoryTypeIdentifierSleepAnalysis"

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
    state = {t: baseline for t, (baseline, _, _, _) in TYPES.items()}
    kinds = list(TYPES) + [SLEEP_TYPE]

    with open(args.path, "w") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n<HealthData locale="en_CA">\n')
        for _ in range(args.records):
            t = rng.choice(kinds)
            m, d, h = rng.randint(1, 12), rng.randint(1, 28), rng.randint(0, 23)

            if t == SLEEP_TYPE:
                v = "HKCategoryValueSleepAnalysisAsleepCore"
            else:
                baseline, lo, hi, step = TYPES[t]
                pulled = state[t] + 0.08 * (baseline - state[t])
                walked = pulled + rng.gauss(0, step)
                state[t] = max(lo, min(hi, walked))
                v = round(state[t], 1)

            f.write(ROW.format(t=t, m=m, d=d, h=h, v=v))
        f.write("</HealthData>\n")


if __name__ == "__main__":
    main()
