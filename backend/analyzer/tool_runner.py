import subprocess
import json
from pathlib import Path
from typing import Optional, List, Dict, Any


def run_clang_tidy(file_path: str,
                   compile_commands_dir: Optional[str] = None,
                   checks: Optional[str] = None) -> List[Dict[str, Any]]:
    if checks is None:
        checks = ("-*,bugprone-*,cppcoreguidelines-*,modernize-*,"
                  "performance-*,readability-*")

    cmd = ["clang-tidy", file_path, f"--checks={checks}",
           "--export-fixes=-", "--quiet"]

    if compile_commands_dir:
        cmd.extend(["-p", compile_commands_dir])

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=60,
        )
        output = result.stdout.strip()
        if not output:
            return []
        fixes = json.loads(output)
        return _parse_clang_tidy_output(fixes.get("Diagnostics", []))
    except FileNotFoundError:
        return []
    except (json.JSONDecodeError, subprocess.TimeoutExpired) as e:
        return [{"tool": "clang-tidy", "error": str(e)}]


def run_cppcheck(file_path: str,
                 project_root: Optional[str] = None,
                 enable: str = "warning,performance,portability,style") -> List[Dict[str, Any]]:
    cmd = ["cppcheck", f"--enable={enable}", "--template=json", "--quiet",
           file_path]

    if project_root:
        cmd.extend(["-I", project_root])

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=60,
        )
        output = result.stdout.strip()
        if not output:
            return []
        fixes = json.loads(output)
        results = fixes if isinstance(fixes, list) else fixes.get("errors", [])
        return _parse_cppcheck_output(results)
    except FileNotFoundError:
        return []
    except (json.JSONDecodeError, subprocess.TimeoutExpired) as e:
        return [{"tool": "cppcheck", "error": str(e)}]


def _parse_clang_tidy_output(diagnostics: List[Dict]) -> List[Dict[str, Any]]:
    parsed = []
    for d in diagnostics:
        diag_name = d.get("DiagnosticName", "")
        message = d.get("Message", "")
        loc = (d.get("DiagnosticMessage", {}).get("FilePath", ""))
        replacements = d.get("Replacements", [])

        for r in replacements:
            parsed.append({
                "tool": "clang-tidy",
                "check": diag_name,
                "message": message,
                "file": r.get("FilePath", ""),
                "line": r.get("Offset", 0),
                "length": r.get("Length", 0),
                "replacement": r.get("ReplacementText", ""),
            })

        if not replacements:
            parsed.append({
                "tool": "clang-tidy",
                "check": diag_name,
                "message": message,
                "file": loc,
                "line": 0,
                "length": 0,
                "replacement": "",
            })

    return parsed


def _parse_cppcheck_output(errors: List[Dict]) -> List[Dict[str, Any]]:
    parsed = []
    for e in errors:
        parsed.append({
            "tool": "cppcheck",
            "severity": e.get("severity", "warning"),
            "message": e.get("message", ""),
            "file": e.get("file", ""),
            "line": int(e.get("line", "0") or "0"),
            "id": e.get("id", ""),
        })
    return parsed


def run_tools(file_path: str,
              compile_commands_dir: Optional[str] = None,
              project_root: Optional[str] = None,
              enable_clang_tidy: bool = True,
              enable_cppcheck: bool = True) -> List[Dict[str, Any]]:
    results = []
    if enable_clang_tidy:
        results.extend(run_clang_tidy(file_path, compile_commands_dir))
    if enable_cppcheck:
        results.extend(run_cppcheck(file_path, project_root))
    return results
