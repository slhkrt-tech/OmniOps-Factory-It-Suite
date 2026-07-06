from django.conf import settings
from django.utils.translation import gettext

from .i18n_js import get_omniops_i18n
from .workspace_service import get_workspace_context


def get_template_defaults() -> dict[str, str]:
    return {
        'overview': gettext('Genel Bakış'),
        'factory_inventory': gettext('Fabrika & Envanter'),
        'infrastructure': gettext('Altyapı'),
        'monitoring': gettext('Performans İzleme'),
        'independent': gettext('Bağımsız'),
        'unknown': gettext('Bilinmiyor'),
        'no_mac': gettext('MAC Yok'),
        'general_ticket': gettext('Genel / Bağımsız'),
        'not_specified': gettext('Belirtilmedi'),
        'hidden_key': gettext('Anahtar Gizli'),
        'system_author': gettext('Sistem'),
        'written_by': gettext('Yazan:'),
        'no_sync_yet': gettext('Henüz sync yapılmadı'),
        'no_sync': gettext('Henüz sync yok.'),
        'no_uri': gettext('URI yok'),
        'no_department': gettext('Departman yok'),
        'no_assignment': gettext('Zimmet yok'),
        'no_system_mapping': gettext('Sistem eşlemesi yok'),
        'external_service': gettext('Dış servis'),
        'no_location': gettext('Lokasyon yok'),
        'no_description': gettext('Açıklama girilmemiş.'),
        'no_reference': gettext('Referans yok'),
        'unlimited': gettext('Süresiz'),
        'overdue': gettext('gecikmiş'),
        'unassigned_ticket': gettext('Atanmadı'),
        'department': gettext('Bölüm'),
        'parent_independent': gettext('Bağımsız'),
        'created_at_label': gettext('Oluşturulma:'),
        'factory_portfolio_title': gettext('Fabrika Portföy Envanteri'),
    }


def notification_context(request):
    from .models import Notification

    workspace = get_workspace_context(request.user, request)
    base = {
        'workspace': workspace,
        'omniops_i18n': get_omniops_i18n(),
        'i18n_defaults': get_template_defaults(),
        'feature_sales_kanban': workspace['features'].get('sales_kanban', getattr(settings, 'FEATURE_SALES_KANBAN', True)),
    }
    if request.user.is_authenticated:
        base['unread_notification_count'] = Notification.objects.filter(
            user=request.user, is_read=False
        ).count()
        return base
    base['unread_notification_count'] = 0
    return base
