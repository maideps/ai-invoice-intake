"""Architecture rules for imports between backend layers.

- arch-007, layer ``domain``: imports only the standard library and the domain package itself.
- arch-008, layers ``api`` and ``services``: never import ``infrastructure`` (or the composition
  root, ``main``); ``services`` also never imports ``api``.

Run from ``backend/``: ``python tools/check_layer_imports.py domain`` (or ``api services``).
Prints ``PASS: ...`` and exits 0 when the rules hold; otherwise lists each offending import.
"""

import ast
import sys
from collections.abc import Iterator
from pathlib import Path

PACKAGE = "invoice_intake"
PACKAGE_ROOT = Path(__file__).resolve().parent.parent / "src" / PACKAGE

# Layers and the parts of the package each one must not import.
FORBIDDEN: dict[str, tuple[str, ...]] = {
    "api": ("infrastructure", "main"),
    "services": ("infrastructure", "main", "api"),
}
LAYERS = ("domain", *FORBIDDEN)


def _module_name(path: Path, package_root: Path) -> str:
    parts = path.relative_to(package_root.parent).with_suffix("").parts
    return ".".join(parts[:-1] if parts[-1] == "__init__" else parts)


def _imports(path: Path, package_root: Path) -> Iterator[tuple[int, str]]:
    """Every imported name as an absolute dotted path, with its line number.

    ``from a import b`` yields ``a.b``, so ``from invoice_intake import infrastructure`` is
    caught as well as ``import invoice_intake.infrastructure``.
    """
    module = _module_name(path, package_root)
    package = (module if path.name == "__init__.py" else module.rsplit(".", 1)[0]).split(".")
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            yield from ((node.lineno, alias.name) for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0:
                base = node.module or ""
            elif node.level - 1 >= len(package):
                yield node.lineno, "." * node.level + (node.module or "")  # escapes the package
                continue
            else:
                anchor = package[: len(package) - (node.level - 1)]
                base = ".".join([*anchor, *([node.module] if node.module else [])])
            yield from ((node.lineno, f"{base}.{alias.name}") for alias in node.names)


def _within(module: str, prefix: str) -> bool:
    return module == prefix or module.startswith(prefix + ".")


def _breaks(layer: str, module: str) -> bool:
    if layer == "domain":
        top = module.split(".")[0]
        allowed = top == "__future__" or (top in sys.stdlib_module_names and top != PACKAGE)
        return not (allowed or _within(module, f"{PACKAGE}.domain"))
    if module.startswith("."):
        return True
    return any(_within(module, f"{PACKAGE}.{part}") for part in FORBIDDEN[layer])


def find_violations(layer: str, package_root: Path = PACKAGE_ROOT) -> list[str]:
    """Return ``path:line: module`` for every import in ``layer`` that breaks its rule."""
    violations: list[str] = []
    for path in sorted((package_root / layer).rglob("*.py")):
        location = path.relative_to(package_root).as_posix()
        for line, module in _imports(path, package_root):
            if _breaks(layer, module):
                violations.append(f"{location}:{line}: {module}")
    return violations


def main(argv: list[str], package_root: Path = PACKAGE_ROOT) -> int:
    layers = argv[1:]
    unknown = [layer for layer in layers if layer not in LAYERS]
    if not layers or unknown:
        print(f"usage: check_layer_imports.py LAYER... (layers: {', '.join(LAYERS)})")
        return 2
    violations = [v for layer in layers for v in find_violations(layer, package_root)]
    if violations:
        print("Imports that break the layer rules:")
        for violation in violations:
            print(f"  {violation}")
        return 1
    print(f"PASS: layer imports follow the rules for {', '.join(layers)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
