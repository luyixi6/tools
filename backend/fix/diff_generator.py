from pathlib import Path
import difflib
from typing import Optional, Tuple


def generate_diff(original: str, modified: str,
                   file_path: str = "file") -> str:
    original_lines = original.splitlines(keepends=True)
    modified_lines = modified.splitlines(keepends=True)

    diff = difflib.unified_diff(
        original_lines, modified_lines,
        fromfile=f"a/{file_path}",
        tofile=f"b/{file_path}",
    )
    return "".join(diff)


def apply_patch(file_path: str, old_code: str, new_code: str,
                backup_dir: str) -> Tuple[bool, str, Optional[str]]:
    path = Path(file_path)
    if not path.exists():
        return False, f"File not found: {file_path}", None

    try:
        content = path.read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        return False, f"Cannot read file: {e}", None

    if old_code not in content:
        return False, f"original_code not found in {file_path}", None

    backup_path = Path(backup_dir) / f"{path.name}.bak"
    try:
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        backup_path.write_text(content, encoding="utf-8")
    except Exception as e:
        return False, f"Backup failed: {e}", None

    new_content = content.replace(old_code, new_code, 1)

    try:
        path.write_text(new_content, encoding="utf-8")
    except Exception as e:
        path.write_text(content, encoding="utf-8")
        return False, f"Write failed: {e}", None

    return True, "Applied successfully", str(backup_path)


def revert_file(file_path: str, backup_path: str) -> Tuple[bool, str]:
    try:
        backup_content = Path(backup_path).read_text(encoding="utf-8")
        Path(file_path).write_text(backup_content, encoding="utf-8")
        return True, "Reverted successfully"
    except Exception as e:
        return False, f"Revert failed: {e}"
