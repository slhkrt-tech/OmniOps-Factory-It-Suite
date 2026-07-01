"""Belge editörü backend seçimi (OnlyOffice / Collabora)."""
import json

from django.conf import settings

from .collabora import build_collabora_editor_url, collabora_enabled
from .onlyoffice import build_onlyoffice_editor_config, get_onlyoffice_script_url, onlyoffice_enabled


def get_document_editor_backend():
    """Aktif belge editörü backend'ini döndürür."""
    preferred = getattr(settings, 'DOCUMENT_EDITOR_BACKEND', 'auto').lower()
    if preferred == 'onlyoffice' and onlyoffice_enabled():
        return 'onlyoffice'
    if preferred == 'collabora' and collabora_enabled():
        return 'collabora'
    if preferred == 'auto':
        if onlyoffice_enabled():
            return 'onlyoffice'
        if collabora_enabled():
            return 'collabora'
    return None


def build_document_editor_context(document, request, mode='edit'):
    """Seçili backend için editör şablon context'i üretir."""
    backend = get_document_editor_backend()
    if backend == 'onlyoffice':
        payload = build_onlyoffice_editor_config(document, request, mode=mode)
        if not payload:
            return None
        return {
            'backend': 'onlyoffice',
            'editor_payload_json': json.dumps(payload),
            'onlyoffice_script_url': get_onlyoffice_script_url(),
            'collabora_editor_url': '',
        }
    if backend == 'collabora':
        url = build_collabora_editor_url(request, document)
        if not url:
            return None
        return {
            'backend': 'collabora',
            'editor_payload_json': '{}',
            'onlyoffice_script_url': '',
            'collabora_editor_url': url,
        }
    return None
