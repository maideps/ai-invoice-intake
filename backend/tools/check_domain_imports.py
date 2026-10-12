"""Architecture rule arch-007: the domain layer imports only the standard library and itself.

Run from ``backend/``: ``python tools/check_domain_imports.py``. Prints ``PASS: ...`` and exits 0
when the rule holds; otherwise lists each offending import and exits 1.
"""

import ast
import sys
from pathlib import Path

DOMAIN_PACKAGE = "invoice_intake.domain"
DEFAULT_ROOT = Path(__file__).resolve().parent.parent / "src" / "invoice_intake" / "domain"


def _allowed(module: str) -> bool:
    top = module.split(".")[0]
    in_domain = module == DOMAIN_PACKAGE or module.startswith(DOMAIN_PACKAGE + ".")
    return in_domain or top == "__future__" or top in sys.stdlib_module_names


def find_violations(root: Path) -> list[str]:
    """Return ``path:line: module`` for every import under ``root`` that breaks the rule."""
    violations: list[str] = []
    for path in sorted(root.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        depth = len(path.relative_to(root).parts) - 1
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                bad = [alias.name for alias in node.names if not _allowed(alias.name)]
            elif isinstance(node, ast.ImportFrom) and node.level == 0:
                bad = [] if _allowed(node.module or "") else [node.module or ""]
            elif isinstance(node, ast.ImportFrom):
                # A relative import is fine until it climbs out of the domain package.
                leaves = node.level > depth + 1
                bad = ["." * node.level + (node.module or "")] if leaves else []
            else:
                continue
            location = f"{path.relative_to(root).as_posix()}:{node.lineno}"
            violations.extend(f"{location}: {module}" for module in bad)
    return violations


def main(argv: list[str]) -> int:
    root = Path(argv[1]) if len(argv) > 1 else DEFAULT_ROOT
    violations = find_violations(root)
    if violations:
        print("Domain layer imports outside the standard library or its own package:")
        for violation in violations:
            print(f"  {violation}")
        return 1
    print(f"PASS: domain layer imports only the standard library and {DOMAIN_PACKAGE}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
