"""The web surface. Everything interesting is in scanner.py / anomaly.py -
this is just wiring: take an upload, run the pipeline, hand back JSON.
"""

import os
import tempfile
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.staticfiles import StaticFiles

import healthunpacked
from healthunpacked.anomaly import flag_anomalies
from healthunpacked.downsample import lttb

app = FastAPI(title="healthunpacked")

STATIC_DIR = Path(__file__).resolve().parent.parent.parent / "static"
SAMPLE_PATH = STATIC_DIR / "sample-export.xml"


def _to_unix(raw):
    return datetime.strptime(raw, "%Y-%m-%d %H:%M:%S %z").timestamp()


async def _save_upload(file: UploadFile) -> str:
    fd, path = tempfile.mkstemp(suffix=".xml")
    try:
        with os.fdopen(fd, "wb") as out:
            while chunk := await file.read(1024 * 1024):
                out.write(chunk)
    except Exception:
        os.unlink(path)
        raise
    return path


async def _resolve_path(file, use_sample):
    if use_sample:
        return str(SAMPLE_PATH), False
    if file is None:
        raise HTTPException(400, "no file provided")
    return await _save_upload(file), True


@app.post("/api/scan")
async def api_scan(file: UploadFile = File(None), use_sample: bool = Form(False)):
    """What's in this export, and how much of it."""
    path, is_temp = await _resolve_path(file, use_sample)
    try:
        total, counts = healthunpacked.scan(path)
    finally:
        if is_temp:
            os.unlink(path)  # processed, not kept
    return {"total": total, "counts": counts}


@app.post("/api/series")
async def api_series(
    file: UploadFile = File(None),
    use_sample: bool = Form(False),
    record_type: str = Form(...),
):
    """One metric's series: downsampled for the chart, plus anomalies."""
    path, is_temp = await _resolve_path(file, use_sample)
    try:
        timestamps, values = healthunpacked.read_series(path, record_type)
    finally:
        if is_temp:
            os.unlink(path)

    if not values:
        raise HTTPException(404, f"no records of type {record_type!r}")

    times = [_to_unix(t) for t in timestamps]
    flags = flag_anomalies(values)
    anomaly_indices = {i for i, is_anom in enumerate(flags) if is_anom}

    # a handful of anomalies out of a million points almost never land on
    # one of lttb's 2000 chosen points by chance - force them in, so the
    # overlay actually has something to draw
    sampled_indices = {i for i, _ in lttb(values, min(2000, len(values)))}
    combined = sorted(sampled_indices | anomaly_indices)

    return {
        "chart": {
            "times": [times[i] for i in combined],
            "values": [values[i] for i in combined],
            "is_anomaly": [i in anomaly_indices for i in combined],
        },
        "total_points": len(values),
        "anomaly_count": len(anomaly_indices),
    }


app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
