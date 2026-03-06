from unittest.mock import Mock, patch

from costsage.waste_detector import detect_waste_resources


@patch("costsage.waste_detector._detect_idle_elbs", return_value=[{"resource_type": "elb", "resource_id": "lb-a"}])
@patch("costsage.waste_detector._detect_old_snapshots", return_value=[{"resource_type": "ebs_snapshot", "resource_id": "snap-1"}])
@patch("costsage.waste_detector._detect_unattached_volumes", return_value=[{"resource_type": "ebs_volume", "resource_id": "vol-1"}])
@patch("costsage.waste_detector._detect_stopped_instances", return_value=[{"resource_type": "ec2_instance", "resource_id": "i-1"}])
def test_detect_waste_resources_collects_all_detectors(
    _mock_instances,
    _mock_volumes,
    _mock_snapshots,
    _mock_elbs,
):
    findings = detect_waste_resources(Mock(), Mock(), Mock(), include_elb_check=True)

    assert len(findings) == 4
    resource_types = {item["resource_type"] for item in findings}
    assert resource_types == {"ec2_instance", "ebs_volume", "ebs_snapshot", "elb"}


@patch("costsage.waste_detector._detect_idle_elbs", side_effect=RuntimeError("boom"))
@patch("costsage.waste_detector._detect_old_snapshots", return_value=[])
@patch("costsage.waste_detector._detect_unattached_volumes", return_value=[])
@patch("costsage.waste_detector._detect_stopped_instances", return_value=[])
def test_detect_waste_resources_tolerates_partial_failures(
    _mock_instances,
    _mock_volumes,
    _mock_snapshots,
    _mock_elbs,
):
    findings = detect_waste_resources(Mock(), Mock(), Mock(), include_elb_check=True)

    assert findings == []


@patch("costsage.waste_detector._detect_idle_elbs")
@patch("costsage.waste_detector._detect_old_snapshots", return_value=[])
@patch("costsage.waste_detector._detect_unattached_volumes", return_value=[])
@patch("costsage.waste_detector._detect_stopped_instances", return_value=[])
def test_detect_waste_resources_skips_elb_when_disabled(
    _mock_instances,
    _mock_volumes,
    _mock_snapshots,
    mock_elb_detector,
):
    mock_elb_detector.return_value = [{"resource_type": "elb", "resource_id": "lb-a"}]

    findings = detect_waste_resources(Mock(), Mock(), Mock(), include_elb_check=False)

    assert findings == []
    mock_elb_detector.assert_not_called()
