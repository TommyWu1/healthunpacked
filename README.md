# healthunpacked

Read an Apple Health export without waiting for it.

## The problem

Every iPhone can export its Health data as a single `export.xml`. After a
couple of years with an Apple Watch that file is commonly 1-2 GB. Apple
gives you no way to open it, and the standard fix, `lxml.etree.parse()`,
builds a document tree that wants north of 10 GB of RAM for a file that
size. It doesn't finish on a normal laptop.

## What this does instead

Scans the file through one fixed 1 MiB buffer and never builds a tree, so
memory stays flat no matter the input size. The hot path is a C extension:
a pure-Python version first ran at a steady ~300 MB/s, over 3 seconds for
a 1 GB export, which is fine for a script but not for something you're
supposed to drop a file onto and watch work.

## Numbers

5,000,000 records, ~1 GB file, M-series Mac, median of 3 runs. `bench/compare.py` reproduces the time and throughput columns; memory comes from `/usr/bin/time -l`.

| | time | throughput | peak memory |
|---|---|---|---|
| **healthunpacked (C)** | **0.71s** | **~1,500 MB/s** | **16 MB** |
| plain Python (regex) | 3.40s | ~313 MB/s | - |
| lxml `iterparse` | 10.69s | ~99 MB/s | 24 MB |
| lxml full tree (246 MB file) | 2.17s | ~113 MB/s | **2.4 GB** |

Full-tree parse runs on a smaller file on purpose: 2.4 GB for 246 MB of
input means the full 1 GB export would want well over 10 GB, which isn't
a "wait longer" problem, it's a "won't run" one. The `iterparse` row uses
the documented sibling-cleanup pattern, not just `.clear()` alone; skip
that step and lxml's own memory looks 6.3x worse than it actually is.

Both scanners are checked against each other on every test run, not just
benchmarked once. See `tests/test_matches_reference.py`.

## Try it

```
pip install -e ".[web]"
uvicorn healthunpacked.api:app --reload
```

Drag in your own export or use the bundled sample. An upload is written
to a temp file, parsed, and deleted in a `finally` block whether the
request succeeds or fails, so nothing is kept around either way.

## Use as a library

```
pip install -e ".[dev]"
```

```python
import healthunpacked

total, counts = healthunpacked.scan("export.xml")
timestamps, values = healthunpacked.read_series("export.xml", "HKQuantityTypeIdentifierHeartRate")
```

```
pytest
python bench/make_export.py data/big.xml --records 5000000
python bench/compare.py data/big.xml
python bench/downsample_bench.py
python bench/anomaly_bench.py
```

## Docker

```
docker build -t healthunpacked .
docker run -p 8000:8000 healthunpacked
```

Hand-reviewed, not build-tested: there's no Docker in the environment this
was built in. `python3-dev` is installed explicitly since `python:slim`
doesn't guarantee `Python.h`, which the C extension needs to build.

## How the pieces work

- Parsing lives in `_scan.c`, a byte scanner rather than an XML parser,
  since a health export has no real nesting. Its own comments cover the
  read-buffer carry-over, the fixed type table, and why `scan()` releases
  the GIL while `read_series()` can't.
- `downsample.py` implements LTTB, so a chart doesn't draw a million
  points and doesn't lose the spikes a naive "every Nth point" approach
  would. 1,000,000 points to 2,000 in 0.12 seconds, in plain Python;
  `bench/downsample_bench.py` is the measurement that decided a C version
  wasn't worth it.
- `anomaly.py` flags spikes and dropouts with a Hampel filter, comparing
  each point to a centered window with itself excluded. F1 0.99 (spike)
  and 0.98 (dropout) on synthetic fault injection, `bench/anomaly_bench.py`.
  Two earlier approaches are documented in the module's own docstring,
  along with why each one failed.

## Known limitations

- No live deployment yet, and the Docker build has never actually run.
- Every number above comes from a synthetic generator (`bench/make_export.py`),
  not a real Apple Health export.
- The anomaly threshold is tuned for heart-rate-like drift and over-flags
  bursty metrics like step count at the same setting.
- LTTB treats a point's index as its x-axis position, not its real
  timestamp, so it assumes roughly even sampling.
