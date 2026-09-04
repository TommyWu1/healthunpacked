from fastapi.testclient import TestClient

from healthunpacked.api import app

client = TestClient(app)

SAMPLE = "tests/fixtures/sample_export.xml"


def test_scan_endpoint():
    with open(SAMPLE, "rb") as f:
        res = client.post("/api/scan", files={"file": f})

    assert res.status_code == 200
    body = res.json()
    assert body["total"] == 5
    assert body["counts"]["HKQuantityTypeIdentifierHeartRate"] == 2


def test_series_endpoint():
    with open(SAMPLE, "rb") as f:
        res = client.post(
            "/api/series",
            files={"file": f},
            data={"record_type": "HKQuantityTypeIdentifierHeartRate"},
        )

    assert res.status_code == 200
    body = res.json()
    assert body["total_points"] == 2
    assert len(body["chart"]["times"]) == 2
    assert body["chart"]["values"] == [72.0, 75.0]


def test_series_unknown_type_is_404():
    with open(SAMPLE, "rb") as f:
        res = client.post(
            "/api/series",
            files={"file": f},
            data={"record_type": "HKQuantityTypeIdentifierNonsense"},
        )

    assert res.status_code == 404


def test_use_sample_flag_skips_file_upload():
    res = client.post("/api/scan", data={"use_sample": "true"})

    assert res.status_code == 200
    assert res.json()["total"] > 0


def test_anomalies_are_always_present_in_chart_points():
    # regression check: anomalies must be guaranteed in the chart's
    # points, not left to chance overlap with the downsampled selection
    res = client.post("/api/scan", data={"use_sample": "true"})
    a_type = next(t for t in res.json()["counts"] if "Quantity" in t)

    res = client.post(
        "/api/series", data={"use_sample": "true", "record_type": a_type}
    )
    body = res.json()

    flagged_in_chart = sum(body["chart"]["is_anomaly"])
    assert flagged_in_chart == body["anomaly_count"]
