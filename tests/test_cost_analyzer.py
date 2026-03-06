from datetime import date
from unittest.mock import Mock

from costsage.cost_analyzer import analyze_costs


def test_analyze_costs_with_mocked_cost_explorer_responses():
    ce_client = Mock()
    ce_client.get_cost_and_usage.side_effect = [
        {
            "ResultsByTime": [
                {
                    "Groups": [
                        {
                            "Keys": ["Amazon EC2"],
                            "Metrics": {"UnblendedCost": {"Amount": "10"}},
                        }
                    ]
                }
            ],
            "NextPageToken": "token-1",
        },
        {
            "ResultsByTime": [
                {
                    "Groups": [
                        {
                            "Keys": ["Amazon S3"],
                            "Metrics": {"UnblendedCost": {"Amount": "2"}},
                        }
                    ]
                }
            ]
        },
        {
            "ResultsByTime": [
                {
                    "Groups": [
                        {
                            "Keys": ["Amazon EC2"],
                            "Metrics": {"UnblendedCost": {"Amount": "8"}},
                        },
                        {
                            "Keys": ["Amazon S3"],
                            "Metrics": {"UnblendedCost": {"Amount": "1"}},
                        },
                    ]
                }
            ]
        },
        {
            "ResultsByTime": [
                {"TimePeriod": {"Start": "2026-02-22"}, "Total": {"UnblendedCost": {"Amount": "10"}}},
                {"TimePeriod": {"Start": "2026-02-23"}, "Total": {"UnblendedCost": {"Amount": "11"}}},
                {"TimePeriod": {"Start": "2026-02-24"}, "Total": {"UnblendedCost": {"Amount": "12"}}},
                {"TimePeriod": {"Start": "2026-02-25"}, "Total": {"UnblendedCost": {"Amount": "13"}}},
                {"TimePeriod": {"Start": "2026-02-26"}, "Total": {"UnblendedCost": {"Amount": "14"}}},
                {"TimePeriod": {"Start": "2026-02-27"}, "Total": {"UnblendedCost": {"Amount": "15"}}},
                {"TimePeriod": {"Start": "2026-02-28"}, "Total": {"UnblendedCost": {"Amount": "16"}}},
            ]
        },
        {
            "ResultsByTime": [
                {
                    "Total": {
                        "UnblendedCost": {
                            "Amount": "250"
                        }
                    }
                }
            ]
        },
    ]

    result = analyze_costs(ce_client, date(2026, 3, 1))

    assert result["yesterday_total"] == 12.0
    assert result["seven_day_average"] == 13.0
    assert result["month_to_date_total"] == 250.0
    assert len(result["top_service_increases"]) == 2
    assert result["top_service_increases"][0]["service"] == "Amazon EC2"
