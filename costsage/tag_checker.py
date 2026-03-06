from collections import defaultdict
from typing import Dict, List


def check_tag_compliance(tagging_client, required_tags: List[str]) -> Dict[str, object]:
    missing_by_type: Dict[str, List[Dict[str, object]]] = defaultdict(list)
    total_missing_resources = 0

    paginator = tagging_client.get_paginator("get_resources")
    for page in paginator.paginate(ResourcesPerPage=100):
        for mapping in page.get("ResourceTagMappingList", []):
            arn = mapping.get("ResourceARN", "unknown")
            tags = {tag["Key"]: tag.get("Value", "") for tag in mapping.get("Tags", [])}
            missing = [tag for tag in required_tags if tag not in tags or not str(tags[tag]).strip()]
            if not missing:
                continue

            resource_type = _extract_resource_type(arn)
            missing_by_type[resource_type].append(
                {
                    "resource_arn": arn,
                    "missing_tags": missing,
                }
            )
            total_missing_resources += 1

    return {
        "required_tags": required_tags,
        "total_missing_resources": total_missing_resources,
        "missing_by_type": dict(missing_by_type),
    }


def _extract_resource_type(resource_arn: str) -> str:
    parts = resource_arn.split(":", 5)
    if len(parts) < 6:
        return "unknown"
    service = parts[2] or "unknown"
    resource_part = parts[5]
    subtype = resource_part.split("/")[0].split(":")[0]
    return f"{service}:{subtype}" if subtype else service