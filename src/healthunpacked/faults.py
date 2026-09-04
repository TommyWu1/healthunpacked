"""Inject known-answer faults into a series, so anomaly detection can
be measured against ground truth instead of eyeballed.
"""

import random


def inject_spikes(values, count, magnitude=8.0, seed=0):
    """Return (values, injected_indices)."""
    rng = random.Random(seed)
    values = list(values)
    spread = (max(values) - min(values)) or 1.0

    indices = rng.sample(range(len(values)), count)
    for i in indices:
        values[i] += magnitude * spread * rng.choice([-1, 1])

    return values, set(indices)


def inject_dropouts(values, count, seed=0):
    """A dropout here means a sensor reading came back zero - the
    record still exists, it's just wrong. Not a missing record.
    """
    rng = random.Random(seed)
    values = list(values)

    indices = rng.sample(range(len(values)), count)
    for i in indices:
        values[i] = 0.0

    return values, set(indices)
