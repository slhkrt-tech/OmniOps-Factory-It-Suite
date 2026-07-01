"""Servis masası yardımcı modülü: RBAC, otomatik atama, bildirimler ve analitik."""
from django.contrib.auth.models import Group, User
from django.db.models import Count, Q
from django.utils import timezone

ROLE_ADMIN = 'Admin'
ROLE_SUPPORT = 'Destek Personeli'
ROLE_CUSTOMER = 'Müşteri'

SUPPORT_GROUP_NAMES = [
    'Destek Personeli', 'Help Desk Ekibi', 'Ağ Ekibi', 'Sistem Ekibi', 'Yönetim', 'Admin',
]

CATEGORY_SLUG_MAP = {
    'donanim': 'Donanim',
    'yazilim': 'Yazilim',
    'ag': 'Ag',
    'diger': 'Diger',
}


def ensure_default_groups():
    """Varsayılan rol gruplarını oluşturur."""
    for group_name in [
        ROLE_ADMIN,
        ROLE_SUPPORT,
        ROLE_CUSTOMER,
        'Help Desk Ekibi',
        'Ağ Ekibi',
        'Sistem Ekibi',
        'Yönetim',
    ]:
        Group.objects.get_or_create(name=group_name)


def ensure_default_permissions():
    """Sidebar ve Guardian kullanan modüller için grup izinlerini hazırlar."""
    from django.contrib.auth.models import Permission

    ensure_default_groups()
    permission_map = {
        ROLE_ADMIN: Permission.objects.all(),
        'Yönetim': Permission.objects.all(),
        ROLE_SUPPORT: Permission.objects.filter(codename__in=[
            'view_ticket', 'add_ticket', 'change_ticket',
            'view_ticketcomment', 'add_ticketcomment', 'change_ticketcomment',
            'view_ticketattachment', 'add_ticketattachment',
            'view_notification', 'change_notification',
            'view_device', 'view_ipaddress',
        ]),
        'Help Desk Ekibi': Permission.objects.filter(codename__in=[
            'view_ticket', 'add_ticket', 'change_ticket',
            'view_ticketcomment', 'add_ticketcomment',
            'view_ticketattachment', 'add_ticketattachment',
            'view_notification', 'change_notification',
        ]),
        'Ağ Ekibi': Permission.objects.filter(codename__in=[
            'view_device', 'add_device', 'change_device',
            'view_ipaddress', 'add_ipaddress', 'change_ipaddress',
            'view_networkscan', 'add_networkscan',
            'view_port', 'add_port', 'change_port',
            'view_devicebackup', 'add_devicebackup',
            'view_ticket', 'add_ticket', 'change_ticket',
        ]),
        'Sistem Ekibi': Permission.objects.filter(codename__in=[
            'view_itasset', 'add_itasset', 'change_itasset',
            'view_license', 'add_license', 'change_license',
            'view_vendorcontract', 'add_vendorcontract', 'change_vendorcontract',
            'view_device', 'view_systemlog',
            'view_ticket', 'add_ticket', 'change_ticket',
        ]),
        ROLE_CUSTOMER: Permission.objects.filter(codename__in=[
            'view_ticket', 'add_ticket',
            'view_ticketcomment', 'add_ticketcomment',
            'view_ticketattachment', 'add_ticketattachment',
        ]),
    }
    for group_name, permissions in permission_map.items():
        group = Group.objects.get(name=group_name)
        group.permissions.add(*permissions)


def ensure_default_categories():
    """Varsayılan talep kategorilerini oluşturur."""
    from .models import TicketCategory

    defaults = [
        ('Donanım', 'donanim', 'mdi:desktop-classic', 24, 'Destek Personeli'),
        ('Yazılım', 'yazilim', 'mdi:application-outline', 24, 'Destek Personeli'),
        ('Ağ', 'ag', 'mdi:lan-connect', 8, 'Ağ Ekibi'),
        ('Diğer', 'diger', 'mdi:dots-horizontal', 48, 'Help Desk Ekibi'),
    ]
    for name, slug, icon, sla_hours, group_name in defaults:
        group = Group.objects.filter(name=group_name).first()
        TicketCategory.objects.get_or_create(
            slug=slug,
            defaults={
                'name': name,
                'icon': icon,
                'sla_hours': sla_hours,
                'auto_assign_group': group,
                'is_active': True,
            },
        )


def user_has_role(user, role_name):
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    if role_name == ROLE_ADMIN:
        return user.is_staff and user.groups.filter(name=ROLE_ADMIN).exists()
    if role_name == ROLE_SUPPORT:
        return user.is_staff or user.groups.filter(name__in=SUPPORT_GROUP_NAMES).exists()
    if role_name == ROLE_CUSTOMER:
        return not user.is_staff
    return user.groups.filter(name=role_name).exists()


def is_support_staff(user):
    return user.is_authenticated and (user.is_staff or user.groups.filter(name__in=SUPPORT_GROUP_NAMES).exists())


def can_access_ticket(user, ticket):
    if not user.is_authenticated:
        return False
    if user.is_superuser or user.is_staff:
        return True
    if ticket.created_by_id == user.id:
        return True
    if ticket.assigned_to_id == user.id:
        return True
    return False


def get_least_loaded_agent(group):
    """Gruptaki en az yüklü destek personelini döndürür."""
    if not group:
        return None
    agents = User.objects.filter(groups=group, is_active=True).annotate(
        open_tickets=Count('assigned_tickets', filter=Q(assigned_tickets__status__in=['Acik', 'Inceleniyor']))
    ).order_by('open_tickets', 'id')
    return agents.first()


