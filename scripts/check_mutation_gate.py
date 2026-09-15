"""Fail CI when filesystem mutation APIs appear outside approved gateways."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = ROOT / "src"

# Filesystem mutations must stay in the policy-reviewed executor gateway.
APPROVED_PREFIXES = (Path("src/cdrive_cleaner/executors"),)

MUTATING_CALLS = {
    "os.remove",
    "os.unlink",
    "os.rmdir",
    "os.removedirs",
    "shutil.rmtree",
    "Path.unlink",
    "Path.rmdir",
}


@dataclass(frozen=True)
class Violation:
    """One disallowed mutation call."""

    path: Path
    line: int
    call: str


def _call_name(node: ast.Call) -> str | None:
    value = node.func
    if isinstance(value, ast.Attribute) and isinstance(value.value, ast.Name):
        return f"{value.value.id}.{value.attr}"
    return None


def _approved(relative: Path) -> bool:
    return any(relative == prefix or prefix in relative.parents for prefix in APPROVED_PREFIXES)


def find_violations(source_root: Path = SOURCE_ROOT) -> list[Violation]:
    """Return direct mutation calls outside explicitly approved modules."""

    violations: list[Violation] = []
    for path in source_root.rglob("*.py"):
        relative = path.relative_to(ROOT)
        if _approved(relative):
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = _call_name(node)
            if name in MUTATING_CALLS:
                violations.append(Violation(relative, node.lineno, name))
    return violations


def main() -> int:
    """Print actionable violations and return a CI-friendly status code."""

    violations = find_violations()
    if not violations:
        print("Mutation gate passed: no direct delete calls outside approved gateways.")
        return 0
    for item in violations:
        print(f"{item.path}:{item.line}: disallowed direct mutation call {item.call}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
