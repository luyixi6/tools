import asyncio
import json
import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional, List

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Query, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import uvicorn

from .config import get_config, reload_config, AppConfig
from .models import (
    ScanRequest, ModuleSelection, AnalysisRequest, BatchAction,
    ScanInfo, ModuleInfo, ScanProgress, CodeIssue, FixResult,
    ScanStatus, IssueStatus, Severity, IssueCategory, FileInfo,
    ModuleProgress,
)
from .db import (
    init_db, create_scan, update_scan_status, insert_files,
    insert_modules, insert_issues, get_scan, get_modules, get_issues,
    update_issue_status, get_issue, get_scan_files, get_issues_by_ids,
    save_backup_path, get_backup_path, get_all_scans, delete_scan,
)
from .scanner.file_scanner import FileScanner
from .scanner.include_graph import build_module_partitions
from .analyzer.static_analyzer import ModuleAnalyzer
from .aggregator import deduplicate_issues
from .llm.client_factory import create_client, get_provider_list as _get_providers


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    cfg = get_config()
    print(f"Server starting on {cfg.server.host}:{cfg.server.port}")
    yield


app = FastAPI(title="CPP Inspector", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

active_connections: dict[str, List[WebSocket]] = {}


def _msg(cfg: AppConfig, en: str, zh: str) -> str:
    return zh if (cfg.language and cfg.language.lower().startswith("zh")) else en


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
        "memory": "memory_safety", "mem": "memory_safety", "leak": "memory_safety",
        "concurrency": "concurrency", "thread": "concurrency", "race": "concurrency",
        "exception": "exception_safety", "except": "exception_safety",
        "modern": "modern_cpp", "cpp": "modern_cpp",
        "style": "code_style", "format": "code_style",
        "type": "type_safety", "cast": "type_safety",
        "ub": "undefined_behavior", "undefined": "undefined_behavior",
        "perform": "performance", "perf": "performance",
    }
    for key, mapped in mapping.items():
        if key in value:
            return mapped
    return "other"


@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "0.1.0"}


@app.get("/api/providers")
async def get_providers():
    return {"providers": _get_providers()}


@app.get("/api/scans")
async def list_scans():
    return {"scans": get_all_scans()}


@app.get("/api/report/schema")
async def get_report_schema():
    return {
        "schema_version": "1.0",
        "description": "分析报告 JSON 格式，由 Claude Code 等工具生成后导入",
        "example": {
            "project_root": "D:/path/to/your/project",
            "report_name": "可选：报告名称（默认使用导入时间）",
            "issues": [
                {
                    "file_path": "src/foo.cpp",
                    "severity": "critical|high|medium|low",
                    "category": "memory_safety|concurrency|exception_safety|modern_cpp|code_style|type_safety|undefined_behavior|performance|other",
                    "title": "问题标题",
                    "description": "详细描述",
                    "title_zh": "可选：中文标题",
                    "description_zh": "可选：中文描述",
                    "line_start": 42,
                    "line_end": 45,
                    "original_code": "文件中存在的原始代码片段（用于精确替换）",
                    "suggested_code": "修改后的代码片段",
                    "rule_reference": "规则引用，如 C++ Core Guidelines R.3"
                }
            ]
        }
    }


