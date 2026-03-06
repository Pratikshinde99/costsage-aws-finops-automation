import json
import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, List
from uuid import uuid4

import boto3
from botocore.exceptions import ClientError

from anomaly_detector import detect_cost_anomaly
from aws_retry import call_with_retries
from config import Settings
from cost_analyzer import analyze_costs
from notifier import (
    build_email_message,
    get_slack_webhook_url,
    send_slack_alert,
    send_sns_email,
)
from report_generator import build_reports, upload_reports_to_s3
from savings_calculator import calculate_potential_savings
from tag_checker import check_tag_compliance
from waste_detector import detect_waste_resources


logger = logging.getLogger()
logger.setLevel(logging.INFO)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if hasattr(record, "execution_id"):
            payload["execution_id"] = getattr(record, "execution_id")
        if hasattr(record, "anomaly_detected"):
            payload["anomaly_detected"] = getattr(record, "anomaly_detected")
        if hasattr(record, "potential_savings"):
            payload["potential_savings"] = getattr(record, "potential_savings")
        if hasattr(record, "projected_monthly_spend"):
            payload["projected_monthly_spend"] = getattr(record, "projected_monthly_spend")
        return json.dumps(payload)


def _configure_logging() -> None:
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)
        return

    for existing_handler in logger.handlers:
        existing_handler.setFormatter(JsonFormatter())


def lambda_handler(event, context):
    _configure_logging()
    settings = Settings.from_env()
    execution_id = getattr(context, "aws_request_id", None) or str(uuid4())

    session = boto3.session.Session(region_name=settings.region)
    ce_client = session.client("ce")
    ec2_client = session.client("ec2")
    tagging_client = session.client("resourcegroupstaggingapi")
    elbv2_client = session.client("elbv2")
    cloudwatch_client = session.client("cloudwatch")
    s3_client = session.client("s3")
    ddb_client = session.client("dynamodb")
    sns_client = session.client("sns")
    secrets_client = session.client("secretsmanager")

    run_date = datetime.now(timezone.utc).date()

    logger.info(
        "Starting CostSage run",
        extra={"execution_id": execution_id},
    )

    lock_acquired = _acquire_daily_run_lock(
        ddb_client=ddb_client,
        table_name=settings.dynamodb_table,
        run_date=run_date.isoformat(),
        execution_id=execution_id,
    )
    if not lock_acquired:
        logger.info(
            "Duplicate daily invocation skipped",
            extra={"execution_id": execution_id},
        )
        return {
            "statusCode": 200,
            "body": json.dumps(
                {
                    "run_date": run_date.isoformat(),
                    "execution_id": execution_id,
                    "skipped": True,
                    "reason": "Run already exists for date",
                }
            ),
        }

    try:
        tag_summary = check_tag_compliance(tagging_client, settings.required_tags)
        waste_findings = detect_waste_resources(
            ec2_client,
            elbv2_client,
            cloudwatch_client,
            include_elb_check=settings.include_elb_check,
        )
        cost_summary = analyze_costs(ce_client, run_date)
        anomaly = detect_cost_anomaly(
            yesterday_total=cost_summary["yesterday_total"],
            seven_day_average=cost_summary["seven_day_average"],
            anomaly_multiplier=settings.anomaly_multiplier,
        )
        savings = calculate_potential_savings(
            waste_findings=waste_findings,
            ec2_default_hourly_usd=settings.ec2_default_hourly_usd,
            ec2_type_hourly_overrides=settings.ec2_type_hourly_overrides,
            ebs_gb_month_usd=settings.ebs_gp3_gb_month_usd,
            snapshot_gb_month_usd=settings.snapshot_gb_month_usd,
        )

        report_payload = _build_report_payload(run_date.isoformat(), cost_summary, anomaly, tag_summary, savings)
        reports = build_reports(report_payload)
        report_keys = upload_reports_to_s3(
            s3_client=s3_client,
            bucket=settings.report_bucket,
            prefix=settings.report_prefix,
            report_date=run_date.isoformat(),
            reports=reports,
            execution_id=execution_id,
        )

        _store_daily_trend(
            ddb_client,
            settings.dynamodb_table,
            run_date.isoformat(),
            cost_summary,
            anomaly,
            savings,
            execution_id,
        )

        active_alerts = _evaluate_alerts(settings, cost_summary, anomaly, tag_summary, savings)
        summary = _build_notification_summary(cost_summary, anomaly, tag_summary, savings)
        if active_alerts:
            webhook_url = get_slack_webhook_url(secrets_client, settings.slack_webhook_secret_name)
            slack_sent = send_slack_alert(webhook_url, summary)

            email_body = build_email_message(summary, active_alerts)
            email_sent = send_sns_email(
                sns_client=sns_client,
                topic_arn=settings.sns_topic_arn,
                subject="CostSage AWS Alert",
                message=email_body,
            )

            if not slack_sent:
                logger.warning("Slack alert was not delivered.", extra={"execution_id": execution_id})
            if not email_sent:
                logger.warning("SNS email alert was not delivered.", extra={"execution_id": execution_id})

        logger.info(
            "Completed CostSage run",
            extra={
                "execution_id": execution_id,
                "anomaly_detected": bool(anomaly.get("anomaly_detected")),
                "potential_savings": savings.get("total_potential_savings", 0.0),
                "projected_monthly_spend": anomaly.get("projected_monthly_spend", 0.0),
            },
        )
        return {
            "statusCode": 200,
            "body": json.dumps(
                {
                    "run_date": run_date.isoformat(),
                    "execution_id": execution_id,
                    "alerts_triggered": active_alerts,
                    "report_keys": report_keys,
                    "potential_savings": savings["total_potential_savings"],
                }
            ),
        }
    except Exception as error:
        _mark_daily_run_failed(
            ddb_client=ddb_client,
            table_name=settings.dynamodb_table,
            run_date=run_date.isoformat(),
            execution_id=execution_id,
            error_message=str(error),
        )
        logger.exception(
            "CostSage run failed",
            extra={"execution_id": execution_id},
        )
        raise


