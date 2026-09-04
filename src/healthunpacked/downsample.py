"""LTTB downsampling, so a chart doesn't have to draw a million points.

Treats each value's position in the list as its x - not its real
timestamp. Good enough for now since health exports are close to
regularly sampled; a series with big time gaps would want the buckets
weighted by actual time instead of by count.
"""


def lttb(values, threshold):
    """Pick `threshold` points out of `values`, keeping the shape.

    Returns a list of (index, value) pairs so the caller can map back
    to whatever else lines up with the original list (timestamps).
    """
    n = len(values)
    if threshold >= n or threshold <= 2:
        return list(enumerate(values))

    bucket_size = (n - 2) / (threshold - 2)
    sampled = [(0, values[0])]
    a = 0

    for i in range(threshold - 2):
        bucket_start = int((i + 1) * bucket_size) + 1
        bucket_end = min(int((i + 2) * bucket_size) + 1, n)
        avg_x = sum(range(bucket_start, bucket_end)) / (bucket_end - bucket_start)
        avg_y = sum(values[bucket_start:bucket_end]) / (bucket_end - bucket_start)

        range_start = int(i * bucket_size) + 1
        range_end = int((i + 1) * bucket_size) + 1

        point_ax, point_ay = a, values[a]
        best_area = -1
        best_index = range_start

        for j in range(range_start, range_end):
            area = abs(
                (point_ax - avg_x) * (values[j] - point_ay)
                - (point_ax - j) * (avg_y - point_ay)
            )
            if area > best_area:
                best_area = area
                best_index = j

        sampled.append((best_index, values[best_index]))
        a = best_index

    sampled.append((n - 1, values[n - 1]))
    return sampled
