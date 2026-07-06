"""Wrap user-facing Python strings with Django gettext markers."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

MODELS_PATH = ROOT / "inventory" / "models.py"
FORMS_PATH = ROOT / "inventory" / "forms.py"
VIEW_FILES = [
    ROOT / "inventory" / "views.py",
    ROOT / "inventory" / "enterprise_views.py",
    ROOT / "inventory" / "helpdesk_views.py",
]


def ensure_import(content: str, lazy: bool = True) -> str:
    import_line = (
        "from django.utils.translation import gettext_lazy as _\n"
        if lazy
        else "from django.utils.translation import gettext as _\n"
    )
    if "gettext_lazy as _" in content or "gettext as _" in content:
        return content
    lines = content.splitlines(keepends=True)
    insert_at = 0
    for i, line in enumerate(lines):
        if line.startswith("from ") or line.startswith("import "):
            insert_at = i + 1
    lines.insert(insert_at, import_line)
    return "".join(lines)


def wrap_verbose_names(content: str) -> str:
    content = ensure_import(content, lazy=True)
    patterns = [
        (r'verbose_name="([^"]+)"', r'verbose_name=_("\1")'),
        (r"verbose_name='([^']+)'", r"verbose_name=_('\1')"),
        (r'verbose_name_plural="([^"]+)"', r'verbose_name_plural=_("\1")'),
        (r"verbose_name_plural='([^']+)'", r"verbose_name_plural=_('\1')"),
        (r'help_text="([^"]+)"', r'help_text=_("\1")'),
        (r"help_text='([^']+)'", r"help_text=_('\1')"),
    ]
    for pattern, repl in patterns:
        content = re.sub(pattern, lambda m: repl.replace("\\1", m.group(1)) if False else re.sub(pattern, repl, m.group(0)), content)
    for pattern, repl in patterns:
        content = re.sub(pattern, repl, content)
    return content


def wrap_choice_labels(content: str) -> str:
    """Wrap Turkish choice display values in tuples like ('key', 'Türkçe')."""
    def replacer(match: re.Match) -> str:
        val = match.group(1)
        if re.search(r"[çğıöşüÇĞİÖŞÜ]", val) or val in {
            "Sunucu", "Bilgisayar", "Diğer", "Açık", "Kapalı", "Orta", "Yüksek", "Düşük",
            "Acik", "Inceleniyor", "Cozuldu", "Kapali",
        }:
            return f"(_('{val}'))"
        return match.group(0)

    content = re.sub(r",\s*'([^']*[çğıöşüÇĞİÖŞÜA-Za-z][^']*)'\)", replacer, content)
    content = re.sub(r",\s*\"([^\"]*[çğıöşüÇĞİÖŞÜA-Za-z][^\"]*)\"\)", replacer, content)
    return content


def wrap_form_placeholders(content: str) -> str:
    content = ensure_import(content, lazy=True)

    def wrap_attr(match: re.Match) -> str:
        key, val = match.group(1), match.group(2)
        if val.startswith("_(") or not re.search(r"[çğıöşüÇĞİÖŞÜ]", val):
            return match.group(0)
        return f"'{key}': forms.TextInput(attrs={{'class': 'form-control', 'placeholder': _('{val}')}})"

    content = re.sub(
        r"'placeholder':\s*'([^']*[çğıöşüÇĞİÖŞÜ][^']*)'",
        lambda m: f"'placeholder': _('{m.group(1)}')",
        content,
    )
    content = re.sub(
        r"'placeholder':\s*\"([^\"]*[çğıöşüÇĞİÖŞÜ][^\"]*)\"",
        lambda m: f"'placeholder': _(\"{m.group(1)}\")",
        content,
    )
    content = re.sub(
        r"label='([^']*[çğıöşüÇĞİÖŞÜ][^']*)'",
        lambda m: f"label=_('{m.group(1)}')",
        content,
    )
    content = re.sub(
        r'label="([^"]*[çğıöşüÇĞİÖŞÜ][^"]*)"',
        lambda m: f'label=_("{m.group(1)}")',
        content,
    )
    content = re.sub(
        r"ValidationError\('([^']*[çğıöşüÇĞİÖŞÜ][^']*)'\)",
        lambda m: f"ValidationError(_('{m.group(1)}'))",
        content,
    )
    content = re.sub(
        r'ValidationError\("([^"]*[çğıöşüÇĞİÖŞÜ][^"]*)"\)',
        lambda m: f'ValidationError(_("{m.group(1)}"))',
        content,
    )
    return content


def wrap_messages(content: str) -> str:
    content = ensure_import(content, lazy=False)

    def wrap_string_literal(match: re.Match) -> str:
        prefix, quote, text = match.group(1), match.group(2), match.group(3)
        if "_(" in prefix or text.startswith("_("):
            return match.group(0)
        if not re.search(r"[çğıöşüÇĞİÖŞÜ]", text) and not any(
            w in text for w in ("success", "error", "failed", "created", "updated")
        ):
            # Still wrap common Turkish words without special chars
            turkish_words = (
                "basari", "basar", "kayit", "talep", "cihaz", "kullanici",
                "yetki", "erisim", "onay", "red", "tamamlandi", "olusturuldu",
            )
            lower = text.lower()
            if not any(w in lower for w in turkish_words) and "ITIL" not in text and "✅" not in text:
                if not re.search(r"[çğıöşüÇĞİÖŞÜ]", text):
                    pass
        if "_(" in text:
            return match.group(0)
        if "{" in text and "}" in text:
            return f"{prefix}_({quote}{text}{quote})"
        return f"{prefix}_({quote}{text}{quote})"

    content = re.sub(
        r"(messages\.(?:success|error|warning|info)\([^,]+,\s*)(['\"])(.+?)\2\)",
        wrap_string_literal,
        content,
        flags=re.DOTALL,
    )
    return content


def main() -> None:
    models = MODELS_PATH.read_text(encoding="utf-8")
    if "gettext_lazy as _" not in models:
        models = models.replace(
            "from django.db import models\n",
            "from django.db import models\nfrom django.utils.translation import gettext_lazy as _\n",
        )
    models = wrap_verbose_names(models)
    MODELS_PATH.write_text(models, encoding="utf-8")
    print("Updated models.py")

    forms = FORMS_PATH.read_text(encoding="utf-8")
    forms = wrap_form_placeholders(forms)
    FORMS_PATH.write_text(forms, encoding="utf-8")
    print("Updated forms.py")

    for path in VIEW_FILES:
        content = path.read_text(encoding="utf-8")
        content = wrap_messages(content)
        path.write_text(content, encoding="utf-8")
        print(f"Updated {path.name}")


if __name__ == "__main__":
    main()
