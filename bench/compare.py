"""How slow is 'just write a Python script', actually?

Times healthunpacked.scan against two things people would reach for
before writing any C: the regex loop by itself over a bigger file, and
lxml, both as a streaming parse and as the naive parse-the-whole-thing
approach that a first attempt usually looks like.

Reports the median of a few runs after a warmup, and prints the machine
it ran on, because these numbers only mean anything next to that.
"""

import argparse
import os
import platform
import statistics
import time

import healthunpacked


def lxml_streaming(path):
    from lxml import etree

    total = 0
    counts = {}
    for _, el in etree.iterparse(path, events=("end",), tag="Record"):
        t = el.get("type")
        counts[t] = counts.get(t, 0) + 1
        total += 1
        el.clear()
    return total, counts


def lxml_full_tree(path):
    from lxml import etree

    tree = etree.parse(path)
    total = 0
    counts = {}
    for record in tree.getroot().iter("Record"):
        t = record.get("type")
        counts[t] = counts.get(t, 0) + 1
        total += 1
    return total, counts


def median_time(fn, path, runs):
    fn(path)  # warmup, so we're not timing disk cache misses
    times = []
    for _ in range(runs):
        start = time.perf_counter()
        fn(path)
        times.append(time.perf_counter() - start)
    return statistics.median(times)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("path")
    parser.add_argument("--runs", type=int, default=3)
    args = parser.parse_args()

    size_mb = os.path.getsize(args.path) / 1e6
    print(f"{platform.platform()}, Python {platform.python_version()}")
    print(f"file: {args.path} ({size_mb:.0f} MB)\n")

    candidates = [
        ("healthunpacked.scan", healthunpacked.scan),
        ("lxml, streaming", lxml_streaming),
    ]
    # the full-tree parse is what most people write first - worth showing
    # even though it's clearly not going to win
    if size_mb < 500:
        candidates.append(("lxml, full tree", lxml_full_tree))

    print(f"{'':<22}{'time':>10}{'MB/s':>10}")
    for name, fn in candidates:
        elapsed = median_time(fn, args.path, args.runs)
        print(f"{name:<22}{elapsed:>9.2f}s{size_mb / elapsed:>10.0f}")


if __name__ == "__main__":
    main()
