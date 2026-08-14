CPP_ANALYSIS_SYSTEM_PROMPT = """You are an expert C++ code reviewer. Analyze the provided C++ code for issues.

## Analysis Rules

### Static Analysis
1. **Memory Safety**: raw new/delete without smart pointers, potential memory leaks, dangling pointers, double-free
2. **Type Safety**: implicit narrowing conversions, C-style casts, signed/unsigned mismatches, reinterpret_cast abuse
3. **Exception Safety**: missing RAII, non-noexcept destructors, resource leaks on exception paths
4. **Const Correctness**: parameters/functions that should be const, const_cast abuse
5. **Undefined Behavior**: uninitialized variables, out-of-bounds access, null dereference, use-after-move
6. **Modern C++**: missing override, raw loops that could be algorithms, C-style arrays vs std::array/vector, missing auto where appropriate

### Dynamic Analysis (Simulated Execution Paths)
7. **Control Flow**: unreachable code, missing switch cases, all branches reachable, infinite loops
8. **Function Contracts**: pre/post conditions, argument validation, return value handling
9. **Concurrency**: potential data races, missing mutex locks, atomic operations correctness
10. **Resource Lifecycle**: file handles not closed, RAII violations, double-close
11. **Error Handling**: missing error checks, swallowed exceptions, error code propagation

For each issue found, output a JSON object in this exact format:

{
  "issues": [
    {
      "severity": "critical|high|medium|low",
      "category": "memory_safety|concurrency|exception_safety|modern_cpp|code_style|type_safety|undefined_behavior|performance|other",
      "file": "relative/path/to/file.cpp",
      "line_start": 42,
      "line_end": 45,
      "title": "Brief issue title",
      "description": "Detailed explanation of the issue and why it matters",
      "original_code": "exact code snippet from the file that has the issue",
      "suggested_code": "corrected version of the code snippet",
      "rule_reference": "C++ Core Guidelines F.6 or relevant reference"
    }
  ]
}

Important:
- Only report real issues, not style preferences without impact
- original_code and suggested_code MUST be exact, compilable code snippets
- If no issues are found, return {"issues": []}
- Output ONLY the JSON, no other text
"""

PROMPT_STATIC = """
Focus on:
- Memory management (raw pointers, leaks, RAII)
- Type safety (casts, conversions)
- Exception safety
- Const correctness
- Undefined behavior risks
"""

PROMPT_DYNAMIC = """
Focus on:
- Execution path analysis: trace all code paths for edge cases
- Loop termination guarantees
- Recursion depth limits
- Resource acquisition/release pairing across all branches
- Concurrency: race conditions, deadlock potential
- Error handling completeness
"""

PROMPT_COMBINED = CPP_ANALYSIS_SYSTEM_PROMPT


def _language_instruction(language: str) -> str:
    if language and language.lower().startswith("zh"):
        return (
            "\n\nIMPORTANT: Write the 'title' and 'description' fields in Simplified Chinese (中文). "
            "Keep the 'category', 'severity', 'file', 'original_code', 'suggested_code', "
            "and 'rule_reference' fields in their original format."
        )
    return ""


def build_module_prompt(
    module_name: str,
    files: list[dict],
    dependencies: list[str],
    analysis_types: list[str],
    language: str = "en",
) -> tuple[str, str]:
    system_prompt = CPP_ANALYSIS_SYSTEM_PROMPT + _language_instruction(language)

    user_content = f"## Module: {module_name}\n\n"

    if dependencies:
        user_content += "### Upstream dependency interfaces (read-only context):\n"
        for dep in dependencies:
            dep_content = dep.get("interface_summary", "")
            if dep_content:
                user_content += f"```cpp\n// {dep.get('name', 'unknown')}\n{dep_content}\n```\n\n"

    type_hints = []
    if "static" in analysis_types:
        type_hints.append(PROMPT_STATIC)
    if "dynamic" in analysis_types:
        type_hints.append(PROMPT_DYNAMIC)
    if type_hints:
        user_content += "### Analysis focus:\n" + "\n".join(type_hints) + "\n\n"

    user_content += "### Module implementation:\n"
    for f in files:
        rel_path = f.get("relative_path", "unknown")
        content = f.get("content", "")
        user_content += f"#### {rel_path}\n```cpp\n{content}\n```\n\n"

    return system_prompt, user_content


def estimate_tokens(text: str) -> int:
    return len(text) // 4


def split_large_file(content: str, max_tokens: int) -> list[dict]:
    token_estimate = estimate_tokens(content)
    if token_estimate <= max_tokens:
        return [{"part": 0, "content": content, "start_line": 1}]

    lines = content.split("\n")
    parts = []
    current_lines = []
    current_tokens = 0
    start_line = 1

    for line in lines:
        line_tokens = estimate_tokens(line) + 1
        if current_tokens + line_tokens > max_tokens and current_lines:
            parts.append({
                "part": len(parts),
                "content": "\n".join(current_lines),
                "start_line": start_line,
            })
            start_line += len(current_lines)
            current_lines = []
            current_tokens = 0
        current_lines.append(line)
        current_tokens += line_tokens

    if current_lines:
        parts.append({
            "part": len(parts),
            "content": "\n".join(current_lines),
            "start_line": start_line,
        })

    return parts