def _acquire_daily_run_lock(
    ddb_client,
    table_name: str,
    run_date: str,
    execution_id: str,
) -> bool:
    try:
        call_with_retries(
            ddb_client.update_item,
            TableName=table_name,
            Key={"Date": {"S": run_date}},
            UpdateExpression=(
                "SET execution_id = :execution_id, #status = :in_progress, started_at = :started_at "
                "REMOVE failed_at, error_message"
            ),
            ConditionExpression="attribute_not_exists(#date) OR #status = :failed",
            ExpressionAttributeNames={"#date": "Date", "#status": "status"},
            ExpressionAttributeValues={
                ":execution_id": {"S": execution_id},
                ":in_progress": {"S": "IN_PROGRESS"},
                ":started_at": {"S": datetime.now(timezone.utc).isoformat()},
                ":failed": {"S": "FAILED"},
            },
        )
        return True
    except ClientError as error:
        if error.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
            return False
        raise


def _build_report_payload(
    run_date: str,
    cost_summary: Dict[str, object],
    anomaly: Dict[str, object],
    tag_summary: Dict[str, object],
    savings: Dict[str, object],
) -> Dict[str, object]:
    return {
        "date": run_date,
        "total_daily_cost": cost_summary["yesterday_total"],
        "seven_day_average": cost_summary["seven_day_average"],
        "anomaly": anomaly,
        "top_service_increases": cost_summary["top_service_increases"],
        "waste_resources": savings["waste_resources"],
        "potential_savings": savings["total_potential_savings"],
        "tag_compliance": tag_summary,
        "month_to_date_total": cost_summary["month_to_date_total"],
    }


