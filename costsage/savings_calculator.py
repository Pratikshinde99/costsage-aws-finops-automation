from typing import Dict, List


def _to_non_negative_float(value: object, default: float = 0.0) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed >= 0 else default


def calculate_potential_savings(
    waste_findings: List[Dict[str, object]],
    ec2_default_hourly_usd: float,
    ec2_type_hourly_overrides: Dict[str, float],
    ebs_gb_month_usd: float,
    snapshot_gb_month_usd: float,
) -> Dict[str, object]:
    enriched = []
    total = 0.0
    ec2_default_hourly = _to_non_negative_float(ec2_default_hourly_usd, default=0.0)
    ebs_rate = _to_non_negative_float(ebs_gb_month_usd, default=0.0)
    snapshot_rate = _to_non_negative_float(snapshot_gb_month_usd, default=0.0)

    for finding in waste_findings:
        resource_type = finding.get("resource_type")
        monthly_cost = 0.0

        if resource_type == "ec2_instance":
            instance_type = str(finding.get("instance_type", ""))
            override_hourly = ec2_type_hourly_overrides.get(instance_type, ec2_default_hourly)
            hourly = _to_non_negative_float(override_hourly, default=ec2_default_hourly)
            monthly_cost = hourly * 24 * 30
        elif resource_type == "ebs_volume":
            size_gb = _to_non_negative_float(finding.get("size_gb", 0), default=0.0)
            monthly_cost = size_gb * ebs_rate
        elif resource_type == "ebs_snapshot":
            size_gb = _to_non_negative_float(finding.get("size_gb", 0), default=0.0)
            monthly_cost = size_gb * snapshot_rate
        elif resource_type == "elb":
            monthly_cost = 18.0

        monthly_cost = round(max(monthly_cost, 0.0), 2)
        total += monthly_cost

        enriched_finding = dict(finding)
        enriched_finding["estimated_monthly_cost"] = monthly_cost
        enriched_finding["savings_message"] = f"If deleted -> Save ${monthly_cost}/month"
        enriched.append(enriched_finding)

    return {
        "waste_resources": enriched,
        "total_potential_savings": round(total, 2),
    }