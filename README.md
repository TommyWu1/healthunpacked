# healthunpacked

Read an Apple Health export without waiting for it.

Drop the file on [the web app](#the-web-app) and it's parsed, charted, and
flagged for anything unusual - or use it as a library, see below.

## The problem

Every iPhone can export its Health data as a single `export.xml`. For anyone
who's worn an Apple Watch for a couple of years that file is commonly
1-2 GB, holding every heart rate sample, step count and sleep block the
phone has recorded. Apple gives you no way to look at it. Excel won't
open it. The usual advice is to write a script.

The script most people write first is `lxml.etree.parse()` - read the
whole thing, walk the tree. On a 1 GB export that wants **north of
10 GB** of memory. It doesn't finish on a normal laptop.

## What this does instead

Reads the file through one fixed 1 MiB buffer and never builds a tree
at all, so memory stays flat no matter how big the input is. The hot
path - finding each `<Record>`, pulling out its `type`, counting it -
is written in C for the same reason: profiling the pure-Python version
first showed it running at a fairly constant ~300 MB/s, over 3 seconds
for a 1 GB export. Fine for a one-off script. Not what "drop a file on
this page" should feel like.

## Numbers

5,000,000 records, ~1 GB file, M-series Mac, median of 3 runs after a
warmup pass. `bench/compare.py` reproduces the time/throughput columns;
memory is `/usr/bin/time -l` on the same file.

| | time | throughput | peak memory |
|---|---|---|---|
| **healthunpacked (C)** | **0.71s** | **~1500 MB/s** | **16 MB** |
| plain Python (regex) | 3.40s | ~313 MB/s | - |
| lxml, `iterparse` | 10.69s | ~99 MB/s | 24 MB |
| lxml, full tree (246 MB file - didn't try this on the full 1 GB one) | 2.17s | ~113 MB/s | **2.4 GB** |

Full-tree parse isn't in the main row group because it's not run
against the full-size file - 2.4 GB resident for a 246 MB input means
the 1 GB export would want something north of 10 GB of RAM, which
isn't a "give it more time" problem, it's a "won't run" problem on most
laptops.

The `iterparse` row uses the documented memory-bounding pattern
(clearing each element *and* deleting its preceding sibling), not just
`.clear()` alone - skipping the sibling cleanup left a million empty
elements attached to the tree and inflated its memory to 152 MB in
testing. Comparing against that would have been comparing against a
mistake, not against `lxml` at its best.

Both scanning implementations are checked against each other on every
test run, not just benchmarked once - `tests/test_matches_reference.py`
builds a file long enough to force the C scanner across its read
buffer more than once, and asserts the two agree record for record.

## How the C side works

A health export is a flat list of `<Record .../>` elements - no real
nesting, no namespaces. A general XML parser pays for handling all of
that anyway. This just looks for the literal bytes `<Record `, then
`type="..."`, then either the record's own `/>` or, if it wraps a
child element instead of self-closing (sleep records do this), the
child's.

Three things made this worth writing down:

- **A record can straddle two reads.** The scanner carries whatever
  didn't fit forward into the next buffer, and gives up if that
  carried remainder ever exceeds 64 KiB - a bound that stops a
  malformed file from growing memory instead of just failing.
- **Counting happens in C, not Python.** Building a Python object per
  record would hand the speed straight back; the boundary crossing is
  the expensive part, not the C itself. `scan()` tallies types against
  a small fixed table and builds the result dict once, at the end -
  and because it never touches a Python object mid-scan, it releases
  the GIL for the whole read.
- **`read_series()` can't do that last trick.** Pulling out a
  timestamp and a value for one record type means building a Python
  string and float for every match, which needs the GIL held. Real
  numbers on the same file: ~2.4x over pure Python, against `scan`'s
  ~4.8x. Smaller win, different job - not a regression.

`scanner.py` is the plain-Python version, kept on purpose: it's both
the benchmark baseline above and the thing the C version is tested
against.

## Downsampling

A chart can't draw a million points, and naive "every Nth point"
decimation drops exactly the spikes and dropouts that matter. LTTB
(largest-triangle-three-buckets) keeps the shape instead: 1,000,000
points down to 2,000 in 0.12 seconds, in plain Python.

That's fast enough on its own - parsing was the actual bottleneck, not
this - so it stayed in Python rather than getting the C treatment by
default. Not everything needs it; `bench/downsample_bench.py` is the
measurement that decided that, not a guess.

Known limitation: it treats a point's position in the list as its x,
not its real timestamp, so it assumes roughly even sampling. A series
with big time gaps would want the buckets weighted by actual time
instead of by count.

## Anomaly detection

Flags spikes and dropouts with a Hampel filter: compare each point to
the median of a window centered on it, with the point itself excluded
from that median so it can't vote on its own normality.

Validated with synthetic fault injection against real data, not
eyeballed - `bench/anomaly_bench.py` injects 100 spikes and 100
dropouts into a real 50,000-point series and checks what comes back:

| fault | precision | recall | f1 |
|---|---|---|---|
| spike | 0.98 | 1.00 | 0.99 |
| dropout | 0.98 | 0.98 | 0.98 |

Two other approaches were tried first and didn't work, for reasons
worth remembering rather than reasons worth hiding:

1. **Raw-value rolling median.** Health data drifts - a resting heart
   rate isn't stationary - and a rolling median assumes the window
   roughly is. Against a drifting window, ordinary drift kept tripping
   the threshold: ~5% precision on real data, almost all false alarms
   on plain trend, no threshold fixed it.
2. **First-difference detection.** Fixed the drift problem, but an
   extreme difference can't say which of its two endpoints is the bad
   one, so both got flagged. One real fault produced three flagged
   points, capping precision at 1/3 regardless of how good the
   underlying detection was - a mechanical ceiling, not a tuning
   problem.

Along the way, the synthetic data generator itself turned out to be
wrong twice - both are `bench/make_export.py`'s history now: an
unbounded random walk that drifted into its own clamped range and got
stuck there (3.5% of a run pinned at the boundary, and every escape
from that plateau looked like a spike to the detector), and dates that
were assigned independently at random per record instead of advancing
in order, which made a chart of otherwise-correct data look like a
scribble.

**Known limitation:** the threshold (`k=6`) is tuned against
heart-rate-like data, which drifts smoothly. A bursty metric like step
count has much larger natural point-to-point variance by design, and
will over-flag with the same threshold - the demo defaults to
HeartRate for exactly this reason. Per-type tuning is the honest next
step, not implemented yet.

## The web app

FastAPI wrapping the four pieces above behind two endpoints, and a
static drag-drop frontend with a chart (uPlot, no build step). A
bundled sample export means there's something to try without your own
data.

An upload is written to a temp file, processed, and deleted immediately
- success or failure, either way - never kept around. If you use the
hosted version instead of running this yourself, your file is
uploaded to process it; it isn't stored, logged, or looked at, and the
code path that deletes it runs in a `finally` block so an error midway
through doesn't skip the cleanup either. Run it locally and nothing
leaves your machine at all.

```
pip install -e ".[web]"
uvicorn healthunpacked.api:app --reload
```

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

Hand-reviewed, not build-tested in CI yet - there's no Docker in the
environment this was built in. `python3-dev` is installed explicitly
in the image because `python:slim` doesn't guarantee `Python.h` is
present, which the C extension needs at build time.

## Status

Scanning, downsampling, anomaly detection, and the web app all work
and are tested. Not done yet: per-type anomaly thresholds, and an
actual verified Docker deploy.
