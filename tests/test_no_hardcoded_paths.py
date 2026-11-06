"""Guard test: scan for hardcoded absolute paths in source files."""

import pathlib
import re
import sys

# Directories to scan
SCAN_DIRS = [
    "src",
    "backend",
    "scripts",
    "experiments",
]

# Patterns to detect hardcoded paths
HARDCODED_PATTERNS = [
    r"/home/",
    r"/Users/",
    r"C:\\",
    r"C:/",
]

# Directories/files to skip
SKIP_DIRS = {
    ".venv",
    "__pycache__",
    "node_modules",
    ".git",
    ".pytest_cache",
    ".mypy_cache",
    "dist",
    "build",
    ".tox",
    ".coverage",
    "htmlcov",
}
SKIP_FILES = {".pyc", ".pyo", ".pyd", ".so", ".dll", ".class", ".o", ".a", ".lib"}

# File extensions to scan
PY_EXTENSIONS = {".py"}

# Regex to find string literals and comments containing paths
# This regex finds string literals (single/double/triple quoted) and comments
STRING_PATTERN = re.compile(
    r'(?:"""[\s\S]*?"""|\'\'\'[\s\S]*?\'\'\'|"[^"\\]*(?:\\.[^"\\]*)*"|\'[^\'\\]*(?:\\.[^\'\\]*)*\')'
)


def should_skip_dir(dirname: str) -> bool:
    """Check if directory should be skipped."""
    return dirname in SKIP_DIRS


def should_skip_file(filename: str) -> bool:
    """Check if file should be skipped."""
    return any(filename.endswith(ext) for ext in SKIP_FILES) or not any(
        filename.endswith(ext) for ext in PY_EXTENSIONS
    )


def find_hardcoded_paths(filepath: pathlib.Path) -> list[tuple[int, str]]:
    """Find hardcoded paths in a Python file. Returns list of (line_number, matched_text)."""
    hits = []
    try:
        content = filepath.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return hits

    lines = content.splitlines()
    for line_num, line in enumerate(lines, 1):
        # Check for hardcoded patterns in string literals
        for match in STRING_PATTERN.finditer(line):
            literal = match.group(0)
            for pattern in HARDCODED_PATTERNS:
                if re.search(pattern, literal):
                    hits.append((line_num, literal.strip()))
                    break

    return hits


def scan_for_hardcoded_paths(root: pathlib.Path) -> list[tuple[str, int, str]]:
    """Scan all Python files for hardcoded paths. Returns list of (file, line, match)."""
    all_hits = []

    for scan_dir in SCAN_DIRS:
        scan_path = root / scan_dir
        if not scan_path.exists():
            continue

        for filepath in scan_path.rglob("*.py"):
            # Check if any parent directory should be skipped
            if any(part in SKIP_DIRS for part in filepath.parts):
                continue

            if should_skip_file(filepath.name):
                continue

            hits = find_hardcoded_paths(filepath)
            for line_num, match in hits:
                rel_path = filepath.relative_to(root)
                all_hits.append((str(rel_path), line_num, match))

    return all_hits


def test_no_hardcoded_paths():
    """Test that no hardcoded absolute paths exist in source files."""
    root = pathlib.Path(__file__).resolve().parents[1]  # repo root
    hits = scan_for_hardcoded_paths(root)

    if hits:
        error_msg = "Hardcoded absolute paths found:\n"
        for filepath, line_num, match in hits:
            error_msg += f"  {filepath}:{line_num}: {match}\n"
        raise AssertionError(error_msg)


if __name__ == "__main__":
    try:
        test_no_hardcoded_paths()
        print("PASS: No hardcoded absolute paths found")
        sys.exit(0)
    except AssertionError as e:
        print(e)
        sys.exit(1)
