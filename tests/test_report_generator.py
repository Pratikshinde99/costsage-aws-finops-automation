from costsage.report_generator import build_reports


def test_build_reports_contains_required_formats():
    payload = {
        "date": "2026-03-01",
        "total_daily_cost": 123.45,
        "seven_day_average": 111.11,
        "anomaly": {"anomaly_detected": False, "message": "No anomaly detected."},
        "top_service_increases": [],
        "waste_resources": [],
        "potential_savings": 50.0,
        "tag_compliance": {"total_missing_resources": 2},
    }

    reports = build_reports(payload)

    assert "json" in reports
    assert "html" in reports
    assert "csv" in reports
    assert "generated_at" in reports["json"]
