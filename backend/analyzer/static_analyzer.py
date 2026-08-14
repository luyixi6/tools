import asyncio
from pathlib import Path
from typing import List, Dict, Any, Optional

from ..config import get_config
from ..llm.base_client import BaseLLMClient
from ..llm.prompt_builder import (
    build_module_prompt, estimate_tokens, split_large_file,
)
from ..llm.response_parser import parse_analysis_response
from .tool_runner import run_tools


class ModuleAnalyzer:
    def __init__(self, client: Optional[BaseLLMClient] = None):
        self.config = get_config()
        if client:
            self.client = client
        else:
            from ..llm.client_factory import create_client
            api = self.config.api
            self.client = create_client(
                provider=api.provider,
                api_key=api.api_key,
                model=api.effective_model(),
                max_tokens=api.max_tokens,
                base_url=api.base_url or None,
                rate_limit_rpm=self.config.batch.rate_limit_rpm,
                extra_headers=api.extra_headers or None,
            )

    async def analyze_module(
        self, module: dict, progress_callback=None,
    ) -> List[Dict[str, Any]]:
        module_files = module.get("files", [])
        if not module_files:
            return []

        file_contents = []
        for fp in module_files:
            try:
                content = Path(fp).read_text(encoding="utf-8", errors="ignore")
            except Exception:
                content = ""
            file_contents.append({
                "path": fp,
                "relative_path": fp,
                "content": content,
            })

        analysis_types = []
        if self.config.analysis.static_check:
            analysis_types.append("static")
        if self.config.analysis.dynamic_check:
            analysis_types.append("dynamic")

        deps = []
        for dep_name in module.get("dependencies", []):
            try:
                dep_content = Path(dep_name).read_text(
                    encoding="utf-8", errors="ignore"
                )
                deps.append({
                    "name": dep_name,
                    "interface_summary": self._extract_interface(dep_content),
                })
            except Exception:
                pass

        max_batch = self.config.chunking.max_tokens_per_batch
        max_file = self.config.chunking.max_file_tokens

        batch_files = []
        batch_tokens = 0
        all_issues = []

        for fc in file_contents:
            content = fc["content"]
            file_tokens = estimate_tokens(content)

            if file_tokens > max_file:
                parts = split_large_file(content, max_file)
                for part in parts:
                    part_fc = {
                        **fc,
                        "relative_path": f"{fc['relative_path']} (part {part['part'] + 1}/{len(parts)})",
                        "content": part["content"],
                    }
                    part_tokens = estimate_tokens(part["content"])
                    if batch_tokens + part_tokens > max_batch and batch_files:
                        issues = await self._analyze_batch(
                            module, batch_files, deps, analysis_types,
                        )
                        for issue in issues:
                            issue["line_start"] += part.get("start_line", 1) - 1
                            issue["line_end"] += part.get("start_line", 1) - 1
                        all_issues.extend(issues)
                        batch_files = []
                        batch_tokens = 0
                        if progress_callback:
                            await progress_callback(module)
                    batch_files.append(part_fc)
                    batch_tokens += part_tokens
            else:
                if batch_tokens + file_tokens > max_batch and batch_files:
                    issues = await self._analyze_batch(
                        module, batch_files, deps, analysis_types,
                    )
                    all_issues.extend(issues)
                    batch_files = []
                    batch_tokens = 0
                    if progress_callback:
                        await progress_callback(module)
                batch_files.append(fc)
                batch_tokens += file_tokens

        if batch_files:
            issues = await self._analyze_batch(
                module, batch_files, deps, analysis_types,
            )
            all_issues.extend(issues)
            if progress_callback:
                await progress_callback(module)

        return all_issues

    async def _analyze_batch(
        self, module: dict, batch_files: List[dict],
        dependencies: List[dict], analysis_types: List[str],
    ) -> List[Dict[str, Any]]:
        cfg = self.config

        tool_results = []
        if cfg.analysis.tools.clang_tidy or cfg.analysis.tools.cppcheck:
            for bf in batch_files:
                tr = run_tools(
                    bf["path"],
                    compile_commands_dir=cfg.project.compile_commands or None,
                    project_root=cfg.project.root or None,
                    enable_clang_tidy=cfg.analysis.tools.clang_tidy,
                    enable_cppcheck=cfg.analysis.tools.cppcheck,
                )
                tool_results.extend(tr)

        if tool_results:
            tool_text = self._format_tool_results(tool_results)
            batch_files = [{
                **bf,
                "content": bf["content"] + f"\n/* Pre-analysis tool findings:\n{tool_text}\n*/",
            } for bf in batch_files]

        system_prompt, user_content = build_module_prompt(
            module.get("name", "unknown"),
            batch_files,
            dependencies,
            analysis_types,
            language=self.config.language,
        )

        try:
            response = await self.client.analyze_code(
                system_prompt=system_prompt,
                code_content=user_content,
                max_tokens=cfg.api.max_tokens,
            )
        except Exception as e:
            return [{
                "title": f"LLM analysis failed: {str(e)}",
                "file": batch_files[0]["relative_path"] if batch_files else "",
                "severity": "medium",
                "category": "other",
                "description": str(e),
                "line_start": 0,
                "line_end": 0,
                "original_code": "",
                "suggested_code": "",
                "rule_reference": "",
            }]

        return parse_analysis_response(response)

    @staticmethod
    def _extract_interface(content: str) -> str:
        lines = content.split("\n")
        interface_lines = []
        depth = 0
        in_interface = False

        for line in lines:
            stripped = line.strip()
            if stripped.startswith("class ") or stripped.startswith("struct "):
                in_interface = True
            if stripped.startswith("template"):
                in_interface = True

            if in_interface:
                interface_lines.append(line)
                depth += stripped.count("{") - stripped.count("}")
                if depth <= 0 and ("};" in stripped or stripped.endswith("}")):
                    in_interface = False
                    depth = 0
                    continue
                if depth <= 0 and stripped.endswith(";"):
                    in_interface = False
                    depth = 0
            elif not stripped.startswith("#") and stripped and not stripped.startswith("//"):
                if stripped.endswith(";") and "{" not in stripped:
                    interface_lines.append(line)

        return "\n".join(interface_lines[:200])

    @staticmethod
    def _format_tool_results(results: List[Dict]) -> str:
        lines = []
        for r in results[:50]:
            tool = r.get("tool", "unknown")
            msg = r.get("message", "")
            file = r.get("file", "")
            line = r.get("line", "")
            lines.append(f"[{tool}] {file}:{line} - {msg}")
        return "\n".join(lines)
