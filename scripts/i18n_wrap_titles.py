"""Wrap static {% block title %} strings with {% trans %}."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "inventory" / "templates"
TITLE_RE = re.compile(r"(\{% block title %\})([^{%]+?)(\{% endblock %\})")


def wrap_file(path: Path) -> int:
    text = path.read_text(encoding="utf-8")
    count = 0

    def repl(match: re.Match[str]) -> str:
        nonlocal count
        inner = match.group(2).strip()
        if "{% trans" in inner or "{{" in inner:
            return match.group(0)
        if not inner or inner == "OmniOps":
            return match.group(0)
        count += 1
        escaped = inner.replace('"', '\\"')
        return match.group(1) + '{% trans "' + escaped + '" %}' + match.group(3)

    updated = TITLE_RE.sub(repl, text)
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
    print(f"Wrapped {total} titles")


if __name__ == "__main__":
    main()
