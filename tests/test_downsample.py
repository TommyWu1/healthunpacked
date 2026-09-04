from healthunpacked.downsample import lttb


def test_fewer_points_than_threshold_returns_everything():
    values = [1, 2, 3]
    assert lttb(values, 10) == [(0, 1), (1, 2), (2, 3)]


def test_always_keeps_first_and_last_point():
    values = list(range(1000))
    result = lttb(values, 50)

    assert result[0] == (0, 0)
    assert result[-1] == (999, 999)


def test_output_size_matches_threshold():
    values = list(range(1000))
    assert len(lttb(values, 50)) == 50


def test_keeps_a_spike_a_flat_line_would_lose():
    # a naive "every nth point" decimation would probably skip right
    # over this - that's the whole reason to use lttb instead
    values = [0.0] * 500
    values[250] = 100.0

    result = lttb(values, 20)
    spiked_indices = [i for i, v in result if v == 100.0]

    assert spiked_indices == [250]
