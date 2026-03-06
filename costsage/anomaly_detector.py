from typing import Dict


def _to_non_negative_float(value: object) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return 0.0
    return parsed if parsed >= 0 else 0.0


def detect_cost_anomaly(
    yesterday_total: float,
    seven_day_average: float,
    anomaly_multiplier: float = 1.30,
) -> Dict[str, object]:
    normalized_yesterday_total = _to_non_negative_float(yesterday_total)
    normalized_seven_day_average = _to_non_negative_float(seven_day_average)
    threshold_multiplier = max(_to_non_negative_float(anomaly_multiplier), 1.0)

    if normalized_seven_day_average <= 0:
        projected_monthly_spend = normalized_yesterday_total * 30.0
        return {
            "anomaly_detected": False,
            "threshold": threshold_multiplier,
            "increase_pct": 0.0,
            "projected_monthly_spend": round(projected_monthly_spend, 2),
            "projected_monthly_baseline": 0.0,
            "projected_monthly_increase_pct": 0.0,
            "projected_monthly_overspend": 0.0,
            "message": "Insufficient baseline data to evaluate anomaly.",
        }

    ratio = normalized_yesterday_total / normalized_seven_day_average
    increase_pct = (ratio - 1.0) * 100.0
    anomaly = ratio > threshold_multiplier
    overspend = max(0.0, normalized_yesterday_total - normalized_seven_day_average) * 30.0
    projected_monthly_spend = normalized_yesterday_total * 30.0
    projected_monthly_baseline = normalized_seven_day_average * 30.0
    projected_monthly_increase_pct = (
        ((projected_monthly_spend - projected_monthly_baseline) / projected_monthly_baseline) * 100.0
        if projected_monthly_baseline > 0
        else 0.0
    )

    return {
        "anomaly_detected": anomaly,
        "threshold": threshold_multiplier,
        "increase_pct": round(increase_pct, 2),
        "projected_monthly_spend": round(projected_monthly_spend, 2),
        "projected_monthly_baseline": round(projected_monthly_baseline, 2),
        "projected_monthly_increase_pct": round(projected_monthly_increase_pct, 2),
        "projected_monthly_overspend": round(overspend, 2),
        "message": (
            "Anomaly detected: yesterday cost exceeds threshold."
            if anomaly
            else "No anomaly detected."
        ),
    }