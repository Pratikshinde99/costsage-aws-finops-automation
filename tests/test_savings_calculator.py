from costsage.savings_calculator import calculate_potential_savings


def test_calculate_potential_savings_with_mixed_resources():
    findings = [
        {"resource_type": "ec2_instance", "resource_id": "i-1", "instance_type": "m5.large"},
        {"resource_type": "ebs_volume", "resource_id": "vol-1", "size_gb": 100},
        {"resource_type": "ebs_snapshot", "resource_id": "snap-1", "size_gb": 50},
    ]

    result = calculate_potential_savings(
        waste_findings=findings,
        ec2_default_hourly_usd=0.05,
        ec2_type_hourly_overrides={"m5.large": 0.096},
        ebs_gb_month_usd=0.08,
        snapshot_gb_month_usd=0.05,
    )

    assert result["total_potential_savings"] == 79.62
    assert len(result["waste_resources"]) == 3


def test_calculate_potential_savings_handles_bad_values():
    findings = [{"resource_type": "ebs_volume", "resource_id": "vol-2", "size_gb": "invalid"}]

    result = calculate_potential_savings(
        waste_findings=findings,
        ec2_default_hourly_usd=-1,
        ec2_type_hourly_overrides={},
        ebs_gb_month_usd=-1,
        snapshot_gb_month_usd=-1,
    )

    assert result["total_potential_savings"] == 0.0
    assert result["waste_resources"][0]["estimated_monthly_cost"] == 0.0
