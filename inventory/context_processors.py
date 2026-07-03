from django.conf import settings

from .workspace_service import get_workspace_context


def notification_context(request):
    from .models import Notification

    workspace = get_workspace_context(request.user, request)
    base = {
        'workspace': workspace,
        'feature_sales_kanban': workspace['features'].get('sales_kanban', getattr(settings, 'FEATURE_SALES_KANBAN', True)),
    }
    if request.user.is_authenticated:
        base['unread_notification_count'] = Notification.objects.filter(
            user=request.user, is_read=False
        ).count()
        return base
    base['unread_notification_count'] = 0
    return base
