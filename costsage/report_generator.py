import csv
import html
import io
import json
import logging
from datetime import datetime, timezone
from typing import Dict

from botocore.exceptions import ClientError

try:
    from .aws_retry import call_with_retries
except ImportError:  # pragma: no cover
    from aws_retry import call_with_retries


logger = logging.getLogger(__name__)


def build_reports(report_payload: Dict[str, object]) -> Dict[str, str]:
    generated_at = datetime.now(timezone.utc).isoformat()
    payload = dict(report_payload)
    payload["generated_at"] = generated_at
    return {
        "json": json.dumps(payload, indent=2),
        "html": _build_html(payload),
        "csv": _build_csv(payload),
    }


def upload_reports_to_s3(
    s3_client,
    bucket: str,
    prefix: str,
    report_date: str,
    reports: Dict[str, str],
    execution_id: str,
) -> Dict[str, str]:
    normalized_prefix = (prefix or "daily").strip("/")

    date_prefix = f"{normalized_prefix}/{report_date}"
    daily_json_key = f"{date_prefix}/report.json"

    if _s3_object_exists(s3_client, bucket, daily_json_key):
        immutable_prefix = f"{date_prefix}/runs/{execution_id}"
        logger.info("Date report already exists, writing immutable run path: %s", immutable_prefix)
    else:
        immutable_prefix = date_prefix

    keys = {
        "json": f"{immutable_prefix}/report.json",
        "html": f"{immutable_prefix}/report.html",
        "csv": f"{immutable_prefix}/report.csv",
        "latest_json": f"{normalized_prefix}/latest/report.json",
        "latest_html": f"{normalized_prefix}/latest/report.html",
        "latest_csv": f"{normalized_prefix}/latest/report.csv",
    }

    content_types = {
        "json": "application/json",
        "html": "text/html",
        "csv": "text/csv",
        "latest_json": "application/json",
        "latest_html": "text/html",
        "latest_csv": "text/csv",
    }

    report_alias_map = {
        "json": "json",
        "html": "html",
        "csv": "csv",
        "latest_json": "json",
        "latest_html": "html",
        "latest_csv": "csv",
    }

    for report_type, key in keys.items():
        source_type = report_alias_map[report_type]
        body = reports.get(report_type, "")
        if not body:
            body = reports.get(source_type, "")
        call_with_retries(
            s3_client.put_object,
            Bucket=bucket,
            Key=key,
            Body=body.encode("utf-8"),
            ContentType=content_types[report_type],
            ServerSideEncryption="AES256",
        )
    return keys


def _s3_object_exists(s3_client, bucket: str, key: str) -> bool:
    try:
        call_with_retries(s3_client.head_object, Bucket=bucket, Key=key)
        return True
    except ClientError as error:
        error_code = error.response.get("Error", {}).get("Code", "")
        if error_code in {"404", "NoSuchKey", "NotFound"}:
            return False
        raise


def _build_html(payload: Dict[str, object]) -> str:
    top_services = payload.get("top_service_increases", [])
    waste = payload.get("waste_resources", [])
    tag_summary = payload.get("tag_compliance", {})
    anomaly = payload.get("anomaly", {})

    top_rows = "".join(
        [
            "<tr>"
            f"<td>{html.escape(str(item.get('service', '')))}</td>"
            f"<td>{item.get('previous_day', 0)}</td>"
            f"<td>{item.get('yesterday', 0)}</td>"
            f"<td>{item.get('increase', 0)}</td>"
            "</tr>"
            for item in top_services
        ]
    )
    if not top_rows:
        top_rows = "<tr><td colspan=\"4\">No increases detected.</td></tr>"

    waste_rows = "".join(
        [
            "<tr>"
            f"<td>{html.escape(str(item.get('resource_type', '')))}</td>"
            f"<td>{html.escape(str(item.get('resource_id', '')))}</td>"
            f"<td>{html.escape(str(item.get('creation_date', '')))}</td>"
            f"<td>{item.get('estimated_monthly_cost', 0)}</td>"
            f"<td>{html.escape(str(item.get('recommendation', '')))}</td>"
            "</tr>"
            for item in waste
        ]
    )
    if not waste_rows:
        waste_rows = "<tr><td colspan=\"5\">No waste resources detected.</td></tr>"

    report_date = html.escape(str(payload.get("date", "")))
    total_daily_cost = payload.get("total_daily_cost", 0)
    seven_day_average = payload.get("seven_day_average", 0)
    anomaly_message = html.escape(str(anomaly.get("message", "")))
    potential_savings = payload.get("potential_savings", 0)
    missing_tag_count = tag_summary.get("total_missing_resources", 0)

    return f"""
<html>
  <head>
    <meta charset=\"utf-8\" />
    <title>CostSage AWS Daily Report</title>
    <style>
      body {{ font-family: Arial, sans-serif; margin: 24px; }}
      h1, h2 {{ color: #1f2937; }}
      table {{ border-collapse: collapse; width: 100%; margin-bottom: 20px; }}
      th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
      th {{ background: #f3f4f6; }}
    </style>
  </head>
  <body>
    <h1>CostSage AWS Daily Report</h1>
    <p><strong>Date:</strong> {report_date}</p>
    <p><strong>Total Daily Cost:</strong> ${total_daily_cost}</p>
    <p><strong>7-Day Average:</strong> ${seven_day_average}</p>
    <p><strong>Anomaly:</strong> {anomaly_message}</p>
    <p><strong>Potential Monthly Savings:</strong> ${potential_savings}</p>
    <p><strong>Missing Tagged Resources:</strong> {missing_tag_count}</p>

    <h2>Top 5 Service Increases</h2>
    <table>
      <tr><th>Service</th><th>Previous Day</th><th>Yesterday</th><th>Increase</th></tr>
      {top_rows}
    </table>

    <h2>Waste Resources</h2>
    <table>
      <tr><th>Type</th><th>ID</th><th>Creation Date</th><th>Estimated Monthly Cost</th><th>Recommendation</th></tr>
      {waste_rows}
    </table>
  </body>
</html>
"""


def _build_csv(payload: Dict[str, object]) -> str:
    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow(["metric", "value"])
    writer.writerow(["date", payload.get("date", "")])
    writer.writerow(["total_daily_cost", payload.get("total_daily_cost", 0)])
    writer.writerow(["seven_day_average", payload.get("seven_day_average", 0)])
    writer.writerow(["anomaly_detected", payload.get("anomaly", {}).get("anomaly_detected", False)])
    writer.writerow(["potential_savings", payload.get("potential_savings", 0)])
    writer.writerow(["missing_tag_resources", payload.get("tag_compliance", {}).get("total_missing_resources", 0)])

    writer.writerow([])
    writer.writerow(["top_service", "previous_day", "yesterday", "increase", "increase_pct"])
    for item in payload.get("top_service_increases", []):
        writer.writerow(
            [
                item.get("service", ""),
                item.get("previous_day", 0),
                item.get("yesterday", 0),
                item.get("increase", 0),
                item.get("increase_pct", 0),
            ]
        )

    writer.writerow([])
    writer.writerow(["waste_type", "resource_id", "creation_date", "estimated_monthly_cost", "recommendation"])
    for item in payload.get("waste_resources", []):
        writer.writerow(
            [
                item.get("resource_type", ""),
                item.get("resource_id", ""),
                item.get("creation_date", ""),
                item.get("estimated_monthly_cost", 0),
                item.get("recommendation", ""),
            ]
        )

    return output.getvalue()