import os
import fnmatch
from pathlib import Path
from typing import List, Dict, Optional

CPP_EXTENSIONS = {".cpp", ".cc", ".cxx", ".c++", ".C", ".c"}
HEADER_EXTENSIONS = {".h", ".hpp", ".hxx", ".h++", ".H"}
ALL_SOURCE_EXTS = CPP_EXTENSIONS | HEADER_EXTENSIONS


class FileInfo:
    def __init__(self, path: str, relative_path: str, size_bytes: int,
                 lines: int, extension: str):
        self.path = path
        self.relative_path = relative_path
        self.size_bytes = size_bytes
        self.lines = lines
        self.extension = extension

    @property
    def language(self) -> str:
        return "cpp"

    @property
    def is_header(self) -> bool:
        return self.extension in HEADER_EXTENSIONS

    @property
    def is_source(self) -> bool:
        return self.extension in CPP_EXTENSIONS

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "relative_path": self.relative_path,
            "size_bytes": self.size_bytes,
            "lines": self.lines,
            "extension": self.extension,
            "language": self.language,
        }

    def __repr__(self):
        return f"FileInfo({self.relative_path})"


class FileScanner:
    def __init__(self, project_root: str,
                 exclude_dirs: Optional[List[str]] = None,
                 exclude_patterns: Optional[List[str]] = None):
        self.project_root = Path(project_root).resolve()
        self.exclude_dirs = set(exclude_dirs or [])
        self.exclude_patterns = exclude_patterns or []

    def scan(self) -> List[FileInfo]:
        files: List[FileInfo] = []
        for dirpath, dirnames, filenames in os.walk(str(self.project_root)):
            rel_dir = Path(dirpath).relative_to(self.project_root)
            dirnames[:] = [
                d for d in dirnames
                if d not in self.exclude_dirs
                and not d.startswith('.')
            ]
            if self._is_excluded_dir(rel_dir):
                dirnames.clear()
                continue
            for fname in filenames:
                _, ext = os.path.splitext(fname)
                if ext not in ALL_SOURCE_EXTS:
                    continue
                full_path = str(Path(dirpath) / fname)
                rel_path = str(Path(rel_dir) / fname).replace("\\", "/")
                if self._matches_exclude_pattern(fname):
                    continue
                size = os.path.getsize(full_path)
                lines = self._count_lines(full_path)
                files.append(FileInfo(
                    path=full_path,
                    relative_path=rel_path,
                    size_bytes=size,
                    lines=lines,
                    extension=ext
                ))
        return files

    def _is_excluded_dir(self, rel_dir: Path) -> bool:
        parts = rel_dir.parts
        for part in parts:
            if part in self.exclude_dirs:
                return True
        return False

    def _matches_exclude_pattern(self, fname: str) -> bool:
        for pattern in self.exclude_patterns:
            if fnmatch.fnmatch(fname, pattern):
                return True
        return False

    @staticmethod
    def _count_lines(filepath: str) -> int:
        try:
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                return sum(1 for _ in f)
        except Exception:
            return 0