def _store_daily_trend(
    ddb_client,
    table_name: str,
    run_date: str,
    cost_summary: Dict[str, object],
    anomaly: Dict[str, object],
    savings: Dict[str, object],
    execution_id: str,
) -> None:
    call_with_retries(
        ddb_client.update_item,
        TableName=table_name,
        Key={"Date": {"S": run_date}},
        UpdateExpression=(
            "SET #status = :status, completed_at = :completed_at, "
            "total_cost = :total_cost, seven_day_avg = :seven_day_avg, "
            "anomaly_detected = :anomaly_detected, potential_savings = :potential_savings, "
            "top_services_json = :top_services_json"
        ),
        ConditionExpression="execution_id = :execution_id",
        ExpressionAttributeNames={"#status": "status"},
        ExpressionAttributeValues={
            ":status": {"S": "COMPLETED"},
            ":completed_at": {"S": datetime.now(timezone.utc).isoformat()},
            ":total_cost": {"N": str(Decimal(str(cost_summary["yesterday_total"])))},
            ":seven_day_avg": {"N": str(Decimal(str(cost_summary["seven_day_average"])))},
            ":anomaly_detected": {"BOOL": bool(anomaly["anomaly_detected"])},
            ":potential_savings": {"N": str(Decimal(str(savings["total_potential_savings"])))},
            ":top_services_json": {"S": json.dumps(cost_summary["top_service_increases"])},
            ":execution_id": {"S": execution_id},
        },
    )


def _mark_daily_run_failed(
    ddb_client,
    table_name: str,
    run_date: str,
    execution_id: str,
    error_message: str,
) -> None:
    try:
        call_with_retries(
            ddb_client.update_item,
            TableName=table_name,
            Key={"Date": {"S": run_date}},
            UpdateExpression="SET #status = :status, failed_at = :failed_at, error_message = :error_message",
            ConditionExpression="execution_id = :execution_id",
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={
                ":status": {"S": "FAILED"},
                ":failed_at": {"S": datetime.now(timezone.utc).isoformat()},
                ":error_message": {"S": error_message[:1000]},
                ":execution_id": {"S": execution_id},
            },
        )
    except Exception:
        logger.exception("Failed to mark daily run as FAILED", extra={"execution_id": execution_id})


def _evaluate_alerts(
    settings: Settings,
    cost_summary: Dict[str, object],
    anomaly: Dict[str, object],
    tag_summary: Dict[str, object],
    savings: Dict[str, object],
) -> List[str]:
    alerts = []
    if settings.monthly_budget_usd > 0:
        budget_ratio = cost_summary["month_to_date_total"] / settings.monthly_budget_usd
        threshold_ratio = settings.budget_alert_threshold_pct / 100.0
        if budget_ratio >= threshold_ratio:
            alerts.append(
                f"Budget consumption is {round(budget_ratio * 100, 2)}% (threshold: {settings.budget_alert_threshold_pct}%)."
            )

    if anomaly.get("anomaly_detected"):
        alerts.append("Cost anomaly detected.")

    if tag_summary.get("total_missing_resources", 0) > settings.missing_tags_alert_threshold:
        alerts.append(
            f"Missing tags count exceeded threshold ({settings.missing_tags_alert_threshold})."
        )

    if savings.get("total_potential_savings", 0.0) > settings.potential_savings_alert_threshold:
        alerts.append(
            f"Potential savings exceeded threshold (${settings.potential_savings_alert_threshold}/month)."
        )

    return alerts


def _build_notification_summary(
    cost_summary: Dict[str, object],
    anomaly: Dict[str, object],
    tag_summary: Dict[str, object],
    savings: Dict[str, object],
) -> Dict[str, object]:
    top_lines = [
        f"- {item.get('service', 'Unknown')}: +${item.get('increase', 0)} ({item.get('increase_pct', 0)}%)"
        for item in cost_summary.get("top_service_increases", [])
    ]
    return {
        "total_daily_cost": cost_summary.get("yesterday_total", 0.0),
        "seven_day_average": cost_summary.get("seven_day_average", 0.0),
        "anomaly_status": "Detected" if anomaly.get("anomaly_detected") else "Normal",
        "projected_monthly_spend": anomaly.get("projected_monthly_spend", 0.0),
        "projected_monthly_baseline": anomaly.get("projected_monthly_baseline", 0.0),
        "projected_monthly_increase_pct": anomaly.get("projected_monthly_increase_pct", 0.0),
        "potential_savings": savings.get("total_potential_savings", 0.0),
        "top_service_lines": top_lines or ["- No increases detected."],
        "missing_tag_count": tag_summary.get("total_missing_resources", 0),
    }