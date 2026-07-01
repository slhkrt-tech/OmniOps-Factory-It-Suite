"""Collabora Online WOPI entegrasyonu."""
import hashlib
import hmac
from urllib.parse import quote

from django.conf import settings


def collabora_enabled():
    return bool(getattr(settings, 'COLLABORA_SERVER_URL', ''))


def build_wopi_access_token(document_id, user_id):
    """Collabora WOPI erişim belirteci üretir."""
    payload = f'{document_id}:{user_id}'
    secret = getattr(settings, 'WOPI_SECRET', '') or getattr(settings, 'DJANGO_SECRET_KEY', '')
    return hmac.new(secret.encode('utf-8'), payload.encode('utf-8'), hashlib.sha256).hexdigest()


def verify_wopi_access_token(document_id, user_id, token):
    if not token:
        return False
    expected = build_wopi_access_token(document_id, user_id)
    return hmac.compare_digest(expected, token)


def build_wopi_src(request, document):
    """CheckFileInfo WOPI kaynak URL'sini oluşturur."""
    user_id = request.user.id
    token = build_wopi_access_token(document.pk, user_id)
    return request.build_absolute_uri(
        f'/wopi/files/{document.pk}?access_token={token}&access_token_ttl=0&access_token_uid={user_id}'
    )


def build_collabora_editor_url(request, document):
    """Collabora iframe URL'sini üretir."""
    if not collabora_enabled():
        return ''

    wopi_src = quote(build_wopi_src(request, document), safe='')
    base = getattr(settings, 'COLLABORA_SERVER_URL', '').rstrip('/')
    return f'{base}/browser/dist/cool.html?WOPISrc={wopi_src}&lang=tr'


def build_wopi_check_file_info(document, user):
    """WOPI CheckFileInfo JSON yanıtı."""
    filename = document.file.name.rsplit('/', 1)[-1] if document.file else f'{document.title}.docx'
    return {
        'BaseFileName': filename,
        'Size': document.file_size or (document.file.size if document.file else 0),
        'UserId': str(user.id),
        'UserFriendlyName': user.get_full_name() or user.username,
        'UserCanWrite': True,
        'UserCanNotWriteRelative': True,
        'SupportsUpdate': True,
        'SupportsLocks': False,
        'LastModifiedTime': document.updated_at.isoformat() if document.updated_at else '',
        'Version': str(document.version),
    }
