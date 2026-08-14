from pathlib import Path
from typing import List, Dict, Any, Optional

from .diff_generator import apply_patch, revert_file


class PatchApplier:
    def __init__(self, backup_dir: str):
        self.backup_dir = Path(backup_dir)
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    def apply_issue(self, issue: Dict[str, Any]) -> Dict[str, Any]:
        file_path = issue.get("file_path", "")
        original = issue.get("original_code", "")
        suggested = issue.get("suggested_code", "")

        if not file_path or not original or not suggested:
            return {
                "issue_id": issue.get("id", ""),
                "file_path": file_path,
                "success": False,
                "error": "Missing file_path, original_code, or suggested_code",
            }

        success, message, backup = apply_patch(
            file_path, original, suggested, str(self.backup_dir),
        )
        return {
            "issue_id": issue.get("id", ""),
            "file_path": file_path,
            "success": success,
            "error": None if success else message,
            "backup_path": backup,
        }

    def apply_batch(self, issues: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        results = []
        for issue in issues:
            result = self.apply_issue(issue)
            results.append(result)
        return results

    def revert_issue(self, file_path: str, backup_path: str) -> Dict[str, Any]:
        success, message = revert_file(file_path, backup_path)
        return {
            "file_path": file_path,
            "success": success,
            "error": None if success else message,
        }
