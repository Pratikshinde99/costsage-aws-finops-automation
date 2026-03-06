import json
import logging
import re
from urllib import request
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from typing import Dict, List

try:
    from .aws_retry import call_with_retries
except ImportError:  # pragma: no cover
    from aws_retry import call_with_retries


logger = logging.getLogger(__name__)


_SLACK_WEBHOOK_PATTERN = re.compile(r"https://hooks\.slack\.com/services/[^\s\"'<>]+")


def _normalize_webhook_url(value: object) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip().strip('"').strip("'")


def _sanitize_extracted_url(value: str) -> str:
    sanitized = _normalize_webhook_url(value)
    return sanitized.rstrip("\\}])>,.;")


def _extract_webhook_url_from_secret(secret_string: str) -> str:
    candidate = _normalize_webhook_url(secret_string)
    if not candidate:
        return ""

    parsed_value: object = candidate
    for _ in range(3):
        if isinstance(parsed_value, dict):
            for key in ("webhook_url", "slack_webhook_url", "url"):
                maybe_url = _normalize_webhook_url(parsed_value.get(key))
                if maybe_url:
                    parsed_value = maybe_url
                    break
            else:
                break
            continue

        if isinstance(parsed_value, str):
            text_value = _normalize_webhook_url(parsed_value)
            if text_value.startswith(("http://", "https://")):
                return text_value

            try:
                parsed_value = json.loads(text_value)
                continue
            except json.JSONDecodeError:
                match = _SLACK_WEBHOOK_PATTERN.search(text_value)
                return _sanitize_extracted_url(match.group(0)) if match else ""

        break

    normalized = _normalize_webhook_url(parsed_value)
    if normalized.startswith(("http://", "https://")):
        return normalized

    match = _SLACK_WEBHOOK_PATTERN.search(candidate)
    return _sanitize_extracted_url(match.group(0)) if match else ""


def get_slack_webhook_url(secrets_client, secret_name: str) -> str:
    if not secret_name:
        return ""
    try:
        response = call_with_retries(
            secrets_client.get_secret_value,
            SecretId=secret_name,
        )
    except Exception as error:
        logger.warning("Unable to retrieve Slack webhook secret '%s': %s", secret_name, error)
        return ""

    secret_string = response.get("SecretString", "")
    if not secret_string:
        logger.warning("Slack secret '%s' is empty.", secret_name)
        return ""

    webhook_url = _extract_webhook_url_from_secret(secret_string)
    if not webhook_url:
        logger.warning("Slack secret '%s' did not contain a valid webhook URL.", secret_name)
    return webhook_url


def send_slack_alert(webhook_url: str, summary: Dict[str, object]) -> bool:
    webhook_url = _normalize_webhook_url(webhook_url)
    if not webhook_url:
        return False

    parsed_url = urlparse(webhook_url)
    if parsed_url.scheme not in {"http", "https"}:
        logger.warning("Slack notification skipped because webhook URL scheme is invalid.")
        return False

    total_daily_cost = summary.get("total_daily_cost", 0)
    seven_day_average = summary.get("seven_day_average", 0)
    anomaly_status = summary.get("anomaly_status", "Unknown")
    potential_savings = summary.get("potential_savings", 0)
    projected_monthly_spend = summary.get("projected_monthly_spend", 0)
    projected_monthly_baseline = summary.get("projected_monthly_baseline", 0)
    projected_monthly_increase_pct = summary.get("projected_monthly_increase_pct", 0)
    top_service_lines = summary.get("top_service_lines") or ["No increases detected."]
    missing_tag_count = summary.get("missing_tag_count", 0)

    body = {
        "blocks": [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": "CostSage AWS Alert"},
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Total Daily Cost*\n${total_daily_cost}",
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*7-Day Average*\n${seven_day_average}",
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Anomaly*\n{anomaly_status}",
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Potential Savings*\n${potential_savings}/month",
                    },
                ],
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Projected Monthly Spend*\n${projected_monthly_spend}",
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*7-Day Baseline Projection*\n${projected_monthly_baseline}",
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Burn Increase vs Baseline*\n{projected_monthly_increase_pct}%",
                    },
                ],
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        "*Top Service Increases*\n"
                        + "\n".join(top_service_lines)
                    ),
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        "*Tag Compliance*\n"
                        f"Missing tagged resources: {missing_tag_count}"
                    ),
                },
            },
        ]
    }

    req = request.Request(
        webhook_url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=10):
            return True
    except (HTTPError, URLError, TimeoutError) as error:
        logger.warning("Slack notification failed: %s", error)
    except Exception as error:
        logger.warning("Unexpected Slack notification error: %s", error)
    return False


def send_sns_email(sns_client, topic_arn: str, subject: str, message: str) -> bool:
    if not topic_arn:
        return False
    try:
        call_with_retries(
            sns_client.publish,
            TopicArn=topic_arn,
            Subject=subject,
            Message=message,
        )
        return True
    except Exception as error:
        logger.warning("SNS publish failed for topic '%s': %s", topic_arn, error)
        return False


def build_email_message(summary: Dict[str, object], active_alerts: List[str]) -> str:
    total_daily_cost = summary.get("total_daily_cost", 0)
    seven_day_average = summary.get("seven_day_average", 0)
    anomaly_status = summary.get("anomaly_status", "Unknown")
    potential_savings = summary.get("potential_savings", 0)
    projected_monthly_spend = summary.get("projected_monthly_spend", 0)
    projected_monthly_baseline = summary.get("projected_monthly_baseline", 0)
    projected_monthly_increase_pct = summary.get("projected_monthly_increase_pct", 0)
    missing_tag_count = summary.get("missing_tag_count", 0)
    top_service_lines = summary.get("top_service_lines") or ["- No increases detected."]

    lines = [
        "CostSage AWS Alert Summary",
        "",
        f"Total daily cost: ${total_daily_cost}",
        f"7-day average: ${seven_day_average}",
        f"Anomaly: {anomaly_status}",
        f"Projected monthly spend (yesterday x 30): ${projected_monthly_spend}",
        f"Projected monthly baseline (7-day avg x 30): ${projected_monthly_baseline}",
        f"Burn increase vs baseline: {projected_monthly_increase_pct}%",
        f"Potential monthly savings: ${potential_savings}",
        f"Missing tags resources: {missing_tag_count}",
        "",
        "Triggered Alerts:",
    ]
    lines.extend([f"- {alert}" for alert in active_alerts] or ["- None"])
    lines.append("")
    lines.append("Top Service Increases:")
    lines.extend(top_service_lines)
    return "\n".join(lines)