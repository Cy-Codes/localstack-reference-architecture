#!/usr/bin/env python3
"""
Pre-commit Auto-Formatter & Unused Import/Using Cleaner.
Uses default language formatters where available (`dotnet format`, `ruff`, `black`, `isort`, `shfmt`)
and provides deterministic Roslyn `IDE0005` + Python `ast` fallbacks so unused `using` and `import`
statements are always removed automatically.
"""
from __future__ import annotations

import ast
from dataclasses import dataclass
import os
import re
import shutil
import subprocess
import sys

INDENT_SPACES: int = 4
CSHARP_IDE0005_PATTERN: re.Pattern[str] = re.compile(
    r"^(?P<path>.+\.cs)\((?P<line>\d+),\d+\):\s+warning\s+IDE0005:"
)
CSHARP_USING_PATTERN: re.Pattern[str] = re.compile(
    r"^\s*using\s+(?:(?P<static>static)\s+)?(?:(?P<alias>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*)?(?P<ns>[A-Za-z0-9_.]+)\s*;\s*$"
)
TEXT_EXTENSIONS: frozenset[str] = frozenset(
    {".cs", ".py", ".sql", ".sh", ".md", ".json", ".yml", ".yaml", ".props", ".slnx"}
)
EXCLUDED_PATH_SEGMENTS: tuple[str, ...] = (
    "/.air/",
    "/bin/",
    "/obj/",
    "/.git/",
    "/migrations/V",
)


def is_Format_eligible(filepath: str) -> bool:
    """Pure check ensuring build outputs, IDE state, and immutable Flyway migrations are never mutated."""
    normalized = filepath.replace("\\", "/")
    ext = os.path.splitext(normalized)[1].lower()
    return (
        ext in TEXT_EXTENSIONS
        and not any(segment in normalized for segment in EXCLUDED_PATH_SEGMENTS)
        and os.path.isfile(filepath)
    )


@dataclass(frozen=True)
class UnusedUsingDiagnostic:
    """Immutable descriptor of a Roslyn IDE0005 unnecessary using warning."""
    filepath: str
    line_number: int


def normalize_whitespace(content: str, preserve_markdown_breaks: bool = False) -> str:
    """Pure transformation normalizing CRLF to LF, stripping trailing spaces, and ensuring single EOF newline."""
    normalized_lines = tuple(
        line if (preserve_markdown_breaks and line.endswith("  ")) else line.rstrip(" \t")
        for line in content.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    )
    body = "\n".join(normalized_lines).rstrip("\n")
    return f"{body}\n" if body else ""


# ============================================================================
# Python AST Unused Import Remover & Sorter
# ============================================================================

def collect_used_python_names(tree: ast.AST) -> frozenset[str]:
    """Pure AST traversal collecting all referenced identifier names outside import statements."""
    import_nodes = {
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
    }
    referenced: set[str] = set()
    for node in ast.walk(tree):
        if node in import_nodes:
            continue
        if isinstance(node, ast.Name):
            referenced.add(node.id)
        elif isinstance(node, ast.Attribute):
            curr: ast.AST = node
            while isinstance(curr, ast.Attribute):
                curr = curr.value
            if isinstance(curr, ast.Name):
                referenced.add(curr.id)
    return frozenset(referenced)


def format_import_node(node: ast.Import | ast.ImportFrom, kept_aliases: tuple[ast.alias, ...]) -> str:
    """Pure formatter reconstructing a single Python import statement from kept aliases."""
    sorted_aliases = sorted(kept_aliases, key=lambda a: (a.name, a.asname or ""))
    rendered_names = ", ".join(
        f"{alias.name} as {alias.asname}" if alias.asname else alias.name
        for alias in sorted_aliases
    )
    if isinstance(node, ast.Import):
        return f"import {rendered_names}"
    module_prefix = "." * (node.level or 0) + (node.module or "")
    return f"from {module_prefix} import {rendered_names}"