def auto_assign_ticket(ticket):
    """Talebi kategoriye göre otomatik atar."""
    if ticket.assigned_to_id:
        return ticket.assigned_to

    group = None
    if ticket.ticket_category and ticket.ticket_category.auto_assign_group:
        group = ticket.ticket_category.auto_assign_group
    else:
        group = Group.objects.filter(name__in=['Help Desk Ekibi', 'Destek Personeli']).first()

    agent = get_least_loaded_agent(group)
    if agent:
        ticket.assigned_to = agent
        ticket.save(update_fields=['assigned_to', 'updated_at'])
        notify_user(
            agent,
            f'Yeni talep atandı: #{ticket.id}',
            ticket.title,
            link=f'/talep/{ticket.id}/',
            notification_type='assignment',
            ticket=ticket,
        )
    return agent


def notify_user(user, title, message, link='', notification_type='info', ticket=None):
    """Uygulama içi bildirim oluşturur."""
    from .models import Notification

    if not user:
        return None
    return Notification.objects.create(
        user=user,
        title=title,
        message=message,
        link=link,
        notification_type=notification_type,
        ticket=ticket,
    )


def notify_ticket_event(ticket, event_type, actor=None):
    """Talep olaylarında ilgili kullanıcılara bildirim gönderir."""
    recipients = set()
    if ticket.created_by:
        recipients.add(ticket.created_by)
    if ticket.assigned_to:
        recipients.add(ticket.assigned_to)
    if actor:
        recipients.discard(actor)

    messages = {
        'comment': ('Yeni yorum', f'#{ticket.id} talebine yeni bir yorum eklendi.'),
        'status': ('Durum güncellendi', f'#{ticket.id} talebinin durumu: {ticket.status}'),
        'closed': ('Talep kapatıldı', f'#{ticket.id} talebi kapatıldı.'),
        'sla_breach': ('SLA ihlali', f'#{ticket.id} talebi SLA süresini aştı!'),
    }
    title, msg = messages.get(event_type, ('Talep güncellendi', ticket.title))
    link = f'/talep/{ticket.id}/'

    for user in recipients:
        notify_user(user, title, msg, link=link, notification_type=event_type, ticket=ticket)

    try:
        from .notification_dispatcher import broadcast_event
        broadcast_event(
            'sla' if event_type == 'sla_breach' else 'ticket',
            title,
            msg,
            factory_site=getattr(ticket, 'factory_site', None),
            payload={'ticket_id': ticket.pk, 'event_type': event_type},
        )
    except Exception:
        pass


def get_helpdesk_analytics():
    """Yönetici paneli için talep analitik verilerini döndürür."""
    from .models import Ticket

    now = timezone.now()
    week_ago = now - timezone.timedelta(days=7)

    open_statuses = ['Acik', 'Inceleniyor']
    tickets = Ticket.objects.all()
    open_tickets = tickets.filter(status__in=open_statuses)

    sla_breached = open_tickets.exclude(sla_deadline__isnull=True).filter(sla_deadline__lt=now).count()
    escalated = open_tickets.filter(is_escalated=True).count()

    by_category = list(
        tickets.values('category').annotate(count=Count('id')).order_by('-count')
    )
    by_priority = list(tickets.values('priority').annotate(count=Count('id')))
    by_status = list(tickets.values('status').annotate(count=Count('id')))

    agent_workload = list(
        User.objects.filter(assigned_tickets__status__in=open_statuses)
        .annotate(open_count=Count('assigned_tickets'))
        .values('id', 'username', 'first_name', 'last_name', 'open_count')
        .order_by('-open_count')[:10]
    )

    resolved = tickets.filter(status__in=['Cozuldu', 'Kapatildi'], closed_at__isnull=False)
    avg_resolution_hours = None
    if resolved.exists():
        total_seconds = sum(
            (t.closed_at - t.created_at).total_seconds()
            for t in resolved.select_related('created_by')[:500]
            if t.closed_at and t.created_at
        )
        if total_seconds:
            avg_resolution_hours = round(total_seconds / resolved.count() / 3600, 1)

    created_this_week = tickets.filter(created_at__gte=week_ago).count()
    closed_this_week = tickets.filter(closed_at__gte=week_ago).count()

    from django.db.models import F

    sla_compliance = 100.0
    closed_with_sla = tickets.filter(closed_at__isnull=False).exclude(sla_deadline__isnull=True)
    if closed_with_sla.exists():
        on_time = closed_with_sla.filter(closed_at__lte=F('sla_deadline')).count()
        sla_compliance = round(on_time / closed_with_sla.count() * 100, 1)

    return {
        'total': tickets.count(),
        'open': open_tickets.count(),
        'sla_breached': sla_breached,
        'escalated': escalated,
        'by_category': by_category,
        'by_priority': by_priority,
        'by_status': by_status,
        'agent_workload': agent_workload,
        'avg_resolution_hours': avg_resolution_hours,
        'created_this_week': created_this_week,
        'closed_this_week': closed_this_week,
        'sla_compliance': sla_compliance,
    }


def assign_customer_role(user):
    """Yeni kayıt olan kullanıcıya Müşteri rolü atar."""
    ensure_default_groups()
    customer_group = Group.objects.get(name=ROLE_CUSTOMER)
    user.groups.add(customer_group)
