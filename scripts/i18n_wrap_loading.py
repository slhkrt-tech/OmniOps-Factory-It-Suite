"""Wrap showGlobalLoading string literals with Django {% trans %} tags."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "inventory" / "templates"
PATTERN = re.compile(
    r"showGlobalLoading\((['\"])([^'\"]+)\1,\s*(['\"])([^'\"]+)\3\)"
)


def wrap_file(path: Path) -> int:
    text = path.read_text(encoding="utf-8")
    count = 0

    def repl(match: re.Match[str]) -> str:
        nonlocal count
        btn_id = match.group(2)
        msg = match.group(4)
        if "{% trans" in msg:
            return match.group(0)
        count += 1
        return "showGlobalLoading('" + btn_id + "', '{% trans \"" + msg + "\" %}')"

    updated = PATTERN.sub(repl, text)
    if count:
        path.write_text(updated, encoding="utf-8")
    return count


def main() -> None:
    total = 0
    for path in ROOT.rglob("*.html"):
        changed = wrap_file(path)
        if changed:
            print(f"{path.name}: {changed}")
            total += changed
    print(f"Wrapped {total} showGlobalLoading calls")


if __name__ == "__main__":
    main()
