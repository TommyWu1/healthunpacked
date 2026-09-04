"""Hampel identifier: flag a point against a window centered on it,
with the point itself excluded from its own baseline.

Two things went wrong on the way here, both worth remembering:

Raw-value rolling median first. Health data drifts, and a rolling
median assumes the window is roughly stationary - against a drifting
window, ordinary drift kept tripping the threshold. ~5% precision,
mostly false alarms on plain trend.

Then first-difference detection, which fixed the drift problem but
introduced a different one: an extreme difference can't say which of
its two endpoints is the bad one, so both got flagged. A single fault
produces two extreme differences (in and out), so three points end up
flagged for every one real fault - precision capped at 1/3 by that
alone, regardless of how good the detector actually was underneath.

A centered window fixes both: excluding the point from its own
baseline means a spike can't inflate the median that's about to judge
it, and comparing directly to a centered window - rather than to a
difference - means the anomalous point is the only one flagged.
"""

import numpy as np


def flag_anomalies(values, window=25, k=6.0):
    """Return a bool array, True where a point looks like a spike or
    dropout relative to the points around it (not including itself).
    """
    values = np.asarray(values, dtype=float)
    n = len(values)
    flags = np.zeros(n, dtype=bool)

    if window % 2 == 0:
        window += 1  # odd window, so the scored point sits exactly in the middle
    half = window // 2
    if n <= window:
        return flags

    windows = np.lib.stride_tricks.sliding_window_view(values, window)
    neighbors = np.delete(windows, half, axis=1)

    median = np.median(neighbors, axis=1)
    mad = np.median(np.abs(neighbors - median[:, None]), axis=1)
    mad = np.where(mad == 0, 1e-9, mad)  # a flat neighborhood shouldn't divide by zero

    centers = values[half:half + len(windows)]
    z = 0.6745 * (centers - median) / mad  # comparable to a normal-distribution z-score

    flags[half:half + len(windows)] = np.abs(z) > k
    return flags
