import os
from dataclasses import dataclass, field
from typing import Dict, List


def _parse_csv_env(value: str, default: List[str]) -> List[str]:
    if not value:
        return default
    return [item.strip() for item in value.split(",") if item.strip()]


def _parse_float_env(name: str, default: float) -> float:
    raw_value = os.getenv(name)
    if raw_value in (None, ""):
        return default
    try:
        return float(raw_value)
    except ValueError:
        return default


def _parse_int_env(name: str, default: int) -> int:
    raw_value = os.getenv(name)
    if raw_value in (None, ""):
        return default
    try:
        return int(raw_value)
    except ValueError:
        return default


def _parse_bool_env(name: str, default: bool) -> bool:
    raw_value = os.getenv(name)
    if raw_value in (None, ""):
        return default
    return raw_value.strip().lower() in {"1", "true", "yes", "y"}


@dataclass(frozen=True)
class Settings:
    region: str
    report_bucket: str
    report_prefix: str
    dynamodb_table: str
    sns_topic_arn: str
    slack_webhook_secret_name: str
    required_tags: List[str] = field(default_factory=lambda: ["Owner", "Project", "Environment"])
    anomaly_multiplier: float = 1.30
    missing_tags_alert_threshold: int = 5
    potential_savings_alert_threshold: float = 100.0
    monthly_budget_usd: float = 0.0
    budget_alert_threshold_pct: float = 80.0
    include_elb_check: bool = True
    ec2_default_hourly_usd: float = 0.05
    ebs_gp3_gb_month_usd: float = 0.08
    snapshot_gb_month_usd: float = 0.05
    ec2_type_hourly_overrides: Dict[str, float] = field(default_factory=dict)

    @staticmethod
    def from_env() -> "Settings":
        raw_overrides = os.getenv("EC2_TYPE_HOURLY_OVERRIDES", "")
        overrides: Dict[str, float] = {}
        if raw_overrides:
            for pair in raw_overrides.split(","):
                if ":" not in pair:
                    continue
                instance_type, price = pair.split(":", 1)
                instance_type = instance_type.strip()
                if not instance_type:
                    continue
                try:
                    overrides[instance_type] = float(price)
                except ValueError:
                    continue

        settings = Settings(
            region=os.getenv("AWS_REGION", "us-east-1"),
            report_bucket=os.getenv("REPORT_BUCKET", ""),
            report_prefix=os.getenv("REPORT_PREFIX", "daily"),
            dynamodb_table=os.getenv("DDB_TABLE", "CostTrends"),
            sns_topic_arn=os.getenv("SNS_TOPIC_ARN", ""),
            slack_webhook_secret_name=os.getenv("SLACK_WEBHOOK_SECRET_NAME", ""),
            required_tags=_parse_csv_env(
                os.getenv("REQUIRED_TAGS", ""),
                ["Owner", "Project", "Environment"],
            ),
            anomaly_multiplier=max(_parse_float_env("ANOMALY_MULTIPLIER", 1.30), 1.0),
            missing_tags_alert_threshold=max(_parse_int_env("MISSING_TAGS_ALERT_THRESHOLD", 5), 0),
            potential_savings_alert_threshold=max(
                _parse_float_env("POTENTIAL_SAVINGS_ALERT_THRESHOLD", 100.0),
                0.0,
            ),
            monthly_budget_usd=max(_parse_float_env("MONTHLY_BUDGET_USD", 0.0), 0.0),
            budget_alert_threshold_pct=_parse_float_env("BUDGET_ALERT_THRESHOLD_PCT", 80.0),
            include_elb_check=_parse_bool_env("INCLUDE_ELB_CHECK", True),
            ec2_default_hourly_usd=max(_parse_float_env("EC2_DEFAULT_HOURLY_USD", 0.05), 0.0),
            ebs_gp3_gb_month_usd=max(_parse_float_env("EBS_GP3_GB_MONTH_USD", 0.08), 0.0),
            snapshot_gb_month_usd=max(_parse_float_env("SNAPSHOT_GB_MONTH_USD", 0.05), 0.0),
            ec2_type_hourly_overrides=overrides,
        )
        settings.validate()
        return settings

    def validate(self) -> None:
        errors: List[str] = []

        if not self.region.strip():
            errors.append("AWS region must not be empty.")
        if not self.report_bucket.strip():
            errors.append("REPORT_BUCKET environment variable must be provided.")
        if not self.report_prefix.strip():
            errors.append("REPORT_PREFIX must not be empty.")
        if not self.dynamodb_table.strip():
            errors.append("DDB_TABLE must not be empty.")
        if self.slack_webhook_secret_name and self.slack_webhook_secret_name.strip().lower().startswith(("http://", "https://")):
            errors.append("SLACK_WEBHOOK_SECRET_NAME must be a Secrets Manager secret name, not a raw webhook URL.")

        if not self.required_tags:
            errors.append("At least one required tag must be configured.")
        elif any(not str(tag).strip() for tag in self.required_tags):
            errors.append("REQUIRED_TAGS must not contain empty tag names.")

        if self.anomaly_multiplier < 1.0:
            errors.append("ANOMALY_MULTIPLIER must be greater than or equal to 1.0.")
        if self.missing_tags_alert_threshold < 0:
            errors.append("MISSING_TAGS_ALERT_THRESHOLD must be non-negative.")
        if self.potential_savings_alert_threshold < 0:
            errors.append("POTENTIAL_SAVINGS_ALERT_THRESHOLD must be non-negative.")
        if self.monthly_budget_usd < 0:
            errors.append("MONTHLY_BUDGET_USD must be non-negative.")
        if self.budget_alert_threshold_pct < 0 or self.budget_alert_threshold_pct > 100:
            errors.append("BUDGET_ALERT_THRESHOLD_PCT must be between 0 and 100.")

        if self.ec2_default_hourly_usd < 0 or self.ebs_gp3_gb_month_usd < 0 or self.snapshot_gb_month_usd < 0:
            errors.append("Default pricing values must be non-negative.")

        negative_overrides = [
            instance_type
            for instance_type, price in self.ec2_type_hourly_overrides.items()
            if price < 0
        ]
        if negative_overrides:
            errors.append(
                "EC2_TYPE_HOURLY_OVERRIDES contains negative prices for: "
                + ", ".join(sorted(negative_overrides))
            )

        if errors:
            raise ValueError("Invalid configuration: " + " ".join(errors))