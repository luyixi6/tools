import json
from typing import Dict, Any, List


def parse_analysis_response(response: Dict[str, Any]) -> List[Dict[str, Any]]:
    parsed = []

    if "issues" in response:
        issues = response["issues"]
    elif isinstance(response, list):
        issues = response
    else:
        return parsed

    for issue in issues:
        if not isinstance(issue, dict):
            continue
        normalized = {
            "severity": _normalize_severity(issue.get("severity", "medium")),
            "category": _normalize_category(issue.get("category", "other")),
            "file_path": issue.get("file", ""),
            "title": issue.get("title", "Untitled issue"),
            "description": issue.get("description", ""),
            "line_start": int(issue.get("line_start", 0) or 0),
            "line_end": int(issue.get("line_end", 0) or 0),
            "original_code": issue.get("original_code", ""),
            "suggested_code": issue.get("suggested_code", ""),
            "rule_reference": issue.get("rule_reference", ""),
        }
        if normalized["title"] and normalized.get("file_path"):
            parsed.append(normalized)

    return parsed


def _normalize_severity(value: str) -> str:
    value = str(value).lower().strip()
    valid = {"critical", "high", "medium", "low"}
    if value in valid:
        return value
    if "crit" in value:
        return "critical"
    if "high" in value:
        return "high"
    if "low" in value:
        return "low"
    return "medium"


def _normalize_category(value: str) -> str:
    value = str(value).lower().strip()
    mapping = {
        "memory": "memory_safety",
        "mem": "memory_safety",
        "leak": "memory_safety",
        "concurrency": "concurrency",
        "thread": "concurrency",
        "race": "concurrency",
        "exception": "exception_safety",
        "except": "exception_safety",
        "modern": "modern_cpp",
        "cpp": "modern_cpp",
        "style": "code_style",
        "format": "code_style",
        "type": "type_safety",
        "cast": "type_safety",
        "ub": "undefined_behavior",
        "undefined": "undefined_behavior",
        "perform": "performance",
        "perf": "performance",
    }
    for key, mapped in mapping.items():
        if key in value:
            return mapped
    return "other"
