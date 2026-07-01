def notification_context(request):
    from django.conf import settings
    if request.user.is_authenticated:
        from .models import Notification
        return {
            'unread_notification_count': Notification.objects.filter(
                user=request.user, is_read=False
            ).count(),
            'feature_sales_kanban': getattr(settings, 'FEATURE_SALES_KANBAN', True),
        }
    return {
        'unread_notification_count': 0,
        'feature_sales_kanban': getattr(settings, 'FEATURE_SALES_KANBAN', True),
    }
