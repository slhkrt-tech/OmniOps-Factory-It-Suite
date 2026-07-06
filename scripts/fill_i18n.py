"""Fill PO files safely using polib, cached EN translations, and manual overrides."""
from __future__ import annotations

import html
import json
import re
from pathlib import Path

import polib

BASE = Path(__file__).resolve().parent.parent / "locale"
CACHE_FILE = BASE / "en_translations.json"
OVERRIDES_FILE = BASE / "en_manual_overrides.json"

try:
    from deep_translator import MyMemoryTranslator
except ImportError:
    MyMemoryTranslator = None

CORRUPT_RE = re.compile(r"<g\s+id=|&#10;|&#09;")


def load_cache() -> dict[str, str]:
    cache = {}
    if CACHE_FILE.exists():
        cache.update(json.loads(CACHE_FILE.read_text(encoding="utf-8")))
    if OVERRIDES_FILE.exists():
        cache.update(json.loads(OVERRIDES_FILE.read_text(encoding="utf-8")))
    return cache


def save_cache(cache: dict[str, str]) -> None:
    overrides = {}
    if OVERRIDES_FILE.exists():
        overrides = json.loads(OVERRIDES_FILE.read_text(encoding="utf-8"))
    persist = {key: value for key, value in cache.items() if key not in overrides}
    CACHE_FILE.write_text(json.dumps(persist, ensure_ascii=False, indent=2), encoding="utf-8")


def sanitize_translation(msgid: str, value: str) -> str:
    cleaned = html.unescape((value or "").strip())
    if not cleaned or CORRUPT_RE.search(cleaned):
        return msgid
    if cleaned == msgid and msgid.isascii():
        return msgid
    return cleaned


def translate_missing(msgids: list[str], cache: dict[str, str]) -> None:
    pending = [m for m in msgids if m and m not in cache]
    if not pending or not MyMemoryTranslator:
        for msgid in pending:
            cache.setdefault(msgid, msgid)
        return
    translator = MyMemoryTranslator(source="tr-TR", target="en-GB")
    batch_size = 20
    for i in range(0, len(pending), batch_size):
        chunk = pending[i:i + batch_size]
        try:
            results = translator.translate_batch(chunk)
            for src, dst in zip(chunk, results):
                cache[src] = sanitize_translation(src, dst or src)
        except Exception:
            for src in chunk:
                try:
                    cache[src] = sanitize_translation(src, translator.translate(src))
                except Exception:
                    cache[src] = src
        save_cache(cache)
        print(f"Translated {min(i + batch_size, len(pending))}/{len(pending)}")


def fill_po(path: Path, *, locale: str, cache: dict[str, str]) -> int:
    po = polib.pofile(str(path))
    updated = 0
    for entry in po:
        if not entry.msgid:
            continue
        if locale == "tr":
            target = "İngilizce" if entry.msgid == "English" else entry.msgid
        else:
            target = sanitize_translation(entry.msgid, cache.get(entry.msgid, entry.msgstr or entry.msgid))
        if entry.fuzzy:
            entry.flags.remove("fuzzy")
        if entry.msgstr != target:
            entry.msgstr = target
            updated += 1
    po.metadata["Language"] = locale
    po.save(str(path))
    return updated


def main() -> None:
    en_path = BASE / "en" / "LC_MESSAGES" / "django.po"
    tr_path = BASE / "tr" / "LC_MESSAGES" / "django.po"
    cache = load_cache()
    if en_path.exists():
        po = polib.pofile(str(en_path))
        msgids = [e.msgid for e in po if e.msgid]
        missing = [m for m in msgids if m not in cache]
        print(f"Missing translations: {len(missing)}")
        if missing:
            translate_missing(missing, cache)
            save_cache(cache)
    tr_count = fill_po(tr_path, locale="tr", cache=cache)
    en_count = fill_po(en_path, locale="en", cache=cache)
    print(f"Updated {en_count} EN, {tr_count} TR; cache={len(cache)}")


if __name__ == "__main__":
    main()
