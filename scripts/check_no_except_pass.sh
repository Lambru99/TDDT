#!/usr/bin/env bash
# Fail if any Python file in tddt/ swallows exceptions silently
# (either `except X: pass` on one line, or `except X:` with only `pass` as body).
set -eu

# Resolve repo root as the parent of this script's directory.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

python3 - "$REPO_ROOT" <<'EOF'
import ast
import pathlib
import sys

repo_root = pathlib.Path(sys.argv[1])
root = repo_root / "tddt"
if not root.is_dir():
    print(f"ERROR: {root} does not exist", file=sys.stderr)
    sys.exit(2)

bad: list[str] = []
total = 0
for py in root.rglob("*.py"):
    total += 1
    try:
        tree = ast.parse(py.read_text(encoding="utf-8"))
    except SyntaxError as exc:
        print(f"warn: cannot parse {py}: {exc}", file=sys.stderr)
        continue
    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler):
            if len(node.body) == 1 and isinstance(node.body[0], ast.Pass):
                rel = py.relative_to(repo_root)
                bad.append(f"{rel}:{node.lineno}: except ... pass (silent swallow)")

if bad:
    print("Guard failed: silent exception swallowing is forbidden.")
    print("Use log.exception() or log.warning(..., exc_info=True) instead.\n")
    for line in bad:
        print(f"  {line}")
    sys.exit(1)

print(f"OK: scanned {total} .py files, no silent swallow.")
EOF
