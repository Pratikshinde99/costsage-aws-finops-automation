from costsage.anomaly_detector import detect_cost_anomaly


def test_detect_cost_anomaly_positive_case():
    result = detect_cost_anomaly(yesterday_total=130.0, seven_day_average=100.0, anomaly_multiplier=1.3)

    assert result["anomaly_detected"] is False
    assert result["increase_pct"] == 30.0
    assert result["projected_monthly_spend"] == 3900.0
    assert result["projected_monthly_baseline"] == 3000.0
    assert result["projected_monthly_increase_pct"] == 30.0


def test_detect_cost_anomaly_when_above_threshold():
    result = detect_cost_anomaly(yesterday_total=131.0, seven_day_average=100.0, anomaly_multiplier=1.3)

    assert result["anomaly_detected"] is True
    assert result["projected_monthly_overspend"] == 930.0


def test_detect_cost_anomaly_invalid_inputs_are_safeguarded():
    result = detect_cost_anomaly(yesterday_total="bad", seven_day_average=-1.0, anomaly_multiplier=-2.0)

    assert result["anomaly_detected"] is False
    assert result["threshold"] == 1.0
    assert result["projected_monthly_spend"] == 0.0
    assert result["projected_monthly_baseline"] == 0.0
    assert result["message"].startswith("Insufficient baseline")