@app.post("/api/report/import")
async def import_report(data: dict):
    # 支持两种格式：完整对象 或 纯 issues 数组
    if isinstance(data, list):
        issues_data = data
        project_root = ""
        report_name = ""
    else:
        issues_data = data.get("issues", [])
        project_root = data.get("project_root", "")
        report_name = data.get("report_name", "")

    if not issues_data:
        raise HTTPException(status_code=400, detail="报告中没有 issues 数据")

    valid_issues = []
    skipped = 0
    already_fixed = 0
    for item in issues_data:
        if not isinstance(item, dict):
            skipped += 1
            continue
        file_path = item.get("file_path", "")
        title = item.get("title", "")
        if not file_path or not title:
            skipped += 1
            continue

        if project_root and not os.path.isabs(file_path):
            file_path = os.path.join(project_root, file_path.replace("/", os.sep))

        # 跳过已修复的问题：如果 original_code 已不在文件中，说明该问题已被修复
        original_code = item.get("original_code", "")
        if original_code:
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                if original_code not in content:
                    already_fixed += 1
                    continue
            except (OSError, IOError):
                skipped += 1
                continue

        valid_issues.append({
            "scan_id": "",
            "module_id": "imported",
            "file_path": file_path,
            "severity": _normalize_severity(item.get("severity", "medium")),
            "category": _normalize_category(item.get("category", "other")),
            "title": title,
            "description": item.get("description", ""),
            "title_zh": item.get("title_zh", ""),
            "description_zh": item.get("description_zh", ""),
            "line_start": int(item.get("line_start", 0) or 0),
            "line_end": int(item.get("line_end", 0) or 0),
            "original_code": original_code,
            "suggested_code": item.get("suggested_code", ""),
            "rule_reference": item.get("rule_reference", ""),
        })

    if not valid_issues:
        return {
            "scan_id": "",
            "name": "",
            "issues_imported": 0,
            "skipped": skipped,
            "already_fixed": already_fixed,
            "message": "报告中的问题均已修复，无需导入",
        }

    cfg = get_config()
    root = project_root or cfg.project.root or "imported"
    scan_id = create_scan(root)

    for issue in valid_issues:
        issue["scan_id"] = scan_id
    insert_issues(valid_issues)

    name = report_name or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    update_scan_status(
        scan_id, "completed",
        name=name,
        total_files=len({i["file_path"] for i in valid_issues}),
        total_modules=1,
        modules_completed=1,
        completed_at=datetime.utcnow().isoformat(),
    )

    return {
        "scan_id": scan_id,
        "name": name,
        "issues_imported": len(valid_issues),
        "skipped": skipped,
        "already_fixed": already_fixed,
    }


