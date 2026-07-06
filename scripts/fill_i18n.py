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
FORMAT_RE = re.compile(r"%\(\w+\)[a-zA-Z%]")
BROKEN_FORMAT_RE = re.compile(r"%\s+\(")
TURKISH_RE = re.compile(r"[çğıöşüÇĞİÖŞÜ]|(?:^|\s)(?:ve|için|ile|olan|yok|tüm|yeni|kaydet|panel|talep|cihaz|fabrika|merkezi|envanter|sistem|rapor|doküman|onay|açık|kapalı|inceleniyor|çözüldü|güncelle|sil|ekle|yönetim|destek|kullanıcı|henüz|bağlantı|işlem|güvenlik|denetim|varlık|problem|süreç)(?:\s|$)", re.I)


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


def is_probably_turkish(text: str) -> bool:
    text = (text or "").strip()
    if not text:
        return False
    if TURKISH_RE.search(text):
        return True
    return False


def is_bad_english(msgid: str, value: str) -> bool:
    if not msgid:
        return False
    cleaned = (value or "").strip()
    if not cleaned or CORRUPT_RE.search(cleaned):
        return True
    if cleaned == msgid.strip() and is_probably_turkish(msgid):
        return True
    if is_probably_turkish(cleaned) and is_probably_turkish(msgid) and cleaned == msgid:
        return True
    return False


def restore_format_placeholders(msgid: str, value: str) -> str:
    """Keep python-format placeholders intact when machine translation breaks them."""
    if not msgid or not value:
        return value
    placeholders = FORMAT_RE.findall(msgid)
    if not placeholders:
        return value
    if BROKEN_FORMAT_RE.search(value) or not all(p in value for p in placeholders):
        restored = value
        for placeholder in placeholders:
            broken = placeholder.replace("(", " (")
            restored = restored.replace(broken, placeholder)
            if placeholder not in restored:
                restored = msgid if is_probably_turkish(msgid) else value
                break
        return restored
    return value


def sanitize_translation(msgid: str, value: str) -> str:
    cleaned = html.unescape((value or "").strip())
    if not cleaned or CORRUPT_RE.search(cleaned):
        return msgid
    cleaned = restore_format_placeholders(msgid, cleaned)
    if cleaned == msgid and not is_probably_turkish(msgid):
        return msgid
    if is_bad_english(msgid, cleaned):
        return msgid
    return cleaned


def translate_missing(msgids: list[str], cache: dict[str, str]) -> None:
    pending = [m for m in msgids if m and (m not in cache or is_bad_english(m, cache.get(m, m)))]
    if not pending:
        return
    if not MyMemoryTranslator:
        for msgid in pending:
            if is_bad_english(msgid, cache.get(msgid, msgid)):
                cache[msgid] = msgid
        return
    translator = MyMemoryTranslator(source="tr-TR", target="en-GB")
    batch_size = 20
    for i in range(0, len(pending), batch_size):
        chunk = pending[i:i + batch_size]
        try:
            results = translator.translate_batch(chunk)
            for src, dst in zip(chunk, results):
                translated = sanitize_translation(src, dst or src)
                if is_bad_english(src, translated):
                    try:
                        translated = sanitize_translation(src, translator.translate(src))
                    except Exception:
                        translated = src
                cache[src] = translated
        except Exception:
            for src in chunk:
                try:
                    cache[src] = sanitize_translation(src, translator.translate(src))
                except Exception:
                    cache[src] = src
        save_cache(cache)
        print(f"Translated {min(i + batch_size, len(pending))}/{len(pending)}")


def collect_stale_msgids(po: polib.POFile, cache: dict[str, str]) -> list[str]:
    stale = []
    for entry in po:
        if not entry.msgid:
            continue
        cached = cache.get(entry.msgid, entry.msgstr or "")
        if is_bad_english(entry.msgid, entry.msgstr or cached):
            stale.append(entry.msgid)
    return stale


def fill_po(path: Path, *, locale: str, cache: dict[str, str]) -> int:
    po = polib.pofile(str(path))
    updated = 0
    for entry in po:
        if not entry.msgid:
            continue
        if locale == "tr":
            target = "İngilizce" if entry.msgid == "English" else entry.msgid
        else:
            raw = cache.get(entry.msgid, entry.msgstr or entry.msgid)
            target = sanitize_translation(entry.msgid, raw)
            if is_bad_english(entry.msgid, target):
                target = cache.get(entry.msgid, entry.msgid)
                if is_bad_english(entry.msgid, target):
                    target = entry.msgid
        if entry.fuzzy and "fuzzy" in entry.flags:
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
        stale = collect_stale_msgids(po, cache)
        print(f"Stale/bad EN translations: {len(stale)}")
        if stale:
            translate_missing(stale, cache)
            save_cache(cache)
        missing = [e.msgid for e in po if e.msgid and e.msgid not in cache]
        print(f"Missing from cache: {len(missing)}")
        if missing:
            translate_missing(missing, cache)
            save_cache(cache)
    tr_count = fill_po(tr_path, locale="tr", cache=cache)
    en_count = fill_po(en_path, locale="en", cache=cache)
    print(f"Updated {en_count} EN, {tr_count} TR; cache={len(cache)}")


if __name__ == "__main__":
    main()
