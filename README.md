# healthunpacked

Read an Apple Health export without waiting for it.

## The problem

Every iPhone can export its Health data as a single `export.xml`. For
anyone who's worn an Apple Watch for a couple of years that file is
commonly 1-2 GB, holding every heart rate sample, step count and sleep
block the phone has recorded. Apple gives you no way to look at it.
Excel won't open it. The usual advice is to write a script.

The script most people write first is `lxml.etree.parse()` - read the
whole thing, walk the tree. On a 205 MB export that holds **2 GB** in
memory. On the 1-2 GB export people actually have, it doesn't finish.

## What this does instead

Reads the file through one fixed 1 MiB buffer and never builds a tree
at all, so memory stays flat no matter how big the input is. The hot
path - finding each `<Record>`, pulling out its `type`, counting it -
is written in C for the same reason: profiling the pure-Python version
first showed it running at a fairly constant ~300 MB/s, which is 3.4
seconds for a realistic ~1 GB export. Fine for a script. Not what you
want a "drop a file on this page" tool to feel like.

## Numbers

5,000,000 records, ~1 GB file, M-series Mac, median of 3 runs after a
warmup pass. `bench/compare.py` reproduces this.

| | time | throughput | peak memory |
|---|---|---|---|
| **healthunpacked (C)** | **0.73s** | **~1400 MB/s** | **15 MB** |
| plain Python (regex) | 3.35s | ~300 MB/s | 15 MB |
| lxml, `iterparse` | 9.68s | ~106 MB/s | 151 MB |
| lxml, full tree (205 MB file) | 1.96s | - | **2080 MB** |

Both implementations are checked against each other on every run of
the test suite, not just benchmarked once - `tests/test_matches_reference.py`
generates a file long enough to force the C scanner across its buffer
boundary several times, and asserts the two agree.

## Why the memory story matters more than the speed one

The plain-Python version is already fine on memory - it reads line by
line and never holds more than one line at a time. The real gap is
`lxml`'s full-tree parse: 2 GB resident for a 205 MB file, because it
builds a Python object for every element instead of throwing each one
away as it goes. A 1.5 GB export would want something in the range of
15 GB of RAM. That's not slow, it's not going to run at all on most
laptops. The C version, and the honest pure-Python version, both avoid
this by never holding the file at more than one buffer's width.

## How the C side works

A health export is a flat list of `<Record .../>` elements - no real
nesting, no namespaces. A general XML parser pays for handling all of
that anyway. This just looks for the literal bytes `<Record `, then
`type="..."`, then either the record's own `/>` or, if it wraps a
child element instead of self-closing (sleep records do this), the
child's.

Two things made this worth writing down:

- **A record can straddle two reads.** The scanner carries whatever
  didn't fit forward into the next buffer, and gives up if that
  carried remainder ever exceeds 64 KiB - a bound that stops a
  malformed file from growing memory instead of just failing.
- **Counting happens in C, not Python.** Building a Python object per
  record would hand the speed straight back; the boundary crossing is
  the expensive part, not the C itself. Types are tallied against a
  small fixed table and the result dict is built once, at the end.

`scanner.py` is the plain-Python version, kept on purpose - it's both
the benchmark baseline above and the thing the C version is tested
against.

## Use

```
pip install -e ".[dev]"
python -c "import healthunpacked; print(healthunpacked.scan('export.xml'))"
```

```
pytest
python bench/make_export.py data/big.xml --records 5000000
python bench/compare.py data/big.xml
```

## Status

Scanning and the benchmark are done. Charting and anomaly detection
(flagging days that look unusual) are next.

Nothing here uploads your export anywhere - everything runs locally.
