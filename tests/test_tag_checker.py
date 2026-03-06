from unittest.mock import Mock

from costsage.tag_checker import check_tag_compliance


def test_check_tag_compliance_groups_missing_tags_by_resource_type():
    tagging_client = Mock()
    paginator = Mock()
    tagging_client.get_paginator.return_value = paginator
    paginator.paginate.return_value = [
        {
            "ResourceTagMappingList": [
                {
                    "ResourceARN": "arn:aws:ec2:us-east-1:111111111111:instance/i-abc",
                    "Tags": [{"Key": "Owner", "Value": "TeamA"}],
                },
                {
                    "ResourceARN": "arn:aws:s3:::costsage-bucket",
                    "Tags": [
                        {"Key": "Owner", "Value": "TeamB"},
                        {"Key": "Project", "Value": "Cost"},
                        {"Key": "Environment", "Value": "prod"},
                    ],
                },
                {
                    "ResourceARN": "arn:aws:ec2:us-east-1:111111111111:volume/vol-123",
                    "Tags": [{"Key": "Owner", "Value": ""}, {"Key": "Project", "Value": "Ops"}],
                },
            ]
        }
    ]

    result = check_tag_compliance(tagging_client, ["Owner", "Project", "Environment"])

    assert result["total_missing_resources"] == 2
    assert "ec2:instance" in result["missing_by_type"]
    assert "ec2:volume" in result["missing_by_type"]
    assert result["required_tags"] == ["Owner", "Project", "Environment"]
