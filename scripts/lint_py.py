#!/usr/bin/env python3
"""AST-based Python linter for Build Forge repository.

Checks:
1. Calls to strip, lstrip, or rstrip with a string literal of 2 or more characters fail,
   unless every character is whitespace or the line contains '# strip-chars-ok: <reason>'.
2. Calls to Path.glob or obj.glob with a pattern starting with './' fail.
"""
import ast
from pathlib import Path
import sys

sys.dont_write_bytecode = True

IGNORE_DIRS = {
    ".git",
    "node_modules",
    ".venv",
    "venv",
    "__pycache__",
    "dist",
    "build",
}


def check_source(source_text: str, filename: str = "<string>") -> list:
    errors = []
    lines = source_text.splitlines()
    try:
        tree = ast.parse(source_text, filename=filename)
    except SyntaxError as e:
        return [f"{filename}:{e.lineno}: SyntaxError: {e.msg}"]

    for node in ast.walk(tree):
        # Check strip / lstrip / rstrip
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr in ("strip", "lstrip", "rstrip") and node.args:
                first_arg = node.args[0]
                if isinstance(first_arg, ast.Constant) and isinstance(first_arg.value, str):
                    val = first_arg.value
                    if len(val) >= 2:
                        # Allow if all characters are whitespace
                        if not all(c.isspace() for c in val):
                            lineno = node.lineno
                            line_content = lines[lineno - 1] if 0 <= lineno - 1 < len(lines) else ""
                            if "# strip-chars-ok:" not in line_content:
                                errors.append(
                                    f"{filename}:{lineno}: {node.func.attr}(\"{repr(val)[1:-1]}\") "
                                    f"uses multi-character strip without '# strip-chars-ok: <reason>'"
                                )

            # Check Path.glob / obj.glob / rglob
            if node.func.attr in ("glob", "rglob") and node.args:
                first_arg = node.args[0]
                if isinstance(first_arg, ast.Constant) and isinstance(first_arg.value, str):
                    val = first_arg.value
                    if val.startswith("./"):
                        lineno = node.lineno
                        errors.append(
                            f"{filename}:{lineno}: {node.func.attr}(\"{repr(val)[1:-1]}\") "
                            f"pattern starts with './' which fails in Path.glob"
                        )

    return errors


def check_file(path: Path) -> list:
    try:
        content = path.read_text(encoding="utf-8")
    except Exception as e:
        return [f"{path}: failed to read: {e}"]
    return check_source(content, filename=str(path))


def find_py_files(root: Path) -> list:
    files = []
    for p in root.rglob("*.py"):
        parts = p.relative_to(root).parts
        if any(d in IGNORE_DIRS for d in parts):
            continue
        files.append(p)
    return sorted(files)


def main():
    root = Path(__file__).resolve().parent.parent
    targets = [Path(a).resolve() for a in sys.argv[1:]] if len(sys.argv) > 1 else find_py_files(root)

    all_errors = []
    for target in targets:
        if target.is_dir():
            for pf in find_py_files(target):
                all_errors.extend(check_file(pf))
        elif target.is_file():
            all_errors.extend(check_file(target))

    if all_errors:
        for err in all_errors:
            print(f"ERROR: {err}")
        print(f"\n{len(all_errors)} Python AST lint error(s) found.")
        sys.exit(1)
    else:
        print("OK: Python AST lint checks passed.")
        sys.exit(0)


if __name__ == "__main__":
    main()