def remove_unused_python_imports(source: str) -> str:
    """Pure AST-based transformation removing unused top-level Python imports."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return source

    used_names = collect_used_python_names(tree)
    lines = source.splitlines()
    lines_to_remove: set[int] = set()
    line_replacements: dict[int, str] = {}

    for node in tree.body:
        if not isinstance(node, (ast.Import, ast.ImportFrom)):
            continue
        if isinstance(node, ast.ImportFrom) and node.module == "__future__":
            continue
        if any(alias.name == "*" for alias in node.names):
            continue

        kept_aliases = tuple(
            alias
            for alias in node.names
            if (alias.asname or alias.name.split(".")[0]) in used_names
        )

        start_line = node.lineno - 1
        end_line = (node.end_lineno or node.lineno) - 1

        if len(kept_aliases) == len(node.names):
            continue

        for line_idx in range(start_line, end_line + 1):
            lines_to_remove.add(line_idx)

        if kept_aliases:
            line_replacements[start_line] = format_import_node(node, kept_aliases)

    updated_lines = [
        line_replacements[idx]
        if idx in line_replacements
        else line
        for idx, line in enumerate(lines)
        if idx not in lines_to_remove or idx in line_replacements
    ]
    return "\n".join(updated_lines) + "\n"


def format_python_file(filepath: str) -> bool:
    """Side-effecting formatter applying default Python formatters (ruff/isort/black) or AST fallback."""
    if shutil.which("ruff"):
        subprocess.run(["ruff", "check", "--select", "F401,I", "--fix", "--quiet", filepath], check=False)
        subprocess.run(["ruff", "format", "--quiet", filepath], check=False)

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            original = f.read()
    except OSError:
        return False

    cleaned = normalize_whitespace(remove_unused_python_imports(original))
    if cleaned != original:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(cleaned)
        return True
    return False


# ============================================================================
# C# Unused Using Cleaner & Sorter (Roslyn IDE0005 + Default Formatting)
# ============================================================================

def sort_csharp_usings_in_content(content: str) -> str:
    """Pure transformation sorting top-of-file C# using directives (System.* first, then alphabetical)."""
    lines = content.splitlines()
    using_indices: list[int] = []

    for idx, line in enumerate(lines):
        stripped = line.strip()
        if not stripped and using_indices:
            continue
        if CSHARP_USING_PATTERN.match(line):
            using_indices.append(idx)
        elif stripped.startswith("//") and not using_indices:
            continue
        elif using_indices:
            break
        else:
            break

    if not using_indices:
        return content

    first_idx = using_indices[0]
    last_idx = using_indices[-1]
    raw_using_lines = [
        lines[i].strip()
        for i in range(first_idx, last_idx + 1)
        if lines[i].strip()
    ]

    def using_sort_key(using_line: str) -> tuple[int, str]:
        match = CSHARP_USING_PATTERN.match(using_line)
        if not match:
            return (3, using_line)
        if match.group("alias"):
            return (2, using_line)
        if match.group("static"):
            return (1, match.group("ns"))
        ns = match.group("ns")
        is_system = ns == "System" or ns.startswith("System.")
        return (0 if is_system else 1, ns)

    deduped_sorted = sorted(set(raw_using_lines), key=using_sort_key)
    new_lines = lines[:first_idx] + deduped_sorted + lines[last_idx + 1:]
    return "\n".join(new_lines) + "\n"


def parse_ide0005_diagnostics(build_output: str) -> tuple[UnusedUsingDiagnostic, ...]:
    """Pure parser extracting unique (filepath, line_number) pairs from Roslyn IDE0005 build warnings."""
    diagnostics: set[UnusedUsingDiagnostic] = set()
    for raw_line in build_output.splitlines():
        match = CSHARP_IDE0005_PATTERN.match(raw_line.strip())
        if match:
            diagnostics.add(
                UnusedUsingDiagnostic(
                    filepath=os.path.abspath(match.group("path")),
                    line_number=int(match.group("line")),
                )
            )
    return tuple(sorted(diagnostics, key=lambda d: (d.filepath, -d.line_number)))


def remove_flagged_csharp_usings(diagnostics: tuple[UnusedUsingDiagnostic, ...]) -> set[str]:
    """Side-effecting helper removing lines flagged by Roslyn IDE0005 and sorting remaining usings."""
    lines_by_file: dict[str, set[int]] = {}
    for diag in diagnostics:
        lines_by_file.setdefault(diag.filepath, set()).add(diag.line_number)

    modified_files: set[str] = set()
    for filepath, line_numbers in lines_by_file.items():
        if not os.path.exists(filepath):
            continue
        with open(filepath, "r", encoding="utf-8") as f:
            original = f.read()

        kept_lines = [
            line
            for idx, line in enumerate(original.splitlines(), start=1)
            if idx not in line_numbers
        ]
        cleaned = normalize_whitespace(sort_csharp_usings_in_content("\n".join(kept_lines)))
        if cleaned != original:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(cleaned)
            modified_files.add(filepath)
    return modified_files


