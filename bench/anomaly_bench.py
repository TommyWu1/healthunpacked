"""Precision/recall on real data with known-answer injected faults.

k=6 is chosen, not default-and-forgotten: swept 3.5 through 10 against
both fault types on this same file before landing here. Lower catches
everything but drowns it in false alarms; higher starts missing real
dropouts. This is the balance point.
"""

import numpy as np

import healthunpacked
from healthunpacked.anomaly import flag_anomalies
from healthunpacked.faults import inject_dropouts, inject_spikes


def score(injected, flags):
    flagged = set(np.nonzero(flags)[0].tolist())
    tp = len(flagged & injected)
    precision = tp / len(flagged) if flagged else 0.0
    recall = tp / len(injected) if injected else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return precision, recall, f1


def main():
    _, values = healthunpacked.read_series("data/big.xml", "HKQuantityTypeIdentifierHeartRate")
    values = values[:50000]

    for name, inject in [("spike", inject_spikes), ("dropout", inject_dropouts)]:
        faulty, injected = inject(values, count=100, seed=0)
        flags = flag_anomalies(faulty, window=25, k=6.0)
        precision, recall, f1 = score(injected, flags)
        print(f"{name:8} precision={precision:.2f}  recall={recall:.2f}  f1={f1:.2f}")


if __name__ == "__main__":
    main()
