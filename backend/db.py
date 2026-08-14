import sqlite3
import os
import json
import uuid
from pathlib import Path
from datetime import datetime
from typing import Optional, List
from contextlib import contextmanager

DB_DIR = Path(__file__).resolve().parent.parent / "data"
DB_PATH = DB_DIR / "cpp_inspector.db"


def get_db_path() -> str:
    DB_DIR.mkdir(parents=True, exist_ok=True)
    return str(DB_PATH)


@contextmanager
def get_connection():
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    with get_connection() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS scans (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL DEFAULT '',
                project_root TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                total_files INTEGER DEFAULT 0,
                total_modules INTEGER DEFAULT 0,
                modules_completed INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                completed_at TEXT
            );

            CREATE TABLE IF NOT EXISTS files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scan_id TEXT NOT NULL,
                path TEXT NOT NULL,
                relative_path TEXT NOT NULL,
                size_bytes INTEGER DEFAULT 0,
                lines INTEGER DEFAULT 0,
                extension TEXT NOT NULL,
                FOREIGN KEY (scan_id) REFERENCES scans(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS modules (
                id TEXT PRIMARY KEY,
                scan_id TEXT NOT NULL,
                name TEXT NOT NULL,
                estimated_tokens INTEGER DEFAULT 0,
                partition_count INTEGER DEFAULT 1,
                FOREIGN KEY (scan_id) REFERENCES scans(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS module_files (
                module_id TEXT NOT NULL,
                file_path TEXT NOT NULL,
                PRIMARY KEY (module_id, file_path),
                FOREIGN KEY (module_id) REFERENCES modules(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS module_dependencies (
                module_id TEXT NOT NULL,
                dependency_id TEXT NOT NULL,
                PRIMARY KEY (module_id, dependency_id),
                FOREIGN KEY (module_id) REFERENCES modules(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS issues (
                id TEXT PRIMARY KEY,
                scan_id TEXT NOT NULL,
                module_id TEXT NOT NULL,
                file_path TEXT NOT NULL,
                severity TEXT NOT NULL DEFAULT 'medium',
                category TEXT NOT NULL DEFAULT 'other',
                title TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                title_zh TEXT NOT NULL DEFAULT '',
                description_zh TEXT NOT NULL DEFAULT '',
                line_start INTEGER DEFAULT 0,
                line_end INTEGER DEFAULT 0,
                original_code TEXT NOT NULL DEFAULT '',
                suggested_code TEXT NOT NULL DEFAULT '',
                rule_reference TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL,
                FOREIGN KEY (scan_id) REFERENCES scans(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_issues_scan ON issues(scan_id);
            CREATE INDEX IF NOT EXISTS idx_issues_status ON issues(status);
            CREATE INDEX IF NOT EXISTS idx_issues_severity ON issues(severity);
        """)

        _migrate(conn)


def _migrate(conn):
    issue_cols = {row["name"] for row in conn.execute("PRAGMA table_info(issues)").fetchall()}
    if "title_zh" not in issue_cols:
        conn.execute("ALTER TABLE issues ADD COLUMN title_zh TEXT NOT NULL DEFAULT ''")
    if "description_zh" not in issue_cols:
        conn.execute("ALTER TABLE issues ADD COLUMN description_zh TEXT NOT NULL DEFAULT ''")

    scan_cols = {row["name"] for row in conn.execute("PRAGMA table_info(scans)").fetchall()}
    if "name" not in scan_cols:
        conn.execute("ALTER TABLE scans ADD COLUMN name TEXT NOT NULL DEFAULT ''")


def create_scan(project_root: str) -> str:
    scan_id = uuid.uuid4().hex[:12]
    now = datetime.now()
    now_iso = datetime.utcnow().isoformat()
    name = now.strftime("%Y-%m-%d %H:%M:%S")
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO scans (id, name, project_root, status, created_at) VALUES (?, ?, ?, ?, ?)",
            (scan_id, name, project_root, "scanning", now_iso)
        )
    return scan_id


def update_scan_status(scan_id: str, status: str, **kwargs):
    fields = ["status = ?"]
    values = [status]
    for k, v in kwargs.items():
        fields.append(f"{k} = ?")
        values.append(v)
    values.append(scan_id)
    sql = f"UPDATE scans SET {', '.join(fields)} WHERE id = ?"
    with get_connection() as conn:
        conn.execute(sql, values)


def insert_files(scan_id: str, files: List[dict]):
    with get_connection() as conn:
        conn.executemany(
            "INSERT INTO files (scan_id, path, relative_path, size_bytes, lines, extension) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            [(scan_id, f["path"], f["relative_path"], f["size_bytes"],
              f["lines"], f["extension"]) for f in files]
        )


def insert_modules(scan_id: str, modules: List[dict]):
    with get_connection() as conn:
        for m in modules:
            conn.execute(
                "INSERT OR REPLACE INTO modules (id, scan_id, name, estimated_tokens, partition_count) "
                "VALUES (?, ?, ?, ?, ?)",
                (m["id"], scan_id, m["name"], m.get("estimated_tokens", 0),
                 m.get("partition_count", 1))
            )
            for fp in m.get("files", []):
                conn.execute(
                    "INSERT OR REPLACE INTO module_files (module_id, file_path) VALUES (?, ?)",
                    (m["id"], fp)
                )
            for dep_id in m.get("dependencies", []):
                conn.execute(
                    "INSERT OR REPLACE INTO module_dependencies (module_id, dependency_id) VALUES (?, ?)",
                    (m["id"], dep_id)
                )


def insert_issues(issues: List[dict]):
    with get_connection() as conn:
        for issue in issues:
            issue_id = uuid.uuid4().hex[:12]
            now = datetime.utcnow().isoformat()
            conn.execute(
                """INSERT INTO issues (id, scan_id, module_id, file_path, severity,
                   category, title, description, title_zh, description_zh,
                   line_start, line_end,
                   original_code, suggested_code, rule_reference, status, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (issue_id, issue["scan_id"], issue["module_id"], issue["file_path"],
                 issue.get("severity", "medium"), issue.get("category", "other"),
                 issue["title"], issue.get("description", ""),
                 issue.get("title_zh", ""), issue.get("description_zh", ""),
                 issue.get("line_start", 0), issue.get("line_end", 0),
                 issue.get("original_code", ""), issue.get("suggested_code", ""),
                 issue.get("rule_reference", ""), "pending", now)
            )


def _ensure_scan_name(s: dict) -> dict:
    if not s.get("name"):
        try:
            created = datetime.fromisoformat(s.get("created_at", ""))
            s["name"] = created.astimezone().strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            s["name"] = s.get("id", "")[:12]
    return s


def get_scan(scan_id: str) -> Optional[dict]:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM scans WHERE id = ?", (scan_id,)).fetchone()
        return _ensure_scan_name(dict(row)) if row else None


def get_all_scans() -> List[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM scans ORDER BY created_at DESC LIMIT 50"
        ).fetchall()
        scans = []
        for row in rows:
            s = _ensure_scan_name(dict(row))
            issue_count = conn.execute(
                "SELECT COUNT(*) AS c FROM issues WHERE scan_id = ?", (s["id"],)
            ).fetchone()
            s["issue_count"] = issue_count["c"] if issue_count else 0
            scans.append(s)
        return scans


def delete_scan(scan_id: str) -> bool:
    with get_connection() as conn:
        cursor = conn.execute("DELETE FROM scans WHERE id = ?", (scan_id,))
        return cursor.rowcount > 0


def get_modules(scan_id: str) -> List[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM modules WHERE scan_id = ?", (scan_id,)
        ).fetchall()
        modules = []
        for row in rows:
            m = dict(row)
            files = conn.execute(
                "SELECT file_path FROM module_files WHERE module_id = ?", (m["id"],)
            ).fetchall()
            m["files"] = [f["file_path"] for f in files]
            deps = conn.execute(
                "SELECT dependency_id FROM module_dependencies WHERE module_id = ?", (m["id"],)
            ).fetchall()
            m["dependencies"] = [d["dependency_id"] for d in deps]
            modules.append(m)
        return modules


def get_issues(scan_id: str, module_id: Optional[str] = None,
               severity: Optional[str] = None,
               status: Optional[str] = None) -> List[dict]:
    with get_connection() as conn:
        sql = "SELECT * FROM issues WHERE scan_id = ?"
        params = [scan_id]
        if module_id:
            sql += " AND module_id = ?"
            params.append(module_id)
        if severity:
            sql += " AND severity = ?"
            params.append(severity)
        if status:
            sql += " AND status = ?"
            params.append(status)
        sql += " ORDER BY CASE severity WHEN 'critical' THEN 0 WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END"
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]


def update_issue_status(issue_id: str, status: str) -> bool:
    with get_connection() as conn:
        cursor = conn.execute(
            "UPDATE issues SET status = ? WHERE id = ?", (status, issue_id)
        )
        return cursor.rowcount > 0


def get_issue(issue_id: str) -> Optional[dict]:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM issues WHERE id = ?", (issue_id,)).fetchone()
        return dict(row) if row else None


def get_scan_files(scan_id: str) -> List[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM files WHERE scan_id = ?", (scan_id,)
        ).fetchall()
        return [dict(r) for r in rows]


def get_issues_by_ids(issue_ids: List[str]) -> List[dict]:
    with get_connection() as conn:
        placeholders = ",".join("?" * len(issue_ids))
        rows = conn.execute(
            f"SELECT * FROM issues WHERE id IN ({placeholders})", issue_ids
        ).fetchall()
        return [dict(r) for r in rows]


def save_backup_path(issue_id: str, backup_path: str) -> None:
    with get_connection() as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS backups (issue_id TEXT PRIMARY KEY, backup_path TEXT)",
        )
        conn.execute(
            "INSERT OR REPLACE INTO backups (issue_id, backup_path) VALUES (?, ?)",
            (issue_id, backup_path),
        )


def get_backup_path(issue_id: str) -> Optional[str]:
    with get_connection() as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS backups (issue_id TEXT PRIMARY KEY, backup_path TEXT)",
        )
        row = conn.execute(
            "SELECT backup_path FROM backups WHERE issue_id = ?", (issue_id,)
        ).fetchone()
        return row["backup_path"] if row else None
