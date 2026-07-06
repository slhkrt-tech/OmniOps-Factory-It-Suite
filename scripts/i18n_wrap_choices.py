"""Wrap Turkish model choice labels with gettext_lazy."""
from __future__ import annotations

import re
from pathlib import Path

MODELS = Path(__file__).resolve().parent.parent / "inventory" / "models.py"

CHOICE_LABELS = [
    "Sunucu", "Bilgisayar", "Diğer", "Açık", "Kapalı", "Inceleniyor", "İnceleniyor",
    "Cozuldu", "Çözüldü", "Kapali", "Orta", "Yuksek", "Yüksek", "Dusuk", "Düşük",
    "Acik", "Diger", "Kritik", "Yuksek Oncelik", "Dusuk Oncelik",
]


def main() -> None:
    content = MODELS.read_text(encoding="utf-8")
    updated = 0
    for label in CHOICE_LABELS:
        for pattern in [
            f", '{label}')",
            f', "{label}")',
        ]:
            wrapped = f", _('{label}'))" if "'" in pattern else f', _("{label}")'
            if pattern in content and wrapped not in content:
                count = content.count(pattern)
                content = content.replace(pattern, wrapped)
                updated += count
    # Generic fallback for remaining Turkish choice labels
    def repl(match: re.Match) -> str:
        label = match.group(1)
        if "_(" in match.group(0):
            return match.group(0)
        return f", _('{label}'))"

    content = re.sub(r", '([^']*[çğıöşüÇĞİÖŞÜ][^']*)'\)", repl, content)
    MODELS.write_text(content, encoding="utf-8")
    print(f"Updated {updated}+ choice labels")


if __name__ == "__main__":
    main()
