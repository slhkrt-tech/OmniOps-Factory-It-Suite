"""Değiştirilemez denetim izi yardımcıları."""
from inventory.models import ImmutableAuditEntry


def record_audit(action, resource_type, resource_id='', actor=None, request=None, payload=None):
    ip_address = None
    user_agent = ''
    if request is not None:
        ip_address = request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip() or request.META.get('REMOTE_ADDR')
        user_agent = (request.META.get('HTTP_USER_AGENT') or '')[:300]
    ImmutableAuditEntry.objects.create(
        actor=actor,
        action=action,
        resource_type=resource_type,
        resource_id=str(resource_id or ''),
        ip_address=ip_address or None,
        user_agent=user_agent,
        payload=payload or {},
    )
