from datetime import date, timedelta
import logging
from typing import Dict, List, Tuple

try:
    from .aws_retry import call_with_retries
except ImportError:  # pragma: no cover
    from aws_retry import call_with_retries


logger = logging.getLogger(__name__)


def _safe_amount(value: object) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return 0.0
    return parsed if parsed >= 0 else 0.0


def analyze_costs(ce_client, reference_date: date) -> Dict[str, object]:
    yesterday = reference_date - timedelta(days=1)
    day_before = reference_date - timedelta(days=2)
    seven_day_start = reference_date - timedelta(days=8)

    yesterday_costs = _get_service_costs_for_day(ce_client, yesterday)
    previous_day_costs = _get_service_costs_for_day(ce_client, day_before)
    seven_day_daily = _get_daily_total_costs(ce_client, seven_day_start, yesterday)
    mtd_cost = _get_month_to_date_total(ce_client, reference_date)

    yesterday_total = sum(yesterday_costs.values())
    seven_day_avg = (
        sum(seven_day_daily.values()) / len(seven_day_daily)
        if seven_day_daily
        else 0.0
    )

    top_service_increases = _top_service_increases(yesterday_costs, previous_day_costs, top_n=5)

    return {
        "yesterday": yesterday.isoformat(),
        "yesterday_total": round(yesterday_total, 2),
        "seven_day_average": round(seven_day_avg, 2),
        "service_costs_yesterday": _round_cost_map(yesterday_costs),
        "service_costs_previous_day": _round_cost_map(previous_day_costs),
        "top_service_increases": top_service_increases,
        "month_to_date_total": round(mtd_cost, 2),
        "daily_totals_previous_7_days": _round_cost_map(seven_day_daily),
    }


def _get_service_costs_for_day(ce_client, target_day: date) -> Dict[str, float]:
    start = target_day.isoformat()
    end = (target_day + timedelta(days=1)).isoformat()

    costs: Dict[str, float] = {}
    next_page_token = None

    try:
        while True:
            request_params = {
                "TimePeriod": {"Start": start, "End": end},
                "Granularity": "DAILY",
                "Metrics": ["UnblendedCost"],
                "GroupBy": [{"Type": "DIMENSION", "Key": "SERVICE"}],
            }
            if next_page_token:
                request_params["NextPageToken"] = next_page_token

            response = call_with_retries(ce_client.get_cost_and_usage, **request_params)
            for result in response.get("ResultsByTime", []):
                for group in result.get("Groups", []):
                    service = group.get("Keys", ["Unknown"])[0]
                    amount = _safe_amount(group.get("Metrics", {}).get("UnblendedCost", {}).get("Amount"))
                    costs[service] = round(costs.get(service, 0.0) + amount, 10)

            next_page_token = response.get("NextPageToken")
            if not next_page_token:
                break
    except Exception as error:
        logger.warning("Failed to fetch service costs for %s: %s", target_day.isoformat(), error)

    return costs


def _get_daily_total_costs(ce_client, start_inclusive: date, end_exclusive: date) -> Dict[str, float]:
    values: Dict[str, float] = {}

    try:
        response = call_with_retries(
            ce_client.get_cost_and_usage,
            TimePeriod={"Start": start_inclusive.isoformat(), "End": end_exclusive.isoformat()},
            Granularity="DAILY",
            Metrics=["UnblendedCost"],
        )
        for item in response.get("ResultsByTime", []):
            day = item.get("TimePeriod", {}).get("Start")
            if not day:
                continue
            amount = _safe_amount(item.get("Total", {}).get("UnblendedCost", {}).get("Amount"))
            values[day] = amount
    except Exception as error:
        logger.warning(
            "Failed to fetch daily totals from %s to %s: %s",
            start_inclusive.isoformat(),
            end_exclusive.isoformat(),
            error,
        )

    return values


def _get_month_to_date_total(ce_client, reference_date: date) -> float:
    month_start = reference_date.replace(day=1)
    try:
        response = call_with_retries(
            ce_client.get_cost_and_usage,
            TimePeriod={"Start": month_start.isoformat(), "End": reference_date.isoformat()},
            Granularity="MONTHLY",
            Metrics=["UnblendedCost"],
        )
        if not response.get("ResultsByTime"):
            return 0.0
        return _safe_amount(response.get("ResultsByTime", [{}])[0].get("Total", {}).get("UnblendedCost", {}).get("Amount"))
    except Exception as error:
        logger.warning("Failed to fetch month-to-date cost for %s: %s", reference_date.isoformat(), error)
        return 0.0


def _top_service_increases(
    current: Dict[str, float],
    previous: Dict[str, float],
    top_n: int,
) -> List[Dict[str, float]]:
    deltas: List[Tuple[str, float, float, float]] = []
    all_services = set(current.keys()) | set(previous.keys())
    for service in all_services:
        cur = current.get(service, 0.0)
        prev = previous.get(service, 0.0)
        delta = cur - prev
        if delta <= 0:
            continue
        deltas.append((service, prev, cur, delta))

    deltas.sort(key=lambda item: item[3], reverse=True)
    top = []
    for service, prev, cur, delta in deltas[:top_n]:
        pct = (delta / prev * 100.0) if prev > 0 else 100.0
        top.append(
            {
                "service": service,
                "previous_day": round(prev, 2),
                "yesterday": round(cur, 2),
                "increase": round(delta, 2),
                "increase_pct": round(pct, 2),
            }
        )
    return top


def _round_cost_map(values: Dict[str, float]) -> Dict[str, float]:
    return {key: round(value, 2) for key, value in values.items()}