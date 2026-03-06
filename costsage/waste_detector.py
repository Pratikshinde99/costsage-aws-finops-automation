import re
from datetime import datetime, timedelta, timezone
import logging
from typing import Dict, List, Optional

try:
    from .aws_retry import call_with_retries
except ImportError:  # pragma: no cover
    from aws_retry import call_with_retries


STATE_TRANSITION_TS = re.compile(r"\((\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) GMT\)")
logger = logging.getLogger(__name__)


def detect_waste_resources(
    ec2_client,
    elbv2_client,
    cloudwatch_client,
    include_elb_check: bool = True,
) -> List[Dict[str, object]]:
    findings: List[Dict[str, object]] = []
    try:
        findings.extend(_detect_stopped_instances(ec2_client))
    except Exception as error:
        logger.warning("Stopped instance detection failed: %s", error)

    try:
        findings.extend(_detect_unattached_volumes(ec2_client))
    except Exception as error:
        logger.warning("Unattached volume detection failed: %s", error)

    try:
        findings.extend(_detect_old_snapshots(ec2_client))
    except Exception as error:
        logger.warning("Old snapshot detection failed: %s", error)

    if include_elb_check:
        try:
            findings.extend(_detect_idle_elbs(elbv2_client, cloudwatch_client))
        except Exception as error:
            logger.warning("Idle load balancer detection failed: %s", error)

    return findings


def _detect_stopped_instances(ec2_client) -> List[Dict[str, object]]:
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=7)
    results: List[Dict[str, object]] = []

    paginator = ec2_client.get_paginator("describe_instances")
    for page in paginator.paginate(
        Filters=[{"Name": "instance-state-name", "Values": ["stopped"]}]
    ):
        for reservation in page.get("Reservations", []):
            for instance in reservation.get("Instances", []):
                stopped_at = _parse_stopped_timestamp(instance.get("StateTransitionReason", ""))
                if stopped_at and stopped_at.tzinfo is None:
                    stopped_at = stopped_at.replace(tzinfo=timezone.utc)
                if not stopped_at or stopped_at > cutoff:
                    continue

                results.append(
                    {
                        "resource_type": "ec2_instance",
                        "resource_id": instance.get("InstanceId"),
                        "instance_type": instance.get("InstanceType"),
                        "creation_date": instance.get("LaunchTime").isoformat()
                        if instance.get("LaunchTime")
                        else None,
                        "reason_date": stopped_at.isoformat(),
                        "recommendation": "Instance has been stopped for more than 7 days. Consider terminating if unused.",
                    }
                )
    return results


def _detect_unattached_volumes(ec2_client) -> List[Dict[str, object]]:
    results: List[Dict[str, object]] = []
    paginator = ec2_client.get_paginator("describe_volumes")
    for page in paginator.paginate(
        Filters=[{"Name": "status", "Values": ["available"]}]
    ):
        for volume in page.get("Volumes", []):
            if volume.get("Attachments"):
                continue
            results.append(
                {
                    "resource_type": "ebs_volume",
                    "resource_id": volume.get("VolumeId"),
                    "size_gb": volume.get("Size", 0),
                    "volume_type": volume.get("VolumeType", "gp3"),
                    "creation_date": volume.get("CreateTime").isoformat()
                    if volume.get("CreateTime")
                    else None,
                    "recommendation": "Volume is unattached. Consider deleting if no longer needed.",
                }
            )
    return results


def _detect_old_snapshots(ec2_client) -> List[Dict[str, object]]:
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=90)
    results: List[Dict[str, object]] = []

    paginator = ec2_client.get_paginator("describe_snapshots")
    for page in paginator.paginate(OwnerIds=["self"]):
        for snapshot in page.get("Snapshots", []):
            start_time = snapshot.get("StartTime")
            if not start_time:
                continue
            if start_time.tzinfo is None:
                start_time = start_time.replace(tzinfo=timezone.utc)
            if start_time > cutoff:
                continue

            results.append(
                {
                    "resource_type": "ebs_snapshot",
                    "resource_id": snapshot.get("SnapshotId"),
                    "size_gb": snapshot.get("VolumeSize", 0),
                    "creation_date": start_time.isoformat(),
                    "recommendation": "Snapshot is older than 90 days. Consider lifecycle cleanup.",
                }
            )
    return results


def _detect_idle_elbs(elbv2_client, cloudwatch_client) -> List[Dict[str, object]]:
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=7)
    results: List[Dict[str, object]] = []

    paginator = elbv2_client.get_paginator("describe_load_balancers")
    for page in paginator.paginate():
        for lb in page.get("LoadBalancers", []):
            lb_arn = lb.get("LoadBalancerArn")
            lb_name = lb.get("LoadBalancerName")
            if not lb_arn or not lb_name:
                continue

            try:
                metric = call_with_retries(
                    cloudwatch_client.get_metric_statistics,
                    Namespace="AWS/ApplicationELB",
                    MetricName="RequestCount",
                    Dimensions=[{"Name": "LoadBalancer", "Value": lb_arn.split("loadbalancer/")[-1]}],
                    StartTime=start,
                    EndTime=now,
                    Period=86400,
                    Statistics=["Sum"],
                )
            except Exception as error:
                logger.warning("CloudWatch metric lookup failed for ELB %s: %s", lb_name, error)
                continue

            total_requests = sum(point.get("Sum", 0.0) for point in metric.get("Datapoints", []))
            if total_requests > 0:
                continue

            created_time = lb.get("CreatedTime")
            results.append(
                {
                    "resource_type": "elb",
                    "resource_id": lb_name,
                    "creation_date": created_time.isoformat() if created_time else None,
                    "request_count_7d": total_requests,
                    "recommendation": "Load balancer has zero requests in 7 days. Review and remove if idle.",
                }
            )

    return results


def _parse_stopped_timestamp(reason: str) -> Optional[datetime]:
    match = STATE_TRANSITION_TS.search(reason or "")
    if not match:
        return None
    timestamp = datetime.strptime(match.group(1), "%Y-%m-%d %H:%M:%S")
    return timestamp.replace(tzinfo=timezone.utc)