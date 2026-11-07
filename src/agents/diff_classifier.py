"""Diff classification utility - determines if a patch is behavior-changing or cosmetic.

A patch is BEHAVIOR-CHANGING if it touches at least one executable statement /
non-comment token outside docstrings/comments/blank lines.

A patch is COSMETIC if it only contains:
- Comments (single-line # or multi-line strings)
- Docstrings (function/class/module level string literals)
- Blank lines
- Whitespace changes
"""

import ast
import difflib
from dataclasses import dataclass
from typing import List, Set


@dataclass
class DiffClassification:
    """Result of diff classification."""

    is_behavior_changing: bool
    reason: str
    changed_lines: List[int]
    behavior_changes: List[str]
    cosmetic_changes: List[str]


def _get_node_lines(node: ast.AST) -> Set[int]:
    """Get all line numbers covered by an AST node."""
    lines = set()
    if hasattr(node, "lineno"):
        lines.add(node.lineno)
    if hasattr(node, "end_lineno") and node.end_lineno:
        lines.update(range(node.lineno, node.end_lineno + 1))
    for child in ast.iter_child_nodes(node):
        lines.update(_get_node_lines(child))
    return lines


def _is_docstring_node(node: ast.AST) -> bool:
    """Check if a node is a docstring (string literal at module/class/function level)."""
    if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
        if isinstance(node.value.value, str):
            return True
    return False


def _is_comment_or_blank(line: str) -> bool:
    """Check if a line is a comment or blank."""
    stripped = line.strip()
    return stripped == "" or stripped.startswith("#")


def _is_docstring_line(code: str, line_num: int) -> bool:
    """Check if a line is inside a docstring by parsing with AST."""
    try:
        tree = ast.parse(code)
        for node in ast.walk(tree):
            if _is_docstring_node(node):
                if hasattr(node, "lineno") and hasattr(node, "end_lineno"):
                    if node.lineno <= line_num <= (node.end_lineno or node.lineno):
                        return True
    except SyntaxError:
        pass
    return False


def _get_changed_lines(original: str, patched: str) -> tuple:
    """Get line numbers of changed lines in both original and patched versions."""
    original_lines = original.splitlines()
    patched_lines = patched.splitlines()

    matcher = difflib.SequenceMatcher(None, original_lines, patched_lines)

    original_changed = set()
    patched_changed = set()

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag != "equal":
            # Lines that changed in original (0-indexed)
            original_changed.update(range(i1, i2))
            # Lines that changed in patched (0-indexed)
            patched_changed.update(range(j1, j2))

    return original_changed, patched_changed


def _contains_executable_token(line: str) -> bool:
    """Heuristic: check if a line contains executable Python tokens (not just comments/docstrings)."""
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return False
    # Simple heuristic: if it has Python keywords or operators, it's likely executable
    executable_tokens = [
        "=",
        "+=",
        "-=",
        "*=",
        "/=",
        "//=",
        "%=",
        "**=",
        "&=",
        "|=",
        "^=",
        ">>=",
        "<<=",
        "return",
        "raise",
        "assert",
        "del",
        "if",
        "for",
        "while",
        "try",
        "with",
        "def",
        "class",
        "import",
        "from",
        "global",
        "nonlocal",
        "yield",
        "await",
        "lambda",
        "+",
        "-",
        "*",
        "/",
        "//",
        "%",
        "**",
        "@",
        "==",
        "!=",
        "<",
        ">",
        "<=",
        ">=",
        "is",
        "in",
        "not",
        "and",
        "or",
        "not",
    ]
    # Check for assignment-like patterns
    if any(token in line for token in executable_tokens):
        # But exclude if it's just a string literal (docstring)
        if stripped.startswith('"""') or stripped.startswith("'''"):
            return False
        return True
    return False


def classify_diff(original_code: str, patched_code: str) -> DiffClassification:
    """
    Classify a diff as behavior-changing or cosmetic.

    Args:
        original_code: Original source code
        patched_code: Patched source code

    Returns:
        DiffClassification with is_behavior_changing flag and details
    """
    if original_code == patched_code:
        return DiffClassification(
            is_behavior_changing=False,
            reason="No changes detected",
            changed_lines=[],
            behavior_changes=[],
            cosmetic_changes=["No changes"],
        )

    # Get changed line numbers (0-indexed)
    original_changed, patched_changed = _get_changed_lines(original_code, patched_code)

    if not original_changed and not patched_changed:
        return DiffClassification(
            is_behavior_changing=False,
            reason="Only whitespace changes",
            changed_lines=[],
            behavior_changes=[],
            cosmetic_changes=["Whitespace only"],
        )

    # Analyze each changed line in the patched version
    patched_lines = patched_code.splitlines()

    cosmetic_changes = []
    behavior_changes = []

    for line_idx in sorted(patched_changed):
        if line_idx < len(patched_lines):
            line = patched_lines[line_idx]
            line_num = line_idx + 1  # 1-indexed for reporting

            if _is_comment_or_blank(line):
                cosmetic_changes.append(f"Line {line_num}: {line.strip()[:80]}")
            elif _is_docstring_line(patched_code, line_num):
                cosmetic_changes.append(
                    f"Line {line_num}: {line.strip()[:80]} (docstring)"
                )
            elif _contains_executable_token(line):
                behavior_changes.append(f"Line {line_num}: {line.strip()[:80]}")
            else:
                # Could be a docstring or other non-behavior content
                cosmetic_changes.append(f"Line {line_num}: {line.strip()[:80]}")

    is_behavior_changing = len(behavior_changes) > 0

    if is_behavior_changing:
        changed_line_nums = sorted(
            [int(c.split(":")[0].split()[-1]) for c in behavior_changes]
        )
        reason = (
            f"Behavior-changing modifications detected on lines: {changed_line_nums}"
        )
    else:
        reason = (
            "Patch is cosmetic (only comments, docstrings, blank lines, or whitespace)"
        )

    return DiffClassification(
        is_behavior_changing=is_behavior_changing,
        reason=reason,
        changed_lines=sorted([line + 1 for line in patched_changed]),
        behavior_changes=behavior_changes,
        cosmetic_changes=cosmetic_changes,
    )


def is_behavior_changing(original_code: str, patched_code: str) -> bool:
    """Quick check if a diff is behavior-changing."""
    return classify_diff(original_code, patched_code).is_behavior_changing
