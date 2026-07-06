"""Find template lines with Turkish chars not wrapped in trans tags."""
from __future__ import annotations

import re
from pathlib import Path

TR = re.compile(r"[çğıöşüÇĞİÖŞÜ]")
SKIP = re.compile(
    r"(\{%\s*trans|\{%\s*blocktrans|#\:|msgid|\.po|\.json|style=|data-icon|iconify|escapejs|json_script|//|/\*)"
)
ROOT = Path(__file__).resolve().parent.parent / "inventory" / "templates"


def main() -> None:
    issues: list[str] = []
    for path in sorted(ROOT.rglob("*.html")):
        for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not TR.search(line):
                continue
            if SKIP.search(line):
                continue
            if "{% trans" in line or "{% blocktrans" in line:
                continue
            stripped = line.strip()
            if not stripped or stripped.startswith("<!--"):
                continue
            issues.append(f"{path.as_posix()}:{i}: {stripped[:120]}")
    print(f"Found {len(issues)} lines")
    for row in issues[:60]:
        print(row)


if __name__ == "__main__":
    main()
