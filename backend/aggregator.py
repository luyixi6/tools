from collections import defaultdict
from typing import List, Dict, Any


def aggregate_module_results(
    all_issues: List[Dict[str, Any]],
    scan_id: str,
) -> Dict[str, Any]:
    issues_with_ids = []
    severity_counts = defaultdict(int)
    category_counts = defaultdict(int)
    file_issue_counts = defaultdict(int)

    for issue in all_issues:
        issue["scan_id"] = scan_id
        severity_counts[issue.get("severity", "medium")] += 1
        category_counts[issue.get("category", "other")] += 1
        file_issue_counts[issue.get("file_path", "")] += 1
        issues_with_ids.append(issue)

    return {
        "issues": issues_with_ids,
        "summary": {
            "total": len(issues_with_ids),
            "by_severity": dict(severity_counts),
            "by_category": dict(category_counts),
            "files_affected": len(file_issue_counts),
            "top_files": sorted(
                file_issue_counts.items(),
                key=lambda x: x[1], reverse=True,
            )[:20],
        },
    }


def deduplicate_issues(issues: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    unique = []
    for issue in issues:
        key = (
            issue.get("file_path", ""),
            issue.get("line_start", 0),
            issue.get("title", ""),
        )
        if key not in seen:
            seen.add(key)
            unique.append(issue)
    return unique