@app.get("/api/report/export/{scan_id}")
async def export_report(scan_id: str):
    scan = get_scan(scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")

    issues = get_issues(scan_id)

    report_issues = []
    for issue in issues:
        file_path = issue.get("file_path", "")
        project_root = scan.get("project_root", "")
        if project_root and os.path.isabs(file_path):
            try:
                file_path = os.path.relpath(file_path, project_root).replace(os.sep, "/")
            except ValueError:
                pass

        report_issues.append({
            "file_path": file_path,
            "severity": issue.get("severity", "medium"),
            "category": issue.get("category", "other"),
            "title": issue.get("title", ""),
            "description": issue.get("description", ""),
            "title_zh": issue.get("title_zh", ""),
            "description_zh": issue.get("description_zh", ""),
            "line_start": issue.get("line_start", 0),
            "line_end": issue.get("line_end", 0),
            "original_code": issue.get("original_code", ""),
            "suggested_code": issue.get("suggested_code", ""),
            "rule_reference": issue.get("rule_reference", ""),
        })

    report = {
        "project_root": scan.get("project_root", ""),
        "report_name": scan.get("name", ""),
        "issues": report_issues,
        "summary": {
            "total": len(report_issues),
            "by_severity": _count_by(report_issues, "severity"),
            "by_category": _count_by(report_issues, "category"),
        },
    }

    # 同时把报告文件保存到工具的 reports/ 目录，按时间命名，方便查找与管理
    reports_dir = Path(__file__).resolve().parent.parent / "reports"
    reports_dir.mkdir(exist_ok=True)
    report_file = reports_dir / f"cpp-report-{_scan_filename(scan)}.json"
    try:
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        report["saved_path"] = str(report_file)
        report["filename"] = report_file.name
    except Exception as e:
        report["saved_path"] = ""
        report["save_error"] = str(e)

    return report


def _count_by(items: List[dict], key: str) -> dict:
    counts: dict = {}
    for item in items:
        v = item.get(key, "unknown")
        counts[v] = counts.get(v, 0) + 1
    return counts


def _scan_filename(scan: dict) -> str:
    name = scan.get("name", "") or scan.get("id", "")
    safe = name.replace(" ", "_").replace(":", "-")
    for ch in ['/', '\\', '*', '?', '"', '<', '>', '|']:
        safe = safe.replace(ch, "-")
    return safe or scan.get("id", "unknown")


@app.delete("/api/scans/{scan_id}")
async def remove_scan(scan_id: str):
    ok = delete_scan(scan_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Scan not found")
    return {"scan_id": scan_id, "deleted": True}


@app.get("/api/config")
async def get_current_config():
    cfg = get_config()
    data = cfg.model_dump()
    key = data.get("api", {}).get("api_key", "")
    data["api"]["api_key_set"] = bool(key)
    data["api"]["api_key"] = ""
    return data


@app.put("/api/config")
async def update_config(data: dict):
    cfg = get_config()

    if "language" in data:
        cfg.language = data["language"]

    if "api" in data:
        api_data = data["api"]
        for k, v in api_data.items():
            if k == "api_key":
                if not v or (isinstance(v, str) and "***" in v):
                    continue
            if hasattr(cfg.api, k):
                setattr(cfg.api, k, v)

    if "project" in data:
        proj_data = data["project"]
        for k, v in proj_data.items():
            if hasattr(cfg.project, k):
                setattr(cfg.project, k, v)

    if "analysis" in data:
        anal_data = data["analysis"]
        for k, v in anal_data.items():
            if hasattr(cfg.analysis, k):
                setattr(cfg.analysis, k, v)

    if "chunking" in data:
        chunk_data = data["chunking"]
        for k, v in chunk_data.items():
            if hasattr(cfg.chunking, k):
                setattr(cfg.chunking, k, v)

    if "batch" in data:
        batch_data = data["batch"]
        for k, v in batch_data.items():
            if hasattr(cfg.batch, k):
                setattr(cfg.batch, k, v)

    from .config import save_config
    save_config(cfg)
    reload_config()
    return {"status": "config_updated"}


@app.post("/api/project/scan")
async def scan_project(req: ScanRequest):
    cfg = get_config()
    project_root = req.project_root or cfg.project.root
    if not project_root:
        raise HTTPException(status_code=400, detail="project_root is required")

    project_path = Path(project_root).resolve()
    if not project_path.exists():
        raise HTTPException(status_code=400, detail=f"Path not found: {project_root}")

    scan_id = create_scan(str(project_path))

    asyncio.create_task(_run_scan(scan_id, str(project_path), cfg))

    return {"scan_id": scan_id, "status": "scanning"}


async def _run_scan(scan_id: str, project_root: str, cfg: AppConfig):
    try:
        await _broadcast(scan_id, {"type": "scan_start", "scan_id": scan_id,
                                    "message": _msg(cfg, "Scanning files...", "正在扫描文件...")})

        scanner = FileScanner(
            project_root=project_root,
            exclude_dirs=cfg.project.exclude_dirs,
            exclude_patterns=cfg.project.exclude_patterns,
        )
        files = scanner.scan()
        file_dicts = [f.to_dict() for f in files]
        insert_files(scan_id, file_dicts)

        if not files:
            update_scan_status(
                scan_id, "failed",
                completed_at=datetime.utcnow().isoformat(),
            )
            await _broadcast(scan_id, {
                "type": "scan_error",
                "scan_id": scan_id,
                "message": _msg(cfg,
                    f"No C++ source files found in {project_root}",
                    f"在 {project_root} 中未找到 C++ 源文件，请检查路径"),
            })
            return

        await _broadcast(scan_id, {"type": "scan_progress", "scan_id": scan_id,
                                    "message": _msg(cfg, f"Found {len(files)} files", f"发现 {len(files)} 个文件")})

        update_scan_status(scan_id, "scanning", total_files=len(files))

        file_paths = [f.path for f in files]

        modules_raw = build_module_partitions(
            file_paths=file_paths,
            project_root=project_root,
            strategy=cfg.chunking.strategy,
        )
        insert_modules(scan_id, modules_raw)

        update_scan_status(
            scan_id, "completed",
            total_modules=len(modules_raw),
            completed_at=datetime.utcnow().isoformat(),
        )

        await _broadcast(scan_id, {
            "type": "scan_complete",
            "scan_id": scan_id,
            "status": "completed",
            "total_files": len(files),
            "total_modules": len(modules_raw),
            "message": _msg(cfg,
                f"Scan complete: {len(files)} files, {len(modules_raw)} modules",
                f"扫描完成：{len(files)} 个文件，{len(modules_raw)} 个模块"),
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        update_scan_status(scan_id, "failed")
        await _broadcast(scan_id, {"type": "scan_error", "scan_id": scan_id,
                                    "message": str(e)})


@app.get("/api/project/modules/{scan_id}")
async def get_scan_modules(scan_id: str):
    scan = get_scan(scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")
    modules = get_modules(scan_id)
    files = get_scan_files(scan_id)
    return {
        "scan": scan,
        "modules": modules,
        "files": files,
    }


@app.get("/api/project/status/{scan_id}")
async def get_scan_status(scan_id: str):
    scan = get_scan(scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")
    return scan


@app.post("/api/analyze/start")
async def start_analysis(req: AnalysisRequest):
    scan = get_scan(req.scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")

    update_scan_status(req.scan_id, "analyzing")
    asyncio.create_task(_run_analysis(req.scan_id, req.module_ids))

    return {"scan_id": req.scan_id, "status": "analyzing",
            "selected_modules": len(req.module_ids)}


async def _run_analysis(scan_id: str, module_ids: List[str]):
    try:
        all_modules = get_modules(scan_id)
        modules_map = {m["id"]: m for m in all_modules}
        selected = [modules_map[mid] for mid in module_ids if mid in modules_map]
        total = len(selected)

        cfg = get_config()
        api = cfg.api
        use_demo = not api.api_key or "your-key" in api.api_key

        if use_demo:
            analyzer = None
        else:
            client = create_client(
                provider=api.provider,
                api_key=api.api_key,
                model=api.effective_model(),
                max_tokens=api.max_tokens,
                base_url=api.base_url or None,
                rate_limit_rpm=cfg.batch.rate_limit_rpm,
                extra_headers=api.extra_headers or None,
            )
            analyzer = ModuleAnalyzer(client=client)

        semaphore = asyncio.Semaphore(max(1, cfg.batch.concurrent_modules))
        completed_count = 0
        completed_lock = asyncio.Lock()

        async def analyze_one(idx: int, module: dict):
            nonlocal completed_count
            async with semaphore:
                progress = ModuleProgress(
                    module_id=module["id"],
                    module_name=module["name"],
                    status="analyzing",
                    total_files=len(module.get("files", [])),
                    files_completed=0,
                    issues_found=0,
                )

                await _broadcast(scan_id, {
                    "type": "analysis_progress",
                    "scan_id": scan_id,
                    "total_modules": total,
                    "modules_completed": completed_count,
                    "current_module": progress.model_dump(),
                    "message": _msg(cfg,
                        f"Analyzing module {idx + 1}/{total}: {module['name']}",
                        f"正在分析模块 {idx + 1}/{total}：{module['name']}"),
                })

                try:
                    if use_demo:
                        issues = _generate_demo_issues(scan_id, module)
                    else:
                        issues = await analyzer.analyze_module(module)
                        for issue in issues:
                            issue["scan_id"] = scan_id
                            issue["module_id"] = module["id"]
                except Exception as e:
                    issues = [{
                        "scan_id": scan_id,
                        "module_id": module["id"],
                        "file_path": "",
                        "severity": "medium",
                        "category": "other",
                        "title": f"Analysis failed: {str(e)}",
                        "description": str(e),
                        "title_zh": f"分析失败：{str(e)}",
                        "description_zh": str(e),
                        "line_start": 0,
                        "line_end": 0,
                        "original_code": "",
                        "suggested_code": "",
                        "rule_reference": "",
                    }]

                if issues:
                    insert_issues(issues)

                async with completed_lock:
                    completed_count += 1
                    update_scan_status(scan_id, "analyzing", modules_completed=completed_count)

                if issues:
                    await _broadcast(scan_id, {
                        "type": "module_complete",
                        "scan_id": scan_id,
                        "module_name": module["name"],
                        "issues_found": len(issues),
                    })

        tasks = [asyncio.create_task(analyze_one(i, m)) for i, m in enumerate(selected)]
        await asyncio.gather(*tasks)

        update_scan_status(
            scan_id, "completed",
            modules_completed=total,
            completed_at=datetime.utcnow().isoformat(),
        )

        issues = get_issues(scan_id)
        await _broadcast(scan_id, {
            "type": "analysis_complete",
            "scan_id": scan_id,
            "status": "completed",
            "total_issues": len(issues),
            "message": _msg(cfg,
                f"Analysis complete: {len(issues)} issues found",
                f"分析完成：发现 {len(issues)} 个问题"),
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        update_scan_status(scan_id, "failed")
        await _broadcast(scan_id, {"type": "analysis_error", "scan_id": scan_id,
                                    "message": str(e)})


def _generate_demo_issues(scan_id: str, module: dict) -> List[dict]:
    issues = []
    files = sorted(module.get("files", []),
                   key=lambda f: Path(f).name if f else "")
    for file_path in files[:2]:
        abs_path = _resolve_file_path(file_path, scan_id)
        try:
            content = abs_path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            content = ""

        patterns = [
            ("high", "memory_safety",
             "Potential memory leak: raw 'new' without matching 'delete'",
             "Look for matching delete/free in all code paths.",
             "可能存在内存泄漏：使用了裸 'new' 而没有匹配的 'delete'",
             "请在所有代码路径中检查是否有匹配的 delete/free。",
             r"\bnew\b[^;]+;"),
            ("medium", "modern_cpp",
             "Consider using 'nullptr' instead of NULL",
             "Modern C++ uses nullptr for type safety.",
             "建议使用 'nullptr' 代替 NULL",
             "现代 C++ 使用 nullptr 以保证类型安全。",
             r"\bNULL\b"),
            ("critical", "undefined_behavior",
             "Potential out-of-bounds access",
             "Loop bound may cause buffer overflow.",
             "可能存在越界访问",
             "循环边界可能导致缓冲区溢出。",
             r"for\s*\([^)]*<=\s*size[^)]*\)"),
            ("medium", "code_style",
             "C-style cast detected",
             "Use static_cast or reinterpret_cast for clarity.",
             "检测到 C 风格强制类型转换",
             "建议使用 static_cast 或 reinterpret_cast 以提高清晰度。",
             r"\(\s*(int|char|double|long|void)\s*\*?\s*\)"),
            ("low", "modern_cpp",
             "Consider using const for immutable variables",
             "Mark variables as const when they should not change.",
             "建议对不可变变量使用 const",
             "对于不应改变的变量，请标记为 const。",
             r"\bint\s+\w+\s*=\s*"),
        ]

        for severity, category, title, desc, title_zh, desc_zh, pattern in patterns:
            found = _find_at_line(content, pattern)
            if found is not None:
                line_num, matched_line = found
                lines = content.split("\n")
                end_num = min(line_num + 2, len(lines))
                original = lines[line_num - 1].strip() if line_num <= len(lines) else matched_line
                issues.append({
                    "scan_id": scan_id,
                    "module_id": module["id"],
                    "file_path": str(abs_path),
                    "severity": severity,
                    "category": category,
                    "title": title,
                    "description": desc,
                    "title_zh": title_zh,
                    "description_zh": desc_zh,
                    "line_start": line_num,
                    "line_end": end_num,
                    "original_code": original[:200],
                    "suggested_code": "// TODO: Fix this issue per the description above",
                    "rule_reference": "C++ Core Guidelines",
                })

    return issues


def _find_at_line(content: str, pattern: str) -> tuple | None:
    import re
    lines = content.split("\n")
    for i, line in enumerate(lines, 1):
        if re.search(pattern, line):
            return (i, line)
    return None


@app.get("/api/issues/{scan_id}")
async def get_scan_issues(
    scan_id: str,
    module_id: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
):
    scan = get_scan(scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")
    issues = get_issues(scan_id, module_id=module_id,
                        severity=severity, status=status)

    severity_counts = {}
    for s in Severity:
        sev_issues = get_issues(scan_id, severity=s.value)
        severity_counts[s.value] = len(sev_issues)

    return {
        "scan_id": scan_id,
        "issues": issues,
        "summary": {
            "total": len(issues),
            "by_severity": severity_counts,
            "pending": len([i for i in issues if i["status"] == "pending"]),
            "applied": len([i for i in issues if i["status"] == "applied"]),
            "rejected": len([i for i in issues if i["status"] == "rejected"]),
        },
    }


@app.post("/api/issues/{issue_id}/accept")
async def accept_issue(issue_id: str):
    issue = get_issue(issue_id)
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")
    result = _apply_single_fix(issue)
    if result.get("success"):
        update_issue_status(issue_id, "applied")
    else:
        update_issue_status(issue_id, "failed")
    return {"issue_id": issue_id, **result}


@app.post("/api/issues/{issue_id}/reject")
async def reject_issue(issue_id: str):
    issue = get_issue(issue_id)
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")
    update_issue_status(issue_id, "rejected")
    return {"issue_id": issue_id, "status": "rejected"}


@app.post("/api/issues/{issue_id}/revert")
async def revert_issue(issue_id: str):
    issue = get_issue(issue_id)
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")
    backup_path = get_backup_path(issue_id)
    if not backup_path:
        return {"issue_id": issue_id, "success": False, "error": "No backup found"}

    file_path = issue.get("file_path", "")
    resolved = _resolve_file_path(file_path, issue.get("scan_id", ""))

    try:
        backup_content = Path(backup_path).read_text(encoding="utf-8")
        resolved.write_text(backup_content, encoding="utf-8")
        try:
            Path(backup_path).unlink(missing_ok=True)
        except Exception:
            pass
        update_issue_status(issue_id, "pending")
        return {"issue_id": issue_id, "success": True}
    except Exception as e:
        return {"issue_id": issue_id, "success": False, "error": str(e)}


def _resolve_file_path(file_path: str, scan_id: str) -> Path:
    resolved = Path(file_path)
    if not resolved.is_absolute():
        scan = get_scan(scan_id)
        if scan:
            resolved = Path(scan["project_root"]) / file_path
    return resolved.resolve()


@app.post("/api/issues/batch")
async def batch_update_issues(action: BatchAction):
    results = []
    issues = get_issues_by_ids(action.issue_ids)
    issues_map = {i["id"]: i for i in issues}

    for issue_id in action.issue_ids:
        issue = issues_map.get(issue_id)
        if not issue:
            results.append({"issue_id": issue_id, "success": False, "error": "Not found"})
            continue
        if action.action == "accept":
            result = _apply_single_fix(issue)
            new_status = "applied" if result.get("success") else "failed"
        else:
            result = {"success": True, "file_path": issue.get("file_path", "")}
            new_status = "rejected"
        update_issue_status(issue_id, new_status)
        results.append({"issue_id": issue_id, "status": new_status, **result})
    return {"results": results}


def _apply_single_fix(issue: dict) -> dict:
    file_path = issue.get("file_path", "")
    original = issue.get("original_code", "")
    suggested = issue.get("suggested_code", "")
    scan_id = issue.get("scan_id", "")

    resolved_path = _resolve_file_path(file_path, scan_id)

    if not file_path or not resolved_path.exists():
        return {"success": False, "error": f"File not found: {resolved_path}", "file_path": file_path}

    try:
        content = resolved_path.read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        return {"success": False, "error": str(e), "file_path": file_path}

    if not original:
        return {"success": False, "error": "No original_code to replace", "file_path": file_path}

    if original not in content:
        return {"success": False, "error": f"original_code not found in file ({len(original)} chars)", "file_path": file_path}

    scan = get_scan(issue.get("scan_id", ""))
    project_root = "."
    if scan:
        project_root = scan.get("project_root", ".")

    backup_dir = Path(project_root) / ".cpp-inspector-backups"
    backup_dir.mkdir(exist_ok=True)
    backup_path = backup_dir / f"{resolved_path.name}.{issue['id']}.bak"

    try:
        backup_path.write_text(content, encoding="utf-8")
        save_backup_path(issue["id"], str(backup_path))
    except Exception as e:
        return {"success": False, "error": f"Backup failed: {e}", "file_path": file_path}

    new_content = content.replace(original, suggested, 1)
    if new_content == content:
        return {"success": False, "error": "Replacement produced no change", "file_path": file_path}

    try:
        resolved_path.write_text(new_content, encoding="utf-8")
    except Exception as e:
        backup_path.write_text(content, encoding="utf-8")
        return {"success": False, "error": f"Write failed: {e}", "file_path": file_path}

    return {"success": True, "file_path": str(resolved_path), "backup_path": str(backup_path)}


@app.websocket("/ws/scan/{scan_id}")
async def websocket_scan(websocket: WebSocket, scan_id: str):
    await websocket.accept()
    if scan_id not in active_connections:
        active_connections[scan_id] = []
    active_connections[scan_id].append(websocket)
    try:
        while True:
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        active_connections[scan_id].remove(websocket)
        if not active_connections[scan_id]:
            del active_connections[scan_id]


async def _broadcast(scan_id: str, message: dict):
    if scan_id in active_connections:
        dead = []
        for ws in active_connections[scan_id]:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            active_connections[scan_id].remove(ws)


FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if FRONTEND_DIR.exists():
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIR / "assets")), name="assets")

    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        if full_path.startswith("api/") or full_path.startswith("ws/"):
            raise HTTPException(status_code=404)
        file_path = FRONTEND_DIR / full_path
        if file_path.exists() and file_path.is_file():
            return FileResponse(str(file_path))
        return FileResponse(str(FRONTEND_DIR / "index.html"))


def main():
    cfg = get_config()
    uvicorn.run(
        "backend.main:app",
        host=cfg.server.host,
        port=cfg.server.port,
        reload=True,
    )


if __name__ == "__main__":
    main()
