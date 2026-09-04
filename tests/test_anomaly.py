import numpy as np

from healthunpacked.anomaly import flag_anomalies
from healthunpacked.faults import inject_dropouts, inject_spikes


def test_flat_series_has_no_anomalies():
    values = [70.0] * 100
    assert not flag_anomalies(values).any()


def test_short_series_returns_all_false():
    flags = flag_anomalies([1, 2, 3], window=25)
    assert flags.tolist() == [False, False, False]


def test_catches_an_obvious_spike():
    values = [70.0] * 200
    values[150] = 400.0

    flags = flag_anomalies(values, window=25)
    assert flags[150]


def test_injected_spikes_are_mostly_recovered():
    rng_values = [70.0 + (i % 5) for i in range(2000)]
    with_spikes, injected = inject_spikes(rng_values, count=30, seed=1)

    flags = flag_anomalies(with_spikes, window=25)
    flagged = set(np.nonzero(flags)[0].tolist())

    recall = len(flagged & injected) / len(injected)
    assert recall > 0.8


def test_injected_dropouts_are_mostly_recovered():
    rng_values = [70.0 + (i % 5) for i in range(2000)]
    with_dropouts, injected = inject_dropouts(rng_values, count=30, seed=2)

    flags = flag_anomalies(with_dropouts, window=25)
    flagged = set(np.nonzero(flags)[0].tolist())

    recall = len(flagged & injected) / len(injected)
    assert recall > 0.8
