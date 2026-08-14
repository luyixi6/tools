import re
import os
import uuid
from pathlib import Path
from typing import List, Dict, Set, Tuple
from collections import defaultdict, Counter

INCLUDE_RE = re.compile(r'^\s*#\s*include\s*[<"]([^>"]+)[>"]')


class IncludeGraph:
    def __init__(self):
        self.nodes: Dict[str, List[str]] = defaultdict(list)
        self.rev_graph: Dict[str, List[str]] = defaultdict(list)
        self.all_files: Set[str] = set()

    def parse_file(self, filepath: str) -> List[str]:
        includes = []
        try:
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    m = INCLUDE_RE.match(line)
                    if m:
                        includes.append(m.group(1))
        except Exception:
            pass
        return includes

    def build(self, files: List[str], project_root: str,
              include_paths: List[str] = None) -> None:
        self.all_files = set(files)
        resolver = IncludeResolver(project_root, include_paths or [])

        for filepath in files:
            related = filepath
            includes = self.parse_file(filepath)
            for inc in includes:
                resolved = resolver.resolve(inc, filepath)
                if resolved and resolved in self.all_files:
                    self.nodes[related].append(resolved)
                    self.rev_graph[resolved].append(related)

        for f in files:
            if f not in self.nodes:
                self.nodes[f] = []

    def get_dependencies(self, filepath: str) -> List[str]:
        return list(self.nodes.get(filepath, []))

    def get_dependents(self, filepath: str) -> List[str]:
        return list(self.rev_graph.get(filepath, []))

    def find_sccs(self) -> List[List[str]]:
        index_counter = [0]
        stack = []
        on_stack: Set[str] = set()
        indices: Dict[str, int] = {}
        lowlink: Dict[str, int] = {}
        sccs: List[List[str]] = []

        def strongconnect(v: str):
            indices[v] = index_counter[0]
            lowlink[v] = index_counter[0]
            index_counter[0] += 1
            stack.append(v)
            on_stack.add(v)

            for w in self.nodes.get(v, []):
                if w not in indices:
                    strongconnect(w)
                    lowlink[v] = min(lowlink[v], lowlink[w])
                elif w in on_stack:
                    lowlink[v] = min(lowlink[v], indices[w])

            if lowlink[v] == indices[v]:
                scc: List[str] = []
                while True:
                    w = stack.pop()
                    on_stack.remove(w)
                    scc.append(w)
                    if w == v:
                        break
                sccs.append(scc)

        for node in list(self.all_files):
            if node not in indices:
                strongconnect(node)

        for node in list(self.all_files):
            if node not in indices:
                sccs.append([node])

        return sccs

    def group_sccs_into_modules(self, sccs: List[List[str]],
                                 file_paths: List[str],
                                 max_module_size: int = 30) -> List[Dict]:
        file_index = {f: i for i, f in enumerate(file_paths)}
        scc_file_to_idx: Dict[str, int] = {}
        for i, scc in enumerate(sccs):
            for f in scc:
                scc_file_to_idx[f] = i

        visited: Set[int] = set()
        modules: List[Dict] = []
        scc_id: Dict[int, str] = {i: uuid.uuid4().hex[:12] for i in range(len(sccs))}
        scc_to_module: Dict[int, str] = {}

        for i, scc_files in enumerate(sccs):
            if i in visited:
                continue
            current_module: List[str] = list(scc_files)
            visited.add(i)
            queue = [i]
            module_id = scc_id[i]
            scc_to_module[i] = module_id

            while queue:
                ci = queue.pop(0)
                for f in sccs[ci]:
                    for dep in self.get_dependents(f):
                        if dep in scc_file_to_idx:
                            dep_idx = scc_file_to_idx[dep]
                            if dep_idx not in visited:
                                new_files = sccs[dep_idx]
                                if len(current_module) + len(new_files) <= max_module_size:
                                    current_module.extend(new_files)
                                    visited.add(dep_idx)
                                    scc_to_module[dep_idx] = module_id
                                    queue.append(dep_idx)

            dep_module_ids: Set[str] = set()
            for f in current_module:
                for dep in self.get_dependencies(f):
                    if dep in scc_file_to_idx:
                        dep_scc_idx = scc_file_to_idx[dep]
                        if dep_scc_idx not in scc_to_module:
                            dep_module_ids.add(scc_id[dep_scc_idx])

            module_name = self._derive_module_name(current_module)
            modules.append({
                "id": module_id,
                "name": module_name,
                "files": sorted(current_module),
                "dependencies": list(dep_module_ids),
                "estimated_tokens": len(current_module) * 3000,
                "partition_count": max(1, len(current_module) // 10),
            })

        return modules

    @staticmethod
    def _derive_module_name(files: List[str]) -> str:
        if not files:
            return "unknown"
        components: Dict[str, int] = Counter()
        for f in files:
            parts = f.replace("\\", "/").split("/")
            if len(parts) >= 2:
                components[parts[-2]] += 1
            elif parts:
                components[parts[0]] += 1
        if components:
            return components.most_common(1)[0][0]
        return os.path.splitext(os.path.basename(files[0]))[0]


class IncludeResolver:
    def __init__(self, project_root: str, include_paths: List[str]):
        self.project_root = Path(project_root).resolve()
        self.include_paths: List[Path] = [Path(p).resolve() for p in include_paths]
        default_include = self.project_root
        if default_include not in self.include_paths:
            self.include_paths.insert(0, default_include)
        self._cache: Dict[str, str | None] = {}

        self._file_index: Dict[str, str] = {}
        self._built_index = False

    def _build_file_index(self):
        if self._built_index:
            return
        self._built_index = True
        common_dirs = ["include", "src", "lib", "inc", "source"]
        search_roots = [self.project_root] + self.include_paths
        for root in search_roots:
            for sub in common_dirs:
                sub_path = root / sub
                if sub_path.is_dir():
                    self._walk_index(root, sub_path)
            self._walk_index(root, root)

    def _walk_index(self, base_root: Path, walk_root: Path):
        try:
            base_root = base_root.resolve()
            walk_root = walk_root.resolve()
            for filepath in walk_root.rglob("*"):
                if filepath.is_file():
                    name = filepath.name
                    full = str(filepath.resolve())
                    self._file_index[name] = full
                    self._file_index[full] = full
                    try:
                        rel = str(filepath.relative_to(base_root)).replace("\\", "/")
                        self._file_index[rel] = full
                    except ValueError:
                        pass
        except (PermissionError, OSError):
            pass

    def resolve(self, include: str, source_file: str) -> str | None:
        cache_key = f"{include}|{source_file}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        source_dir = Path(source_file).parent.resolve()
        candidate = (source_dir / include).resolve()
        if candidate.exists() and candidate.is_file():
            self._cache[cache_key] = str(candidate)
            return str(candidate)

        for inc_dir in self.include_paths:
            candidate = (inc_dir / include).resolve()
            if candidate.exists() and candidate.is_file():
                self._cache[cache_key] = str(candidate)
                return str(candidate)

        direct = (self.project_root / include).resolve()
        if direct.exists() and direct.is_file():
            self._cache[cache_key] = str(direct)
            return str(direct)

        self._build_file_index()
        include_name = include.replace("\\", "/")
        basename = include_name.split("/")[-1]

        if include_name in self._file_index:
            resolved = self._file_index[include_name]
            if Path(resolved).exists():
                self._cache[cache_key] = resolved
                return resolved

        suffix = "/" + include_name
        for key, val in self._file_index.items():
            if key == include_name or key.endswith(suffix):
                if Path(val).exists():
                    self._cache[cache_key] = val
                    return val

        if basename in self._file_index:
            resolved = self._file_index[basename]
            if Path(resolved).exists():
                candidates = [resolved]
                for key, val in self._file_index.items():
                    if key == resolved:
                        continue
                    if key.endswith("/" + basename) or key == basename:
                        candidates.append(val)
                if candidates and len(candidates) == 1:
                    self._cache[cache_key] = candidates[0]
                    return candidates[0]

        self._cache[cache_key] = None
        return None


def build_module_partitions(
    file_paths: List[str],
    project_root: str,
    strategy: str = "auto",
    include_paths: List[str] = None,
) -> List[Dict]:
    graph = IncludeGraph()
    graph.build(file_paths, project_root, include_paths)
    sccs = graph.find_sccs()
    modules = graph.group_sccs_into_modules(sccs, file_paths)
    return modules