def format_csharp_workspace(repo_root: str, csharp_files: tuple[str, ...]) -> set[str]:
    """Runs default `dotnet format` when available plus Roslyn IDE0005 unused-using cleanup."""
    modified: set[str] = set()
    solution_path = os.path.join(repo_root, "CrmApi", "CrmApi.slnx")
    dotnet_bin = shutil.which("dotnet") or "/opt/homebrew/bin/dotnet"

    if os.path.exists(solution_path) and os.path.exists(dotnet_bin):
        env = {
            **os.environ,
            "DOTNET_CLI_HOME": os.environ.get("DOTNET_CLI_HOME", "/tmp"),
            "DOTNET_SKIP_FIRST_TIME_EXPERIENCE": "1",
        }
        # 1. Try default `dotnet format` (works when out-of-process build host is permitted)
        subprocess.run(
            [dotnet_bin, "format", solution_path, "--no-restore", "--verbosity", "quiet"],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )

        # 2. Run Roslyn build with IDE0005 enabled to strip any remaining unused usings deterministically
        build_res = subprocess.run(
            [dotnet_bin, "build", solution_path, "--no-restore", "--no-incremental", "-m:1"],
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        diagnostics = parse_ide0005_diagnostics(build_res.stdout + "\n" + build_res.stderr)
        modified.update(remove_flagged_csharp_usings(diagnostics))

        # Clean up any temporary `/tmp` or `.local` artifacts if created in workspace
        local_dir = os.path.join(repo_root, ".local")
        if os.path.isdir(local_dir):
            shutil.rmtree(local_dir, ignore_errors=True)

    for filepath in csharp_files:
        if not os.path.exists(filepath):
            continue
        with open(filepath, "r", encoding="utf-8") as f:
            original = f.read()
        sorted_and_cleaned = normalize_whitespace(sort_csharp_usings_in_content(original))
        if sorted_and_cleaned != original:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(sorted_and_cleaned)
            modified.add(os.path.abspath(filepath))

    return modified


# ============================================================================
# Shell & Generic Text Formatting
# ============================================================================

def format_generic_file(filepath: str) -> bool:
    """Formats shell scripts (via shfmt if installed) and normalizes whitespace/newlines."""
    ext = os.path.splitext(filepath)[1].lower()
    if ext == ".sh" and shutil.which("shfmt"):
        subprocess.run(["shfmt", "-w", "-i", str(INDENT_SPACES), filepath], check=False)

    if ext not in TEXT_EXTENSIONS:
        return False

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            original = f.read()
    except (OSError, UnicodeDecodeError):
        return False

    cleaned = normalize_whitespace(original, preserve_markdown_breaks=(ext == ".md"))
    if cleaned != original:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(cleaned)
        return True
    return False


def discover_all_tracked_files(repo_root: str) -> tuple[str, ...]:
    """Discovers all tracked source files across root and submodules when `--all` is passed."""
    collected: list[str] = []
    subrepos = ("", "CrmApi", "CRMDatabaseMS", "CRMDatabasePG")
    for sub in subrepos:
        sub_dir = os.path.join(repo_root, sub) if sub else repo_root
        if not os.path.isdir(sub_dir):
            continue
        res = subprocess.run(
            ["git", "-C", sub_dir, "ls-files", "--cached", "--others", "--exclude-standard"],
            capture_output=True,
            text=True,
            check=False,
        )
        for rel in res.stdout.splitlines():
            full_path = os.path.abspath(os.path.join(sub_dir, rel))
            if is_Format_eligible(full_path):
                collected.append(full_path)
    return tuple(sorted(set(collected)))


def main() -> int:
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    args = sys.argv[1:]

    if not args or "--all" in args:
        target_files = discover_all_tracked_files(repo_root)
    else:
        target_files = tuple(
            os.path.abspath(arg)
            for arg in args
            if is_Format_eligible(os.path.abspath(arg))
        )

    csharp_files = tuple(f for f in target_files if f.endswith(".cs"))
    python_files = tuple(f for f in target_files if f.endswith(".py"))
    other_files = tuple(f for f in target_files if not f.endswith((".cs", ".py")))

    modified_files: set[str] = set()

    if csharp_files:
        modified_files.update(format_csharp_workspace(repo_root, csharp_files))

    for py_file in python_files:
        if format_python_file(py_file):
            modified_files.add(py_file)

    for other_file in other_files:
        if format_generic_file(other_file):
            modified_files.add(other_file)

    if modified_files:
        for mod in sorted(modified_files):
            rel = os.path.relpath(mod, repo_root)
            print(f"  [Auto-Formatted] {rel}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
