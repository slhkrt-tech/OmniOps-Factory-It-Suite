"""Fix broken trans tags from auto-wrap script."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "inventory" / "templates"


def fix_file(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    original = text
    text = re.sub(r'\{% trans \\"([^\\"]+)\\" %\}', r"{% trans '\1' %}", text)
    text = text.replace(
        '{% trans "placeholder=\\"192.168.1.0/24\\" required" %}',
        'placeholder="192.168.1.0/24" required',
    )
    text = text.replace(
        '{% trans "placeholder=\\"26\\" required min=\\"1\\" max=\\"32\\"" %}',
        'placeholder="26" required min="1" max="32"',
    )
    if text != original:
        path.write_text(text, encoding="utf-8")
        return True
    return False


def main() -> None:
    count = 0
    for path in ROOT.rglob("*.html"):
        if fix_file(path):
            print(path.relative_to(ROOT))
            count += 1
    print(f"Fixed {count} files")


if __name__ == "__main__":
    main()
