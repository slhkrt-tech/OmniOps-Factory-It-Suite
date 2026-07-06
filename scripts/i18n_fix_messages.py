"""Fix missing closing parens from i18n_wrap_code messages pass."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FILES = [
    ROOT / "inventory" / "views.py",
    ROOT / "inventory" / "enterprise_views.py",
    ROOT / "inventory" / "helpdesk_views.py",
]

PATTERN = re.compile(
    r"(messages\.(?:success|error|warning|info)\(\s*request,\s*_\((['\"])(?:\\.|(?!\2).)*\2\))(\s*)$",
    re.MULTILINE,
)


def fix_file(path: Path) -> int:
    content = path.read_text(encoding="utf-8")
    count = 0

    def repl(match: re.Match) -> str:
        nonlocal count
        if match.group(0).rstrip().endswith("))"):
            return match.group(0)
        count += 1
        return f"{match.group(1)}){match.group(3)}"

    new_content = PATTERN.sub(repl, content)
    if new_content != content:
        path.write_text(new_content, encoding="utf-8")
    return count


def main() -> None:
    for path in FILES:
        fixed = fix_file(path)
        print(f"{path.name}: fixed {fixed}")


if __name__ == "__main__":
    main()
