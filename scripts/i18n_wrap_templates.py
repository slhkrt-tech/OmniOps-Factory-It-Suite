"""Add i18n load tags and wrap visible Turkish template text with {% trans %}."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = ROOT / "inventory" / "templates"

SKIP_TAGS = {"script", "style", "code", "pre", "textarea"}
SKIP_PATTERNS = (
    re.compile(r"\{%\s*trans\b"),
    re.compile(r"\{%\s*blocktrans\b"),
    re.compile(r"\{\{"),
    re.compile(r"\{%"),
    re.compile(r"^\s*//"),
    re.compile(r"data-icon="),
    re.compile(r"class="),
    re.compile(r"https?://"),
    re.compile(r"^\s*$"),
)

TURKISH_RE = re.compile(r"[çğıöşüÇĞİÖŞÜ]|(?:^|\s)(?:ve|için|ile|olan|yok|tüm|yeni|kaydet|sil|ekle|güncelle|panel|talep|cihaz|kullanıcı|fabrika|merkezi|envanter|sistem|rapor|doküman|onay|red|açık|kapalı|inceleniyor|çözüldü)(?:\s|$)", re.I)


def should_translate(text: str) -> bool:
    text = text.strip()
    if len(text) < 2 or len(text) > 200:
        return False
    if not TURKISH_RE.search(text):
        return False
    for pat in SKIP_PATTERNS:
        if pat.search(text):
            return False
    if text.startswith("mdi:") or text.startswith("OmniOps"):
        return False
    return True


def ensure_i18n_load(content: str) -> str:
    if "{% load i18n %}" in content:
        return content
    if "{% extends" in content:
        return re.sub(
            r"(\{% extends [^%]+%\}\n)",
            r"\1{% load i18n %}\n",
            content,
            count=1,
        )
    if "<!DOCTYPE" in content or "<html" in content:
        return re.sub(
            r"(\{% load static %\}\n)",
            r"\1{% load i18n %}\n",
            content,
            count=1,
        )
    return "{% load i18n %}\n" + content


def wrap_line_text(line: str) -> str:
    if "{% trans" in line or "{{" in line or ("{%" in line and "end" not in line.lower()):
        pass
    else:
        stripped = line.strip()
        if stripped and not stripped.startswith("<") and not stripped.startswith("{") and should_translate(stripped):
            indent = line[: len(line) - len(line.lstrip())]
            return f'{indent}{{% trans "{stripped.replace(chr(34), chr(92)+chr(34))}" %}}\n'

    if "{% trans" in line:
        return line

    def repl(match: re.Match) -> str:
        before, text, after = match.group(1), match.group(2), match.group(3)
        if not should_translate(text.strip()):
            return match.group(0)
        escaped = text.strip().replace('"', '\\"')
        return f'{before}{{% trans "{escaped}" %}}{after}'

    line = re.sub(r"(>)([^<{}]+?)(<)", repl, line)
    return line


def process_file(path: Path) -> int:
    original = path.read_text(encoding="utf-8")
    content = ensure_i18n_load(original)
    lines = content.splitlines(keepends=True)
    new_lines = []
    in_skip = False
    changed = 0
    for line in lines:
        tag_open = re.search(r"<(script|style)\b", line, re.I)
        tag_close = re.search(r"</(script|style)>", line, re.I)
        if tag_open:
            in_skip = True
        new_line = line if in_skip else wrap_line_text(line)
        if new_line != line:
            changed += 1
        new_lines.append(new_line)
        if tag_close:
            in_skip = False
    new_content = "".join(new_lines)
    if new_content != original:
        path.write_text(new_content, encoding="utf-8")
    return changed


def main() -> None:
    total = 0
    for path in sorted(TEMPLATES_DIR.rglob("*.html")):
        count = process_file(path)
        if count:
            print(f"{path.relative_to(ROOT)}: {count} lines")
            total += count
    print(f"Total line changes: {total}")


if __name__ == "__main__":
    main()
