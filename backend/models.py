from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from enum import Enum
from datetime import datetime


class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class IssueCategory(str, Enum):
    MEMORY_SAFETY = "memory_safety"
    CONCURRENCY = "concurrency"
    EXCEPTION_SAFETY = "exception_safety"
    MODERN_CPP = "modern_cpp"
    CODE_STYLE = "code_style"
    TYPE_SAFETY = "type_safety"
    UNDEFINED_BEHAVIOR = "undefined_behavior"
    PERFORMANCE = "performance"
    OTHER = "other"


class IssueStatus(str, Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    APPLIED = "applied"
    FAILED = "failed"


class FileInfo(BaseModel):
    path: str
    relative_path: str
    size_bytes: int
    lines: int
    extension: str
    language: str = "cpp"


class ModuleInfo(BaseModel):
    id: str
    name: str
    files: List[str] = Field(default_factory=list)
    dependencies: List[str] = Field(default_factory=list)
    estimated_tokens: int = 0
    partition_count: int = 1


class ScanStatus(str, Enum):
    PENDING = "pending"
    SCANNING = "scanning"
    ANALYZING = "analyzing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ScanInfo(BaseModel):
    id: str = ""
    project_root: str = ""
    status: ScanStatus = ScanStatus.PENDING
    total_files: int = 0
    total_modules: int = 0
    modules_completed: int = 0
    created_at: str = ""
    completed_at: Optional[str] = None


class CodeIssue(BaseModel):
    id: Optional[str] = None
    scan_id: str = ""
    module_id: str = ""
    file_path: str = ""
    severity: Severity = Severity.MEDIUM
    category: IssueCategory = IssueCategory.OTHER
    title: str = ""
    description: str = ""
    title_zh: str = ""
    description_zh: str = ""
    line_start: int = 0
    line_end: int = 0
    original_code: str = ""
    suggested_code: str = ""
    rule_reference: str = ""
    status: IssueStatus = IssueStatus.PENDING
    created_at: str = ""


class ModuleProgress(BaseModel):
    module_id: str = ""
    module_name: str = ""
    status: str = "pending"
    total_files: int = 0
    files_completed: int = 0
    issues_found: int = 0


class ScanProgress(BaseModel):
    scan_id: str = ""
    status: str = ""
    total_modules: int = 0
    modules_completed: int = 0
    total_issues: int = 0
    current_module: Optional[ModuleProgress] = None
    message: str = ""


class BatchAction(BaseModel):
    issue_ids: List[str]
    action: str


class FixResult(BaseModel):
    issue_id: str = ""
    file_path: str = ""
    success: bool = False
    error: Optional[str] = None
    backup_path: Optional[str] = None


class ScanRequest(BaseModel):
    project_root: Optional[str] = None


class ModuleSelection(BaseModel):
    module_ids: List[str]


class AnalysisRequest(BaseModel):
    scan_id: str
    module_ids: List[str]
