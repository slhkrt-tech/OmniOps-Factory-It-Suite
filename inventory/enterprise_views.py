import json
import io
import os
from datetime import timedelta
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.contrib import messages
from django.conf import settings
from django.contrib.auth.models import User, Group
from django.http import HttpResponse, JsonResponse, FileResponse
from django.core.files.base import ContentFile
from django.contrib.staticfiles import finders
from django.contrib.staticfiles.storage import staticfiles_storage
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.db import connection, models
from django.db.models import Count
from django.urls import reverse
from django.utils import timezone

from .helpdesk import is_support_staff
from .site_access import (
    filter_queryset_by_site, get_accessible_sites, resolve_site_for_user,
    user_can_access_site, user_has_global_site_access, user_has_module_permission,
)
from .forms import (
    FactoryAreaForm, ConsumableItemForm,
    MaintenanceTaskForm, EmployeeITProcessForm,
    ProcurementRequestForm, OnCallShiftForm, BackupJobMonitorForm,
    VendorSupportCaseForm, AssetHandoverForm, MajorIncidentForm,
    AccessRequestForm, PrinterFleetItemForm, RunbookForm,
    RemoteAccessGrantForm, DepartmentChannelForm, DepartmentMessageForm,
    CameraDeviceForm, BusinessApplicationForm, ReportTemplateForm,
    ChangeCalendarEventForm, ServiceDependencyForm, IntegrationHealthCheckForm,
    ComplianceControlForm, DocumentOutputJobForm,
    DirectoryConnectionForm, DirectoryGroupForm, DirectoryUserForm,
    EndpointDeviceForm, IdentityLifecycleTaskForm,
    FactoryDepartmentForm, FactoryZoneForm, ManagedDocumentForm, FactoryITAssetRelationForm,
    FactorySiteForm, DepartmentInventoryItemForm,
    UserFactorySiteAccessForm, OTConnectionForm,
    AssetQRTagForm, ERPConnectionForm,
    ProblemRecordForm, ReleaseRecordForm, AssetLifecycleEventForm,
    NotificationChannelForm, MonitoringConnectionForm, VMSConnectionForm,
    EmailTicketInboxForm, BackupVendorConnectionForm, WMSConnectionForm,
    ModulePermissionGrantForm,
)
from .models import (
    FieldVisit, SalesOpportunity, Ticket, DLPEvent, Device, ITAsset, License,
    TicketCategory,
    FactoryArea, ConsumableItem, MaintenanceTask, EmployeeITProcess,
    ProcurementRequest, OnCallShift, BackupJobMonitor, VendorSupportCase, AssetHandover,
    MajorIncident, AccessRequest, PrinterFleetItem, Runbook,
    RemoteAccessGrant, DepartmentChannel, DepartmentMessage, CameraDevice,
    BusinessApplication, ReportTemplate,
    ChangeCalendarEvent, ServiceDependency, IntegrationHealthCheck,
    ComplianceControl, DocumentOutputJob,
    DirectoryConnection, DirectoryGroup, DirectoryUser, EndpointDevice,
    IdentityLifecycleTask, SystemLog,
    FactoryDepartment, FactoryZone, ManagedDocument, FactoryITAssetRelation,
    FactorySite, DepartmentInventoryItem,
    UserFactorySiteAccess,
    AssetQRTag, ERPConnection, OTConnection,
    ProblemRecord, ReleaseRecord, NotificationChannel, MonitoringConnection,
    VMSConnection, EmailTicketInbox, ImmutableAuditEntry, AssetLifecycleEvent,
    BackupVendorConnection, WMSConnection, ModulePermissionGrant,
)


def _parse_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _parse_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _parse_optional_float(value):
    if value in (None, ''):
        return None
    return _parse_float(value, None)


def health_check(request):
    """Yük dengeleyici ve Docker sağlık kontrolü için hafif durum uç noktası."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception as exc:
        return JsonResponse({'status': 'error', 'database': str(exc)}, status=503)
    return JsonResponse({'status': 'ok'})


def _readiness_item(key, title, ok, detail='', action='', severity='success'):
    return {
        'key': key,
        'title': title,
        'ok': bool(ok),
        'detail': detail,
        'action': action,
        'severity': severity if ok else 'danger',
    }


def build_readiness_report():
    """İlk kurulum ve canlı kullanım için ürün hazır olma raporu."""
    checks = []
    db_ok = True
    db_detail = 'Veritabanı bağlantısı çalışıyor.'
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception as exc:
        db_ok = False
        db_detail = str(exc)

    required_groups = ['Admin', 'Yönetim', 'Ağ Ekibi', 'Sistem Ekibi', 'Help Desk Ekibi']
    existing_groups = set(Group.objects.filter(name__in=required_groups).values_list('name', flat=True))
    missing_groups = [name for name in required_groups if name not in existing_groups]

    media_root = getattr(settings, 'MEDIA_ROOT', '')
    log_dir = getattr(settings, 'LOG_DIR', os.path.join(settings.BASE_DIR, 'logs'))

    checks.extend([
        _readiness_item('database', 'Veritabanı', db_ok, db_detail, 'DATABASE_URL ve migration durumunu kontrol edin.'),
        _readiness_item('admin', 'Admin Kullanıcı', User.objects.filter(is_superuser=True).exists(), 'En az bir superuser bulunmalı.', 'python manage.py createsuperuser'),
        _readiness_item('groups', 'Rol Grupları', not missing_groups, 'Eksik grup: ' + ', '.join(missing_groups) if missing_groups else 'Temel RBAC grupları hazır.', 'python manage.py setup_helpdesk'),
        _readiness_item('ticket_categories', 'Ticket Kategorileri', TicketCategory.objects.exists(), 'Varsayılan destek kategorileri hazır olmalı.', 'python manage.py setup_helpdesk'),
        _readiness_item('secret_key', 'Gizli Anahtar', bool(getattr(settings, 'SECRET_KEY', '')) and 'change-me' not in settings.SECRET_KEY.lower(), 'DJANGO_SECRET_KEY canlı ortamda benzersiz olmalı.', '.env içinden DJANGO_SECRET_KEY değerini değiştirin.'),
        _readiness_item('allowed_hosts', 'Allowed Hosts', bool(getattr(settings, 'ALLOWED_HOSTS', [])), ', '.join(getattr(settings, 'ALLOWED_HOSTS', [])) or 'Boş', 'ALLOWED_HOSTS canlı domainleri içermeli.'),
        _readiness_item('remote_secret', 'Remote Probe Secret', bool(getattr(settings, 'REMOTE_PROBE_SHARED_SECRET', '')), 'Uzak ajan senkronizasyon şifresi.', 'REMOTE_PROBE_SHARED_SECRET ayarlayın.'),
        _readiness_item('media_root', 'Media Dizini', bool(media_root) and os.path.isdir(media_root), str(media_root), 'media klasörünü oluşturup yazılabilir yapın.'),
        _readiness_item('logs', 'Log Dizini', bool(log_dir) and os.path.isdir(log_dir), str(log_dir), 'logs klasörünü oluşturup kalıcı volume bağlayın.'),
        _readiness_item('email', 'E-posta Ayarı', bool(getattr(settings, 'EMAIL_HOST', '')), getattr(settings, 'EMAIL_HOST', '') or 'Tanımlı değil', 'SMTP bilgilerini .env içine ekleyin.', 'warning'),
        _readiness_item('sso', 'SSO Hazırlığı', any([
            bool(getattr(settings, 'SOCIAL_AUTH_AZUREAD_OAUTH2_KEY', '')),
            bool(getattr(settings, 'SOCIAL_AUTH_OIDC_KEY', '')),
            bool(getattr(settings, 'SAML_ENABLED', False)),
        ]), 'Azure AD/OIDC/SAML opsiyonel.', 'Kurumsal giriş isteniyorsa SSO bilgilerini girin.', 'warning'),
        _readiness_item('celery', 'Celery/Redis Ayarı', bool(getattr(settings, 'CELERY_BROKER_URL', '')), getattr(settings, 'CELERY_BROKER_URL', ''), 'Redis ve Celery worker/beat servislerini çalıştırın.'),
        _readiness_item('factory_departments', 'Fabrika Kartelası', FactoryDepartment.objects.filter(is_active=True).exists(), 'Departman kartelası boş.', 'python manage.py omniops_doctor --bootstrap', 'warning'),
        _readiness_item('factory_sites', 'Fabrika Portföyü', FactorySite.objects.filter(is_active=True).exists(), 'Tesis/portföy kaydı yok.', 'python manage.py omniops_doctor --bootstrap', 'warning'),
        _readiness_item('department_inventory', 'Bölüm Envanteri', DepartmentInventoryItem.objects.filter(is_active=True).exists(), 'Bölüm envanter kaydı yok.', '/fabrika-portfoy-envanter/ veya bootstrap', 'warning'),
        _readiness_item('managed_documents', 'Doküman Merkezi', ManagedDocument.objects.exists(), 'Henüz yönetilen doküman yok.', 'Fabrika BT Komuta Merkezi üzerinden PDF/DOCX yükleyin.', 'warning'),
        _readiness_item('qr_tags', 'QR/Barkod Etiketleri', AssetQRTag.objects.filter(is_active=True).exists(), 'Varlık QR etiketi tanımlı değil.', 'python manage.py omniops_doctor --bootstrap veya /varlik-qr-tara/', 'warning'),
        _readiness_item(
            'onlyoffice',
            'OnlyOffice Editör',
            bool(getattr(settings, 'ONLYOFFICE_DOCUMENT_SERVER_URL', '')),
            getattr(settings, 'ONLYOFFICE_DOCUMENT_SERVER_URL', '') or 'ONLYOFFICE_DOCUMENT_SERVER_URL tanımlı değil.',
            'Tarayıcı editörü için OnlyOffice sunucu URL ve isteğe bağlı JWT ayarlayın.',
            'warning',
        ),
        _readiness_item(
            'collabora',
            'Collabora Editör',
            bool(getattr(settings, 'COLLABORA_SERVER_URL', '')),
            getattr(settings, 'COLLABORA_SERVER_URL', '') or 'COLLABORA_SERVER_URL tanımlı değil.',
            'Alternatif editör için Collabora CODE URL ayarlayın.',
            'warning',
        ),
    ])

    module_status = [
        {'title': 'Cihaz', 'count': Device.objects.count(), 'url': '/topoloji/'},
        {'title': 'Ticket', 'count': Ticket.objects.count(), 'url': '/panel/'},
        {'title': 'BT Varlık', 'count': ITAsset.objects.count(), 'url': '/it-envanter/'},
        {'title': 'Lisans', 'count': License.objects.count(), 'url': '/it-envanter/'},
        {'title': 'Fabrika Alanı', 'count': FactoryArea.objects.count(), 'url': '/fabrika-operasyonlari/'},
        {'title': 'Kamera', 'count': CameraDevice.objects.count(), 'url': '/komuta-merkezi/'},
        {'title': 'İş Uygulaması', 'count': BusinessApplication.objects.count(), 'url': '/komuta-merkezi/'},
        {'title': 'Runbook', 'count': Runbook.objects.count(), 'url': '/servis-surecleri/'},
        {'title': 'Rapor Şablonu', 'count': ReportTemplate.objects.count(), 'url': '/komuta-merkezi/'},
        {'title': 'Directory Kullanıcısı', 'count': DirectoryUser.objects.count(), 'url': '/kimlik-operasyonlari/'},
        {'title': 'Endpoint Cihazı', 'count': EndpointDevice.objects.count(), 'url': '/kimlik-operasyonlari/'},
        {'title': 'Fabrika Tesisi', 'count': FactorySite.objects.filter(is_active=True).count(), 'url': '/fabrika-portfoy-envanter/'},
        {'title': 'Bölüm Envanteri', 'count': DepartmentInventoryItem.objects.filter(is_active=True).count(), 'url': '/fabrika-portfoy-envanter/'},
        {'title': 'Fabrika Departmanı', 'count': FactoryDepartment.objects.filter(is_active=True).count(), 'url': '/fabrika-komuta-merkezi/'},
        {'title': 'Yönetilen Doküman', 'count': ManagedDocument.objects.count(), 'url': '/fabrika-komuta-merkezi/'},
        {'title': 'QR Etiket', 'count': AssetQRTag.objects.filter(is_active=True).count(), 'url': '/varlik-qr-tara/'},
        {'title': 'ERP Bağlantısı', 'count': ERPConnection.objects.count(), 'url': '/erp-entegrasyonlari/'},
        {'title': 'Entegrasyon Merkezi', 'count': MonitoringConnection.objects.count(), 'url': '/entegrasyon-merkezi/'},
        {'title': 'ITSM Problem', 'count': ProblemRecord.objects.count(), 'url': '/itsm-olgunluk/'},
    ]

    critical_total = len([item for item in checks if item['severity'] == 'danger'])
    warning_total = len([item for item in checks if item['severity'] == 'warning' and not item['ok']])
    ok_total = len([item for item in checks if item['ok']])
    score = int((ok_total / len(checks)) * 100) if checks else 0

    return {
        'score': score,
        'critical_total': critical_total,
        'warning_total': warning_total,
        'ok_total': ok_total,
        'checks': checks,
        'module_status': module_status,
        'quick_start': [
            {'title': '1. Rolleri ve kategorileri hazırla', 'command': 'python manage.py setup_helpdesk'},
            {'title': '2. Admin oluştur', 'command': 'python manage.py createsuperuser'},
            {'title': '3. Veritabanını güncelle', 'command': 'python manage.py migrate'},
            {'title': '4. Fabrika kartelasını hazırla', 'command': 'python manage.py omniops_doctor --bootstrap'},
            {'title': '5. Üretim servislerini başlat', 'command': 'docker compose up --build -d'},
            {'title': '6. Sağlık kontrolü', 'command': 'curl http://127.0.0.1:8000/health/'},
            {'title': '7. Fabrika BT Komuta Merkezi', 'command': 'http://127.0.0.1:8000/fabrika-komuta-merkezi/'},
        ],
    }


def run_directory_sync(connection, actor=None, dry_run=None):
    """Directory senkronizasyonu — LDAP/AD/Azure AD veya manuel snapshot."""
    from .integrations.directory_sync import run_directory_sync as execute_directory_sync
    return execute_directory_sync(connection, actor=actor, dry_run=dry_run)


@login_required
def setup_center_view(request):
    if not is_support_staff(request.user):
        return redirect('dashboard')
    return render(request, 'setup_center.html', build_readiness_report())


@login_required
def readiness_api(request):
    if not is_support_staff(request.user):
        return JsonResponse({'status': 'error', 'message': 'Unauthorized'}, status=403)
    return JsonResponse(build_readiness_report())


@login_required
def identity_operations_view(request):
    if not is_support_staff(request.user):
        return redirect('dashboard')

    forms = {
        'connection': DirectoryConnectionForm(),
        'group': DirectoryGroupForm(),
        'user': DirectoryUserForm(),
        'endpoint': EndpointDeviceForm(),
        'lifecycle': IdentityLifecycleTaskForm(),
        'site_access': UserFactorySiteAccessForm(),
    }

    if request.method == 'POST':
        action = request.POST.get('action')
        form_map = {
            'connection': DirectoryConnectionForm,
            'group': DirectoryGroupForm,
            'user': DirectoryUserForm,
            'endpoint': EndpointDeviceForm,
            'lifecycle': IdentityLifecycleTaskForm,
            'site_access': UserFactorySiteAccessForm,
        }
        form_class = form_map.get(action)
        if form_class:
            form = form_class(request.POST)
            if form.is_valid():
                obj = form.save(commit=False)
                if action == 'lifecycle':
                    obj.requested_by = request.user
                if action == 'site_access':
                    if not user_has_global_site_access(request.user):
                        messages.error(request, 'Tesis erişim yetkisi yalnızca global yöneticiler tarafından atanabilir.')
                        return redirect('identity_operations')
                    obj.granted_by = request.user
                obj.save()
                if hasattr(form, 'save_m2m'):
                    form.save_m2m()
                messages.success(request, "Kimlik merkezi kaydı oluşturuldu.")
                return redirect('identity_operations')
            forms[action] = form
        elif action == 'sync_directory':
            connection = DirectoryConnection.objects.filter(pk=request.POST.get('connection_id')).first()
            ok, message = run_directory_sync(connection, actor=request.user)
            if ok:
                messages.success(request, message)
            else:
                messages.warning(request, message)
            return redirect('identity_operations')
        elif action == 'mark_endpoint_compliant':
            endpoint = EndpointDevice.objects.filter(pk=request.POST.get('endpoint_id')).first()
            if endpoint:
                endpoint.status = 'compliant'
                endpoint.antivirus_ok = True
                endpoint.disk_encrypted = True
                endpoint.last_seen_at = timezone.now()
                endpoint.save(update_fields=['status', 'antivirus_ok', 'disk_encrypted', 'last_seen_at', 'updated_at'])
                messages.success(request, f"Endpoint uyumlu işaretlendi: {endpoint.hostname}")
                return redirect('identity_operations')
        elif action == 'mark_lifecycle_done':
            task = IdentityLifecycleTask.objects.filter(pk=request.POST.get('task_id')).first()
            if task:
                task.status = 'done'
                task.ad_account_done = True
                task.mailbox_done = True
                task.groups_done = True
                task.endpoint_done = True
                task.vpn_done = True
                task.save(update_fields=[
                    'status', 'ad_account_done', 'mailbox_done', 'groups_done',
                    'endpoint_done', 'vpn_done', 'updated_at',
                ])
                messages.success(request, f"Kimlik işi tamamlandı: {task.title}")
                return redirect('identity_operations')
        elif action == 'run_lifecycle_automation':
            task = IdentityLifecycleTask.objects.filter(pk=request.POST.get('task_id')).first()
            if task:
                from .integrations.ad_lifecycle import ADLifecycleError, run_identity_lifecycle_task
                try:
                    _, message = run_identity_lifecycle_task(task, actor=request.user)
                    messages.success(request, message)
                except ADLifecycleError as exc:
                    messages.error(request, str(exc))
                return redirect('identity_operations')

    connections = DirectoryConnection.objects.select_related('owner').order_by('name')
    directory_users = DirectoryUser.objects.select_related('connection', 'user').prefetch_related('groups').order_by('status', 'username')
    attention_users = [user for user in directory_users[:200] if user.needs_attention]
    endpoints = EndpointDevice.objects.select_related('asset', 'assigned_user', 'factory_area').order_by('status', 'hostname')
    endpoint_alerts = [endpoint for endpoint in endpoints[:200] if not endpoint.is_compliant or endpoint.is_stale]
    lifecycle_tasks = IdentityLifecycleTask.objects.select_related('directory_user', 'requested_by', 'assigned_to').exclude(status__in=['done', 'cancelled']).order_by('due_date', '-created_at')
    privileged_groups = DirectoryGroup.objects.filter(is_privileged=True).select_related('connection', 'owner').order_by('risk_level', 'name')
    site_access_rows = UserFactorySiteAccess.objects.select_related('user', 'factory_site', 'granted_by').order_by('factory_site__title', 'user__username')[:50]

    context = {
        'forms': forms,
        'connections': connections[:12],
        'attention_users': attention_users[:20],
        'endpoint_alerts': endpoint_alerts[:20],
        'lifecycle_tasks': lifecycle_tasks[:20],
        'privileged_groups': privileged_groups[:20],
        'site_access_rows': site_access_rows,
        'can_manage_site_access': user_has_global_site_access(request.user),
        'metrics': {
            'connections': connections.count(),
            'directory_users': DirectoryUser.objects.count(),
            'attention_users': len(attention_users),
            'endpoint_alerts': len(endpoint_alerts),
            'lifecycle_tasks': lifecycle_tasks.count(),
            'privileged_groups': privileged_groups.count(),
            'site_access_grants': UserFactorySiteAccess.objects.filter(is_active=True).count(),
        },
    }
    return render(request, 'identity_operations.html', context)


@login_required
def field_routes_view(request):
    if not is_support_staff(request.user):
        return redirect('dashboard')

    if request.method == 'POST':
        visit = FieldVisit.objects.create(
            title=request.POST.get('title') or 'Saha Ziyareti',
            customer_name=request.POST.get('customer_name') or 'Müşteri',
            address=request.POST.get('address', ''),
            latitude=_parse_optional_float(request.POST.get('latitude')),
            longitude=_parse_optional_float(request.POST.get('longitude')),
            distance_km=_parse_float(request.POST.get('distance_km'), 0),
            vehicle_model=request.POST.get('vehicle_model') or 'Standart Servis Aracı',
            fuel_l_per_100km=_parse_float(request.POST.get('fuel_l_per_100km'), 7.5),
            ac_multiplier=_parse_float(request.POST.get('ac_multiplier'), 1.08),
            technician_id=request.POST.get('technician') or request.user.id,
            ticket_id=request.POST.get('ticket') or None,
        )
        messages.success(request, f"Rota durağı eklendi: {visit.title}")
        return redirect('field_routes')

    visits = FieldVisit.objects.select_related('technician', 'ticket').order_by('order_index', 'id')
    route_points = [
        {
            'id': visit.id,
            'title': visit.title,
            'customer': visit.customer_name,
            'lat': visit.latitude,
            'lng': visit.longitude,
            'fuel': visit.estimated_fuel_l,
            'distance': visit.distance_km,
        }
        for visit in visits if visit.latitude is not None and visit.longitude is not None
    ]
    return render(request, 'field_routes.html', {
        'visits': visits,
        'route_points_json': json.dumps(route_points),
        'technicians': User.objects.filter(is_active=True).order_by('username'),
        'tickets': Ticket.objects.filter(status__in=['Acik', 'Inceleniyor']).order_by('-created_at')[:100],
    })


@login_required
def sales_kanban_view(request):
    if not getattr(settings, 'FEATURE_SALES_KANBAN', True):
        return redirect('dashboard')
    if not is_support_staff(request.user):
        return redirect('dashboard')

    if request.method == 'POST':
        SalesOpportunity.objects.create(
            title=request.POST.get('title') or 'Yeni Fırsat',
            customer_name=request.POST.get('customer_name') or 'Müşteri',
            potential_revenue=_parse_float(request.POST.get('potential_revenue'), 0),
            probability=_parse_int(request.POST.get('probability'), 20),
            owner=request.user,
            notes=request.POST.get('notes', ''),
        )
        messages.success(request, "Satış fırsatı eklendi.")
        return redirect('sales_kanban')

    stages = []
    for value, label in SalesOpportunity.STAGE_CHOICES:
        opportunities = SalesOpportunity.objects.filter(stage=value).select_related('owner').order_by('position', '-updated_at')
        total = sum(item.weighted_revenue for item in opportunities)
        stages.append({
            'value': value,
            'label': label,
            'items': opportunities,
            'weighted_total': total,
        })
    return render(request, 'sales_kanban.html', {'stages': stages})


@login_required
def offline_field_app(request):
    if not is_support_staff(request.user):
        return redirect('user_panel')
    return render(request, 'offline_field_app.html')


def service_worker_js(request):
    source_path = finders.find('js/service-worker.js')
    if source_path:
        with open(source_path, 'r', encoding='utf-8') as handle:
            return HttpResponse(handle.read(), content_type='application/javascript')
    with staticfiles_storage.open('js/service-worker.js', 'r') as handle:
        return HttpResponse(handle.read(), content_type='application/javascript')


@login_required
def factory_operations_view(request):
    if not is_support_staff(request.user):
        return redirect('dashboard')

    forms = {
        'area': FactoryAreaForm(),
        'consumable': ConsumableItemForm(),
        'maintenance': MaintenanceTaskForm(),
        'employee_process': EmployeeITProcessForm(),
    }

    if request.method == 'POST':
        action = request.POST.get('action')
        form_map = {
            'area': FactoryAreaForm,
            'consumable': ConsumableItemForm,
            'maintenance': MaintenanceTaskForm,
            'employee_process': EmployeeITProcessForm,
        }
        form_class = form_map.get(action)
        if form_class:
            form = form_class(request.POST)
            if form.is_valid():
                obj = form.save(commit=False)
                if action == 'employee_process':
                    obj.requester = request.user
                obj.save()
                messages.success(request, "Fabrika IT operasyon kaydı oluşturuldu.")
                return redirect('factory_operations')
            forms[action] = form
        elif action == 'mark_maintenance_done':
            task = MaintenanceTask.objects.filter(pk=request.POST.get('task_id')).first()
            if task:
                task.mark_done()
                messages.success(request, f"Bakım tamamlandı: {task.title}")
                return redirect('factory_operations')
        elif action == 'close_employee_process':
            process = EmployeeITProcess.objects.filter(pk=request.POST.get('process_id')).first()
            if process:
                process.status = 'done'
                process.save(update_fields=['status', 'updated_at'])
                messages.success(request, f"Personel IT süreci tamamlandı: {process.employee_name}")
                return redirect('factory_operations')

    now = timezone.now()
    today = now.date()
    low_stock = ConsumableItem.objects.filter(quantity__lte=models.F('minimum_quantity')).order_by('quantity', 'name')
    due_tasks = MaintenanceTask.objects.select_related('factory_area', 'owner').exclude(status='done').filter(next_due_at__lte=now + timedelta(days=7))
    open_processes = EmployeeITProcess.objects.select_related('factory_area', 'assigned_to').exclude(status__in=['done', 'cancelled'])

    context = {
        'forms': forms,
        'areas': FactoryArea.objects.all()[:50],
        'consumables': ConsumableItem.objects.all()[:100],
        'low_stock': low_stock[:20],
        'maintenance_tasks': MaintenanceTask.objects.select_related('factory_area', 'owner').order_by('next_due_at')[:100],
        'due_tasks': due_tasks[:20],
        'employee_processes': open_processes[:100],
        'overdue_processes_count': open_processes.filter(due_date__lt=today).count(),
        'metrics': {
            'areas': FactoryArea.objects.count(),
            'low_stock': low_stock.count(),
            'due_tasks': due_tasks.count(),
            'open_processes': open_processes.count(),
        },
    }
    return render(request, 'factory_operations.html', context)


@login_required
def it_operations_view(request):
    if not is_support_staff(request.user):
        return redirect('dashboard')

    forms = {
        'procurement': ProcurementRequestForm(),
        'oncall': OnCallShiftForm(),
        'backup': BackupJobMonitorForm(),
        'vendor_case': VendorSupportCaseForm(),
        'handover': AssetHandoverForm(),
    }

    if request.method == 'POST':
        action = request.POST.get('action')
        form_map = {
            'procurement': ProcurementRequestForm,
            'oncall': OnCallShiftForm,
            'backup': BackupJobMonitorForm,
            'vendor_case': VendorSupportCaseForm,
            'handover': AssetHandoverForm,
        }
        form_class = form_map.get(action)
        if form_class:
            form = form_class(request.POST)
            if form.is_valid():
                obj = form.save(commit=False)
                if action == 'procurement':
                    obj.requester = request.user
                elif action == 'handover':
                    obj.performed_by = request.user
                obj.save()
                messages.success(request, "IT operasyon kaydı oluşturuldu.")
                return redirect('it_operations')
            forms[action] = form
        elif action == 'approve_procurement':
            procurement = ProcurementRequest.objects.filter(pk=request.POST.get('procurement_id')).first()
            if procurement:
                procurement.status = 'approved'
                procurement.approved_by = request.user
                procurement.save(update_fields=['status', 'approved_by', 'updated_at'])
                messages.success(request, f"Satın alma talebi onaylandı: {procurement.title}")
                return redirect('it_operations')
        elif action == 'resolve_vendor_case':
            case = VendorSupportCase.objects.filter(pk=request.POST.get('case_id')).first()
            if case:
                case.status = 'resolved'
                case.resolved_at = timezone.now()
                case.save(update_fields=['status', 'resolved_at', 'updated_at'])
                messages.success(request, f"Tedarikçi vakası çözüldü: {case.title}")
                return redirect('it_operations')
        elif action == 'mark_backup_success':
            job = BackupJobMonitor.objects.filter(pk=request.POST.get('job_id')).first()
            if job:
                job.last_status = 'success'
                job.last_run_at = timezone.now()
                job.save(update_fields=['last_status', 'last_run_at', 'updated_at'])
                messages.success(request, f"Yedekleme başarılı işaretlendi: {job.name}")
                return redirect('it_operations')

    now = timezone.now()
    active_oncall = OnCallShift.objects.filter(start_at__lte=now, end_at__gte=now).select_related('engineer')
    unhealthy_backups = BackupJobMonitor.objects.filter(is_active=True, last_status__in=['failed', 'missed', 'warning'])
    pending_procurements = ProcurementRequest.objects.filter(status='pending').select_related('requester')
    open_vendor_cases = VendorSupportCase.objects.exclude(status__in=['resolved', 'closed']).select_related('assigned_to')

    context = {
        'forms': forms,
        'active_oncall': active_oncall,
        'pending_procurements': pending_procurements[:20],
        'unhealthy_backups': unhealthy_backups[:20],
        'open_vendor_cases': open_vendor_cases[:20],
        'recent_handovers': AssetHandover.objects.select_related('asset', 'performed_by').order_by('-handover_date')[:20],
        'metrics': {
            'pending_procurements': pending_procurements.count(),
            'active_oncall': active_oncall.count(),
            'unhealthy_backups': unhealthy_backups.count(),
            'open_vendor_cases': open_vendor_cases.count(),
        },
    }
    return render(request, 'it_operations.html', context)


@login_required
def service_operations_view(request):
    if not is_support_staff(request.user):
        return redirect('dashboard')

    forms = {
        'incident': MajorIncidentForm(),
        'access': AccessRequestForm(),
        'printer': PrinterFleetItemForm(),
        'runbook': RunbookForm(),
    }

    if request.method == 'POST':
        action = request.POST.get('action')
        form_map = {
            'incident': MajorIncidentForm,
            'access': AccessRequestForm,
            'printer': PrinterFleetItemForm,
            'runbook': RunbookForm,
        }
        form_class = form_map.get(action)
        if form_class:
            form = form_class(request.POST)
            if form.is_valid():
                obj = form.save(commit=False)
                if action == 'access':
                    obj.requester = request.user
                obj.save()
                messages.success(request, "Servis süreç kaydı oluşturuldu.")
                return redirect('service_operations')
            forms[action] = form
        elif action == 'resolve_incident':
            incident = MajorIncident.objects.filter(pk=request.POST.get('incident_id')).first()
            if incident:
                incident.status = 'resolved'
                incident.resolved_at = timezone.now()
                incident.save(update_fields=['status', 'resolved_at', 'updated_at'])
                messages.success(request, f"Major incident çözüldü: {incident.title}")
                return redirect('service_operations')
        elif action == 'approve_access':
            access_request = AccessRequest.objects.filter(pk=request.POST.get('access_id')).first()
            if access_request:
                access_request.status = 'approved'
                access_request.approved_by = request.user
                access_request.save(update_fields=['status', 'approved_by', 'updated_at'])
                messages.success(request, f"Erişim talebi onaylandı: {access_request.target_system}")
                return redirect('service_operations')
        elif action == 'printer_maintenance_done':
            printer = PrinterFleetItem.objects.filter(pk=request.POST.get('printer_id')).first()
            if printer:
                printer.status = 'online'
                printer.last_maintenance_at = timezone.now()
                printer.save(update_fields=['status', 'last_maintenance_at', 'updated_at'])
                messages.success(request, f"Yazıcı bakım tamamlandı: {printer.name}")
                return redirect('service_operations')

    open_incidents = MajorIncident.objects.exclude(status__in=['resolved', 'closed']).select_related('factory_area', 'incident_commander')
    pending_access = AccessRequest.objects.filter(status='pending').select_related('requester')
    printer_alerts = PrinterFleetItem.objects.filter(models.Q(toner_level_percent__lte=15) | models.Q(status__in=['warning', 'maintenance', 'offline'])).select_related('factory_area')
    active_runbooks = Runbook.objects.filter(is_active=True).select_related('owner')

    context = {
        'forms': forms,
        'open_incidents': open_incidents[:20],
        'pending_access': pending_access[:20],
        'printer_alerts': printer_alerts[:20],
        'runbooks': active_runbooks[:30],
        'metrics': {
            'open_incidents': open_incidents.count(),
            'pending_access': pending_access.count(),
            'printer_alerts': printer_alerts.count(),
            'runbooks': active_runbooks.count(),
        },
    }
    return render(request, 'service_operations.html', context)


@login_required
def command_center_view(request):
    if not is_support_staff(request.user):
        return redirect('dashboard')

    forms = {
        'remote_access': RemoteAccessGrantForm(),
        'channel': DepartmentChannelForm(),
        'message': DepartmentMessageForm(),
        'camera': CameraDeviceForm(),
        'application': BusinessApplicationForm(),
        'report': ReportTemplateForm(),
    }

    if request.method == 'POST':
        action = request.POST.get('action')
        form_map = {
            'remote_access': RemoteAccessGrantForm,
            'channel': DepartmentChannelForm,
            'message': DepartmentMessageForm,
            'camera': CameraDeviceForm,
            'application': BusinessApplicationForm,
            'report': ReportTemplateForm,
        }
        form_class = form_map.get(action)
        if form_class:
            form = form_class(request.POST)
            if form.is_valid():
                obj = form.save(commit=False)
                if action == 'message':
                    obj.author = request.user
                obj.save()
                messages.success(request, "Komuta merkezi kaydı oluşturuldu.")
                return redirect('command_center')
            forms[action] = form
        elif action == 'activate_remote_access':
            grant = RemoteAccessGrant.objects.filter(pk=request.POST.get('grant_id')).first()
            if grant:
                grant.status = 'active'
                grant.approved_by = request.user
                grant.save(update_fields=['status', 'approved_by', 'updated_at'])
                messages.success(request, f"Uzaktan erişim aktif edildi: {grant.employee_name}")
                return redirect('command_center')
        elif action == 'camera_checked':
            camera = CameraDevice.objects.filter(pk=request.POST.get('camera_id')).first()
            if camera:
                camera.status = 'online'
                camera.last_checked_at = timezone.now()
                camera.save(update_fields=['status', 'last_checked_at', 'updated_at'])
                messages.success(request, f"Kamera kontrol edildi: {camera.name}")
                return redirect('command_center')

    remote_access = RemoteAccessGrant.objects.exclude(status__in=['revoked', 'expired']).select_related('approved_by')
    camera_alerts = CameraDevice.objects.filter(status__in=['warning', 'offline', 'maintenance']).select_related('factory_area')
    applications = BusinessApplication.objects.select_related('technical_owner').order_by('status', 'name')
    channels = DepartmentChannel.objects.filter(is_active=True).order_by('department', 'name')

    context = {
        'forms': forms,
        'remote_access': remote_access[:20],
        'camera_alerts': camera_alerts[:20],
        'applications': applications[:24],
        'channels': channels[:20],
        'recent_messages': DepartmentMessage.objects.select_related('channel', 'author').order_by('-created_at')[:30],
        'reports': ReportTemplate.objects.filter(is_active=True).select_related('owner')[:20],
        'metrics': {
            'remote_access': remote_access.count(),
            'camera_alerts': camera_alerts.count(),
            'applications': applications.count(),
            'channels': channels.count(),
        },
    }
    return render(request, 'command_center.html', context)


@login_required
def governance_center_view(request):
    if not is_support_staff(request.user):
        return redirect('dashboard')

    forms = {
        'calendar': ChangeCalendarEventForm(),
        'dependency': ServiceDependencyForm(),
        'integration': IntegrationHealthCheckForm(),
        'compliance': ComplianceControlForm(),
        'document': DocumentOutputJobForm(),
    }

    if request.method == 'POST':
        action = request.POST.get('action')
        form_map = {
            'calendar': ChangeCalendarEventForm,
            'dependency': ServiceDependencyForm,
            'integration': IntegrationHealthCheckForm,
            'compliance': ComplianceControlForm,
            'document': DocumentOutputJobForm,
        }
        form_class = form_map.get(action)
        if form_class:
            form = form_class(request.POST)
            if form.is_valid():
                obj = form.save(commit=False)
                if action == 'document':
                    obj.requested_by = request.user
                obj.save()
                messages.success(request, "Yönetişim kaydı oluşturuldu.")
                return redirect('governance_center')
            forms[action] = form
        elif action == 'complete_calendar':
            event = ChangeCalendarEvent.objects.filter(pk=request.POST.get('event_id')).first()
            if event:
                event.status = 'completed'
                event.save(update_fields=['status', 'updated_at'])
                messages.success(request, f"Takvim işi tamamlandı: {event.title}")
                return redirect('governance_center')
        elif action == 'mark_integration_healthy':
            check = IntegrationHealthCheck.objects.filter(pk=request.POST.get('check_id')).first()
            if check:
                check.last_status = 'healthy'
                check.last_checked_at = timezone.now()
                check.save(update_fields=['last_status', 'last_checked_at', 'updated_at'])
                messages.success(request, f"Entegrasyon sağlıklı işaretlendi: {check.name}")
                return redirect('governance_center')
        elif action == 'mark_compliant':
            control = ComplianceControl.objects.filter(pk=request.POST.get('control_id')).first()
            if control:
                control.status = 'compliant'
                control.last_checked_at = timezone.now().date()
                control.save(update_fields=['status', 'last_checked_at', 'updated_at'])
                messages.success(request, f"Uyum kontrolü tamamlandı: {control.title}")
                return redirect('governance_center')
        elif action == 'mark_document_ready':
            job = DocumentOutputJob.objects.filter(pk=request.POST.get('job_id')).first()
            if job:
                job.status = 'ready'
                job.save(update_fields=['status', 'updated_at'])
                messages.success(request, f"Çıktı işi hazır: {job.title}")
                return redirect('governance_center')

    now = timezone.now()
    upcoming_events = ChangeCalendarEvent.objects.exclude(status__in=['completed', 'cancelled']).filter(start_at__lte=now + timedelta(days=14)).select_related('factory_area', 'owner')
    unhealthy_integrations = IntegrationHealthCheck.objects.filter(last_status__in=['degraded', 'down']).select_related('owner')
    open_controls = ComplianceControl.objects.exclude(status='compliant').select_related('owner')
    document_jobs = DocumentOutputJob.objects.exclude(status__in=['delivered']).select_related('requested_by', 'template')

    context = {
        'forms': forms,
        'upcoming_events': upcoming_events[:20],
        'dependencies': ServiceDependency.objects.select_related('business_application', 'device').order_by('criticality')[:30],
        'unhealthy_integrations': unhealthy_integrations[:20],
        'open_controls': open_controls[:20],
        'document_jobs': document_jobs[:20],
        'metrics': {
            'upcoming_events': upcoming_events.count(),
            'dependencies': ServiceDependency.objects.count(),
            'unhealthy_integrations': unhealthy_integrations.count(),
            'open_controls': open_controls.count(),
            'document_jobs': document_jobs.count(),
        },
    }
    return render(request, 'governance_center.html', context)


@login_required
def dlp_events_view(request):
    if not is_support_staff(request.user):
        return redirect('dashboard')
    events = DLPEvent.objects.select_related('user').order_by('-created_at')[:200]
    return render(request, 'dlp_events.html', {'events': events})


@login_required
def topology_png_export(request):
    if not is_support_staff(request.user):
        return redirect('dashboard')

    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import networkx as nx

    graph = nx.Graph()
    devices = Device.objects.select_related('parent_device').all()
    for device in devices:
        graph.add_node(device.name, device_type=device.device_type)
        if device.parent_device:
            graph.add_edge(device.parent_device.name, device.name)

    fig, ax = plt.subplots(figsize=(12, 8))
    pos = nx.spring_layout(graph, seed=42)
    colors = [
        '#ef4444' if graph.nodes[node].get('device_type') == 'Router'
        else '#22c55e' if graph.nodes[node].get('device_type') == 'Switch'
        else '#0ea5e9'
        for node in graph.nodes
    ]
    nx.draw_networkx(graph, pos, node_color=colors, edge_color='#94a3b8', with_labels=True, ax=ax, font_size=9)
    ax.set_axis_off()
    buffer = io.BytesIO()
    fig.tight_layout()
    fig.savefig(buffer, format='png', dpi=150)
    plt.close(fig)
    buffer.seek(0)
    return HttpResponse(buffer.getvalue(), content_type='image/png')


@login_required
@require_POST
def optimize_field_route(request):
    if not is_support_staff(request.user):
        return redirect('dashboard')
    visits = list(FieldVisit.objects.all().order_by('order_index', 'id'))
    current = None
    ordered = []
    remaining = visits[:]
    while remaining:
        if not current:
            next_visit = remaining.pop(0)
        else:
            next_visit = min(
                remaining,
                key=lambda v: ((v.latitude or 0) - (current.latitude or 0)) ** 2 + ((v.longitude or 0) - (current.longitude or 0)) ** 2,
            )
            remaining.remove(next_visit)
        ordered.append(next_visit)
        current = next_visit

    for index, visit in enumerate(ordered):
        visit.order_index = index + 1
        visit.save(update_fields=['order_index', 'updated_at'])
    messages.success(request, "Rota en yakın komşu algoritmasıyla optimize edildi.")
    return redirect('field_routes')


def _factory_area_ids_for_scope(department=None, zone=None):
    if zone and zone.factory_area_id:
        return [zone.factory_area_id]
    if department:
        return list(
            department.zones.filter(is_active=True, factory_area__isnull=False)
            .values_list('factory_area_id', flat=True)
            .distinct()
        )
    return []


def _gather_factory_scope_modules(department=None, zone=None):
    """Seçili departman/alan için modül kartları ve varlık listelerini üretir."""
    relation_filter = models.Q()
    document_filter = models.Q()

    if zone:
        relation_filter = models.Q(zone=zone)
        document_filter = models.Q(zone=zone) | models.Q(department=zone.department)
        scope_label = zone.name
    elif department:
        relation_filter = models.Q(department=department) | models.Q(zone__department=department)
        document_filter = models.Q(department=department)
        scope_label = department.name
    else:
        return {'scope_label': None, 'modules': [], 'relations': [], 'documents': []}

    relations = FactoryITAssetRelation.objects.filter(relation_filter).select_related(
        'department', 'zone', 'device', 'camera', 'endpoint', 'printer',
        'application', 'ticket', 'document', 'maintenance_task', 'consumable', 'it_asset',
    ).order_by('asset_type', '-updated_at')

    documents = ManagedDocument.objects.filter(document_filter).select_related('department', 'zone', 'owner').order_by('-updated_at')
    area_ids = _factory_area_ids_for_scope(department=department, zone=zone)

    cameras = CameraDevice.objects.filter(
        models.Q(pk__in=relations.filter(camera__isnull=False).values_list('camera_id', flat=True))
        | (models.Q(factory_area_id__in=area_ids) if area_ids else models.Q(pk__in=[]))
    ).distinct().order_by('status', 'name')

    devices = Device.objects.filter(
        pk__in=relations.filter(device__isnull=False).values_list('device_id', flat=True)
    ).order_by('name')

    endpoints = EndpointDevice.objects.filter(
        models.Q(pk__in=relations.filter(endpoint__isnull=False).values_list('endpoint_id', flat=True))
        | (models.Q(factory_area_id__in=area_ids) if area_ids else models.Q(pk__in=[]))
    ).distinct().order_by('status', 'hostname')

    printers = PrinterFleetItem.objects.filter(
        pk__in=relations.filter(printer__isnull=False).values_list('printer_id', flat=True)
    ).order_by('name')

    applications = BusinessApplication.objects.filter(
        pk__in=relations.filter(application__isnull=False).values_list('application_id', flat=True)
    ).order_by('name')

    tickets = Ticket.objects.filter(
        pk__in=relations.filter(ticket__isnull=False).values_list('ticket_id', flat=True)
    ).order_by('-created_at')

    maintenance_tasks = MaintenanceTask.objects.filter(
        models.Q(pk__in=relations.filter(maintenance_task__isnull=False).values_list('maintenance_task_id', flat=True))
        | (models.Q(factory_area_id__in=area_ids) if area_ids else models.Q(pk__in=[]))
    ).distinct().order_by('next_due_at')

    consumables = ConsumableItem.objects.filter(
        pk__in=relations.filter(consumable__isnull=False).values_list('consumable_id', flat=True)
    ).order_by('name')

    it_assets = ITAsset.objects.filter(
        pk__in=relations.filter(it_asset__isnull=False).values_list('it_asset_id', flat=True)
    ).order_by('name')

    modules = [
        {'key': 'cameras', 'title': 'Kameralar', 'icon': 'mdi:cctv', 'items': list(cameras[:8]), 'count': cameras.count(), 'url': '/komuta-merkezi/'},
        {'key': 'devices', 'title': 'Ağ Cihazları', 'icon': 'mdi:router-network', 'items': list(devices[:8]), 'count': devices.count(), 'url': '/topoloji/'},
        {'key': 'endpoints', 'title': 'Endpointler', 'icon': 'mdi:laptop', 'items': list(endpoints[:8]), 'count': endpoints.count(), 'url': '/kimlik-operasyonlari/'},
        {'key': 'printers', 'title': 'Yazıcılar', 'icon': 'mdi:printer', 'items': list(printers[:8]), 'count': printers.count(), 'url': '/servis-surecleri/'},
        {'key': 'applications', 'title': 'İş Uygulamaları', 'icon': 'mdi:apps', 'items': list(applications[:8]), 'count': applications.count(), 'url': '/komuta-merkezi/'},
        {'key': 'tickets', 'title': 'Ticketlar', 'icon': 'mdi:ticket-confirmation-outline', 'items': list(tickets[:8]), 'count': tickets.count(), 'url': '/panel/'},
        {'key': 'documents', 'title': 'Dokümanlar', 'icon': 'mdi:file-document-outline', 'items': list(documents[:8]), 'count': documents.count(), 'url': '#documents-panel'},
        {'key': 'maintenance', 'title': 'Bakım İşleri', 'icon': 'mdi:wrench-clock', 'items': list(maintenance_tasks[:8]), 'count': maintenance_tasks.count(), 'url': '/fabrika-operasyonlari/'},
        {'key': 'consumables', 'title': 'Sarf/Yedek', 'icon': 'mdi:package-variant-closed', 'items': list(consumables[:8]), 'count': consumables.count(), 'url': '/fabrika-operasyonlari/'},
        {'key': 'assets', 'title': 'IT Varlıkları', 'icon': 'mdi:server-network', 'items': list(it_assets[:8]), 'count': it_assets.count(), 'url': '/it-envanter/'},
    ]

    risk_count = (
        cameras.filter(status__in=['offline', 'warning']).count()
        + endpoints.exclude(status='compliant').count()
        + sum(1 for task in maintenance_tasks if task.is_overdue)
        + documents.filter(status__in=['draft', 'review']).count()
    )

    return {
        'scope_label': scope_label,
        'modules': modules,
        'relations': relations[:30],
        'documents': documents[:20],
        'risk_count': risk_count,
    }


@login_required
def factory_portfolio_inventory_view(request):
    """Müşteri portföyündeki fabrika tesisleri ve bölüm envanterleri."""
    if not is_support_staff(request.user):
        return redirect('dashboard')

    factory_sites = get_accessible_sites(request.user).annotate(
        department_total=Count('departments', filter=models.Q(departments__is_active=True), distinct=True),
        inventory_total=Count('inventory_items', filter=models.Q(inventory_items__is_active=True), distinct=True),
    )

    selected_site = None
    selected_department = None
    site_id = request.GET.get('site')
    department_id = request.GET.get('department')

    if site_id:
        if not user_can_access_site(request.user, site_id):
            messages.error(request, 'Bu fabrika tesisine erişim yetkiniz yok.')
            return redirect('factory_portfolio_inventory')
        selected_site = factory_sites.filter(pk=site_id).first()
    if not selected_site:
        selected_site = factory_sites.first()

    if department_id and selected_site:
        selected_department = FactoryDepartment.objects.filter(
            pk=department_id, factory_site=selected_site, is_active=True,
        ).first()

    forms = {
        'site_new': FactorySiteForm(),
        'inventory': DepartmentInventoryItemForm(),
    }
    if selected_site:
        forms['site_edit'] = FactorySiteForm(instance=selected_site)
        forms['inventory'].fields['factory_site'].initial = selected_site.pk
        forms['inventory'].fields['department'].queryset = FactoryDepartment.objects.filter(
            factory_site=selected_site, is_active=True,
        ).order_by('name')
        forms['inventory'].fields['zone'].queryset = FactoryZone.objects.filter(
            department__factory_site=selected_site, is_active=True,
        ).select_related('department').order_by('department__name', 'name')

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'site':
            form = FactorySiteForm(request.POST)
            if form.is_valid():
                form.save()
                messages.success(request, "Fabrika tesisi kaydedildi.")
                return redirect(f"{reverse('factory_portfolio_inventory')}?site={form.instance.pk}")
            forms['site_new'] = form
        elif action == 'update_site' and selected_site:
            form = FactorySiteForm(request.POST, instance=selected_site)
            if form.is_valid():
                form.save()
                messages.success(request, "Tesis başlıkları güncellendi.")
                return redirect(f"{reverse('factory_portfolio_inventory')}?site={selected_site.pk}")
            forms['site_edit'] = form
        elif action == 'inventory':
            form = DepartmentInventoryItemForm(request.POST)
            if form.is_valid():
                form.save()
                messages.success(request, "Envanter kalemi eklendi.")
                redirect_url = reverse('factory_portfolio_inventory')
                params = [f"site={form.instance.factory_site_id}"]
                if form.instance.department_id:
                    params.append(f"department={form.instance.department_id}")
                return redirect(f"{redirect_url}?{'&'.join(params)}")
            forms['inventory'] = form

    departments = []
    inventory_groups = []
    inventory_items = DepartmentInventoryItem.objects.none()
    if selected_site:
        departments = FactoryDepartment.objects.filter(
            factory_site=selected_site, is_active=True,
        ).annotate(
            inventory_total=Count('inventory_items', filter=models.Q(inventory_items__is_active=True)),
            zone_total=Count('zones', filter=models.Q(zones__is_active=True)),
        ).order_by('department_type', 'name')

        inventory_qs = DepartmentInventoryItem.objects.filter(
            factory_site=selected_site, is_active=True,
        ).select_related('department', 'zone').order_by('department__name', 'sort_order', 'title')
        if selected_department:
            inventory_qs = inventory_qs.filter(department=selected_department)
        inventory_items = inventory_qs

        grouped = {}
        for item in inventory_items:
            key = item.department_id or 0
            grouped.setdefault(key, {'department': item.department, 'items': []})['items'].append(item)
        inventory_groups = sorted(
            grouped.values(),
            key=lambda group: (group['department'].name if group['department'] else 'zzz'),
        )

    context = {
        'factory_sites': factory_sites,
        'selected_site': selected_site,
        'selected_department': selected_department,
        'departments': departments,
        'inventory_items': inventory_items,
        'inventory_groups': inventory_groups,
        'forms': forms,
        'metrics': {
            'sites': factory_sites.count(),
            'departments': departments.count() if selected_site else 0,
            'inventory': inventory_items.count(),
            'industries': factory_sites.values('industry_type').distinct().count(),
        },
    }
    return render(request, 'factory_portfolio_inventory.html', context)


@login_required
def factory_command_center_view(request):
    if not is_support_staff(request.user):
        return redirect('dashboard')

    forms = {
        'department': FactoryDepartmentForm(),
        'zone': FactoryZoneForm(),
        'document': ManagedDocumentForm(),
        'relation': FactoryITAssetRelationForm(),
    }

    factory_sites = get_accessible_sites(request.user)
    selected_site = None
    site_id = request.GET.get('site')
    if site_id:
        if not user_can_access_site(request.user, site_id):
            messages.error(request, 'Bu fabrika tesisine erişim yetkiniz yok.')
            return redirect('factory_command_center')
        selected_site = factory_sites.filter(pk=site_id).first()
    if not selected_site:
        selected_site = factory_sites.first()

    if selected_site:
        forms['department'].fields['factory_site'].initial = selected_site.pk

    if request.method == 'POST':
        action = request.POST.get('action')
        form_map = {
            'department': FactoryDepartmentForm,
            'zone': FactoryZoneForm,
            'document': ManagedDocumentForm,
            'relation': FactoryITAssetRelationForm,
        }
        form_class = form_map.get(action)
        if form_class:
            form = form_class(request.POST, request.FILES if action == 'document' else None)
            if form.is_valid():
                obj = form.save(commit=False)
                if action == 'document':
                    obj.owner = request.user
                obj.save()
                if hasattr(form, 'save_m2m'):
                    form.save_m2m()
                messages.success(request, "Fabrika komuta merkezi kaydı oluşturuldu.")
                redirect_url = 'factory_command_center'
                site_param = f"site={obj.factory_site_id}" if getattr(obj, 'factory_site_id', None) else (
                    f"site={selected_site.pk}" if selected_site else ''
                )
                if action == 'zone' and obj.department_id:
                    url = f"{reverse('factory_command_center')}?department={obj.department_id}"
                    if site_param:
                        url = f"{url}&{site_param}"
                    return redirect(url)
                if action in ('document', 'relation') and obj.department_id:
                    url = f"{reverse('factory_command_center')}?department={obj.department_id}"
                    if site_param:
                        url = f"{url}&{site_param}"
                    return redirect(url)
                if site_param:
                    return redirect(f"{reverse('factory_command_center')}?{site_param}")
                return redirect(redirect_url)
            forms[action] = form
        elif action == 'approve_document':
            document = ManagedDocument.objects.filter(pk=request.POST.get('document_id')).first()
            if document:
                document.status = 'approved'
                document.save(update_fields=['status', 'updated_at'])
                messages.success(request, f"Doküman onaylandı: {document.title}")
                return redirect(f"{reverse('factory_command_center')}?document={document.pk}")

    selected_department = None
    selected_zone = None
    selected_document = None

    department_id = request.GET.get('department')
    zone_id = request.GET.get('zone')
    document_id = request.GET.get('document')

    if department_id:
        selected_department = FactoryDepartment.objects.filter(pk=department_id, is_active=True).first()
    if zone_id:
        selected_zone = FactoryZone.objects.select_related('department', 'factory_area').filter(pk=zone_id, is_active=True).first()
        if selected_zone and not selected_department:
            selected_department = selected_zone.department
    if document_id:
        selected_document = ManagedDocument.objects.select_related('department', 'zone', 'owner').filter(pk=document_id).first()
        if selected_document and not selected_department and selected_document.department_id:
            selected_department = selected_document.department

    departments = FactoryDepartment.objects.filter(is_active=True)
    departments = filter_queryset_by_site(departments, request.user)
    if selected_site:
        departments = departments.filter(factory_site=selected_site)
    departments = departments.annotate(
        zone_total=Count('zones', filter=models.Q(zones__is_active=True))
    ).select_related('factory_site').order_by('department_type', 'name')

    scope = _gather_factory_scope_modules(
        department=selected_department,
        zone=selected_zone,
    )

    if not selected_department and not selected_zone:
        scope['documents'] = list(
            ManagedDocument.objects.select_related('department', 'zone', 'owner').order_by('-updated_at')[:20]
        )

    zones = []
    if selected_department:
        zones = selected_department.zones.filter(is_active=True).select_related('factory_area').order_by('zone_type', 'name')

    context = {
        'forms': forms,
        'factory_sites': factory_sites,
        'selected_site': selected_site,
        'departments': departments,
        'selected_department': selected_department,
        'selected_zone': selected_zone,
        'selected_document': selected_document,
        'zones': zones,
        'scope': scope,
        'metrics': {
            'departments': departments.count(),
            'zones': FactoryZone.objects.filter(is_active=True).count(),
            'documents': ManagedDocument.objects.count(),
            'relations': FactoryITAssetRelation.objects.count(),
            'review_documents': sum(1 for doc in ManagedDocument.objects.all() if doc.needs_review),
            'risk_items': scope.get('risk_count', 0) if selected_department or selected_zone else 0,
        },
    }
    return render(request, 'factory_command_center.html', context)


@login_required
def managed_document_download(request, pk):
    if not is_support_staff(request.user):
        return redirect('dashboard')
    document = ManagedDocument.objects.filter(pk=pk).first()
    if not document or not document.file:
        from django.http import Http404
        raise Http404('Doküman bulunamadı.')
    filename = os.path.basename(document.file.name)
    return FileResponse(document.file.open('rb'), as_attachment=True, filename=filename)


@login_required
def managed_document_preview(request, pk):
    if not is_support_staff(request.user):
        return redirect('dashboard')
    document = ManagedDocument.objects.filter(pk=pk).first()
    if not document or not document.can_browser_preview:
        from django.http import Http404
        raise Http404('Bu doküman tarayıcıda önizlenemiyor.')
    filename = os.path.basename(document.file.name)
    response = FileResponse(document.file.open('rb'), content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="{filename}"'
    return response


@login_required
def asset_qr_scanner_view(request):
    if not is_support_staff(request.user):
        return redirect('dashboard')

    lookup_result = None
    forms = {'tag': AssetQRTagForm()}

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'tag':
            form = AssetQRTagForm(request.POST)
            if form.is_valid():
                form.save()
                messages.success(request, 'QR etiket kaydı oluşturuldu.')
                return redirect('asset_qr_scanner')
            forms['tag'] = form
        elif action == 'lookup':
            from .integrations.qr_resolver import resolve_qr_code
            lookup_result = resolve_qr_code(request.POST.get('code'))

    recent_tags = AssetQRTag.objects.filter(is_active=True).select_related(
        'device', 'endpoint', 'it_asset', 'camera', 'factory_zone',
    ).order_by('-updated_at')[:20]

    return render(request, 'asset_qr_scanner.html', {
        'forms': forms,
        'lookup_result': lookup_result,
        'recent_tags': recent_tags,
        'metrics': {'tags': AssetQRTag.objects.filter(is_active=True).count()},
    })


@login_required
def qr_lookup_api(request):
    if not is_support_staff(request.user):
        return JsonResponse({'detail': 'Yetkisiz'}, status=403)
    from .integrations.qr_resolver import resolve_qr_code
    code = (request.GET.get('code') or '').strip()
    return JsonResponse(resolve_qr_code(code) or {'found': False, 'code': code})


@login_required
def managed_document_editor(request, pk):
    if not is_support_staff(request.user):
        return redirect('dashboard')
    from django.http import Http404
    from .integrations.document_editor import build_document_editor_context, get_document_editor_backend

    document = ManagedDocument.objects.filter(pk=pk).first()
    if not document or not document.file or not document.can_office_edit:
        raise Http404('Bu doküman tarayıcı editöründe açılamaz.')

    editor_context = build_document_editor_context(document, request)
    if not editor_context:
        backend = get_document_editor_backend()
        messages.warning(
            request,
            'Belge editörü yapılandırılmamış. ONLYOFFICE_DOCUMENT_SERVER_URL veya COLLABORA_SERVER_URL ayarlayın.',
        )
        return redirect(f"{reverse('factory_command_center')}?document={document.pk}")

    return render(request, 'managed_document_editor.html', {
        'document': document,
        **editor_context,
    })


@csrf_exempt
@require_POST
def managed_document_editor_callback(request, pk):
    """OnlyOffice belge sunucusunun kaydetme geri çağrısı (callback)."""
    import json
    import urllib.request
    from django.http import HttpResponse
    from .integrations.onlyoffice import build_document_key

    document = ManagedDocument.objects.filter(pk=pk).first()
    if not document:
        return HttpResponse(json.dumps({'error': 1}), content_type='application/json')

    try:
        payload = json.loads(request.body.decode('utf-8'))
    except (ValueError, UnicodeDecodeError):
        return HttpResponse(json.dumps({'error': 1}), content_type='application/json')

    status = payload.get('status')
    if status == 2 and payload.get('url'):
        try:
            with urllib.request.urlopen(payload['url'], timeout=30) as remote:
                content = remote.read()
            filename = os.path.basename(document.file.name)
            document.file.save(filename, ContentFile(content), save=False)
            document.file_size = len(content)
            document.updated_at = timezone.now()
            document.save(update_fields=['file', 'file_size', 'updated_at'])
        except Exception as exc:
            SystemLog.objects.create(action='SYSTEM', details=f'OnlyOffice callback hatası #{document.pk}: {exc}')
            return HttpResponse(json.dumps({'error': 1}), content_type='application/json')

    if build_document_key(document) != payload.get('key', ''):
        pass

    return HttpResponse(json.dumps({'error': 0}), content_type='application/json')


@csrf_exempt
def wopi_check_file_info(request, pk):
    """Collabora WOPI CheckFileInfo uç noktası."""
    from .integrations.collabora import build_wopi_check_file_info, verify_wopi_access_token

    document = ManagedDocument.objects.filter(pk=pk).first()
    if not document or not document.file:
        return JsonResponse({'detail': 'Dosya bulunamadı.'}, status=404)

    user_id = request.GET.get('access_token_uid') or request.user.id if request.user.is_authenticated else None
    token = request.GET.get('access_token', '')
    if not user_id:
        user_id = document.owner_id or 1
    if not verify_wopi_access_token(document.pk, user_id, token):
        return JsonResponse({'detail': 'WOPI erişim belirteci geçersiz.'}, status=401)

    user = User.objects.filter(pk=user_id).first() or request.user
    payload = build_wopi_check_file_info(document, user)
    response = JsonResponse(payload)
    response['X-WOPI-ItemVersion'] = str(document.version)
    return response


@csrf_exempt
def wopi_file_contents(request, pk):
    """Collabora WOPI GetFile / PutFile uç noktası."""
    from .integrations.collabora import verify_wopi_access_token

    document = ManagedDocument.objects.filter(pk=pk).first()
    if not document or not document.file:
        return JsonResponse({'detail': 'Dosya bulunamadı.'}, status=404)

    user_id = request.GET.get('access_token_uid') or (request.user.id if request.user.is_authenticated else document.owner_id or 1)
    token = request.GET.get('access_token', '')
    if not verify_wopi_access_token(document.pk, user_id, token):
        return JsonResponse({'detail': 'WOPI erişim belirteci geçersiz.'}, status=401)

    if request.method == 'GET':
        filename = os.path.basename(document.file.name)
        response = FileResponse(document.file.open('rb'))
        response['Content-Disposition'] = f'inline; filename="{filename}"'
        return response

    if request.method == 'POST' and request.headers.get('X-WOPI-Override', '').upper() == 'PUT':
        content = request.body
        filename = os.path.basename(document.file.name)
        document.file.save(filename, ContentFile(content), save=False)
        document.file_size = len(content)
        document.updated_at = timezone.now()
        document.save(update_fields=['file', 'file_size', 'updated_at'])
        return HttpResponse(status=200)

    return JsonResponse({'detail': 'Desteklenmeyen WOPI işlemi.'}, status=405)


@login_required
def asset_qr_label_pdf(request, pk):
    """Tek QR etiket PDF çıktısı."""
    if not is_support_staff(request.user):
        return redirect('dashboard')
    from django.http import Http404
    from .integrations.qr_labels import build_qr_labels_pdf

    tag = AssetQRTag.objects.filter(pk=pk, is_active=True).first()
    if not tag:
        raise Http404('QR etiket bulunamadı.')

    pdf_buffer = build_qr_labels_pdf([tag], base_url=request.build_absolute_uri('/'))
    response = FileResponse(pdf_buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="qr-{tag.code}.pdf"'
    return response


@login_required
def asset_qr_labels_batch_pdf(request):
    """Seçili veya tüm aktif QR etiketler için toplu PDF."""
    if not is_support_staff(request.user):
        return redirect('dashboard')
    from .integrations.qr_labels import build_qr_labels_pdf

    ids = [value for value in request.GET.get('ids', '').split(',') if value.strip().isdigit()]
    queryset = AssetQRTag.objects.filter(is_active=True).order_by('code')
    if ids:
        queryset = queryset.filter(pk__in=ids)
    tags = list(queryset[:50])
    if not tags:
        messages.warning(request, 'PDF için aktif QR etiket bulunamadı.')
        return redirect('asset_qr_scanner')

    pdf_buffer = build_qr_labels_pdf(tags, base_url=request.build_absolute_uri('/'))
    response = FileResponse(pdf_buffer, content_type='application/pdf')
    response['Content-Disposition'] = 'inline; filename="omniops-qr-etiketleri.pdf"'
    return response


@login_required
def erp_integrations_view(request):
    if not is_support_staff(request.user):
        return redirect('dashboard')

    form = ERPConnectionForm()
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'connection':
            form = ERPConnectionForm(request.POST)
            if form.is_valid():
                obj = form.save(commit=False)
                obj.owner = request.user
                obj.save()
                messages.success(request, 'ERP bağlantısı kaydedildi.')
                return redirect('erp_integrations')
        elif action == 'test_connection':
            connection = ERPConnection.objects.filter(pk=request.POST.get('connection_id')).first()
            if connection:
                from .integrations.erp_connector import ERPClientError, test_erp_connection
                try:
                    result = test_erp_connection(connection)
                    connection.last_sync_status = 'healthy'
                    connection.last_sync_message = f"Test OK · sürüm {result.get('server_version', 'unknown')}"
                    connection.save(update_fields=['last_sync_status', 'last_sync_message', 'updated_at'])
                    messages.success(request, connection.last_sync_message)
                except ERPClientError as exc:
                    connection.last_sync_status = 'error'
                    connection.last_sync_message = str(exc)
                    connection.save(update_fields=['last_sync_status', 'last_sync_message', 'updated_at'])
                    messages.error(request, str(exc))
                return redirect('erp_integrations')
        elif action == 'sync_connection':
            connection = ERPConnection.objects.filter(pk=request.POST.get('connection_id')).first()
            if connection:
                from inventory.tasks import sync_erp_connection_task
                sync_erp_connection_task.delay(connection.id)
                messages.success(request, f'{connection.name} sync kuyruğa alındı.')
                return redirect('erp_integrations')
        elif action == 'poll_cameras':
            from inventory.tasks import poll_camera_health_task
            poll_camera_health_task.delay()
            messages.success(request, 'Kamera sağlık taraması kuyruğa alındı.')
            return redirect('erp_integrations')

    connections = ERPConnection.objects.select_related('owner').order_by('erp_type', 'name')
    camera_summary = {
        'online': CameraDevice.objects.filter(status='online').count(),
        'warning': CameraDevice.objects.filter(status='warning').count(),
        'offline': CameraDevice.objects.filter(status='offline').count(),
        'maintenance': CameraDevice.objects.filter(status='maintenance').count(),
    }

    return render(request, 'erp_integrations.html', {
        'form': form,
        'connections': connections,
        'camera_summary': camera_summary,
        'metrics': {
            'connections': connections.count(),
            'healthy': connections.filter(last_sync_status='healthy').count(),
            'errors': connections.filter(last_sync_status='error').count(),
        },
    })


@login_required
def ot_integrations_view(request):
    if not is_support_staff(request.user):
        return redirect('dashboard')

    form = OTConnectionForm()
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'connection':
            form = OTConnectionForm(request.POST)
            if form.is_valid():
                obj = form.save(commit=False)
                obj.owner = request.user
                obj.save()
                messages.success(request, 'OT/MES bağlantısı kaydedildi.')
                return redirect('ot_integrations')
        elif action == 'test_connection':
            connection = OTConnection.objects.filter(pk=request.POST.get('connection_id')).first()
            if connection:
                from .integrations.ot_connector import OTClientError, test_ot_connection
                try:
                    result = test_ot_connection(connection)
                    messages.success(request, f"OT test OK · örnek varlık: {result.get('asset_sample', 0)}")
                except OTClientError as exc:
                    messages.error(request, str(exc))
                return redirect('ot_integrations')
        elif action == 'sync_connection':
            connection = OTConnection.objects.filter(pk=request.POST.get('connection_id')).first()
            if connection:
                from inventory.tasks import sync_ot_connection_task
                sync_ot_connection_task.delay(connection.id)
                messages.success(request, f'{connection.name} OT sync kuyruğa alındı.')
                return redirect('ot_integrations')

    connections = filter_queryset_by_site(
        OTConnection.objects.select_related('owner', 'factory_site').order_by('factory_site__title', 'name'),
        request.user,
    )
    return render(request, 'ot_integrations.html', {
        'form': form,
        'connections': connections,
        'metrics': {
            'connections': connections.count(),
            'healthy': connections.filter(last_sync_status='healthy').count(),
            'errors': connections.filter(last_sync_status='error').count(),
        },
    })


@login_required
def integration_hub_center_view(request):
    if not is_support_staff(request.user):
        return redirect('dashboard')
    if not user_has_module_permission(request.user, 'integrations', 'view'):
        messages.error(request, 'Entegrasyon merkezi için yetkiniz yok.')
        return redirect('dashboard')

    forms = {
        'notification': NotificationChannelForm(),
        'monitoring': MonitoringConnectionForm(),
        'vms': VMSConnectionForm(),
        'email_inbox': EmailTicketInboxForm(),
        'backup': BackupVendorConnectionForm(),
        'wms': WMSConnectionForm(),
        'module_grant': ModulePermissionGrantForm(),
    }

    if request.method == 'POST':
        action = request.POST.get('action')
        form_map = {
            'notification': NotificationChannelForm,
            'monitoring': MonitoringConnectionForm,
            'vms': VMSConnectionForm,
            'email_inbox': EmailTicketInboxForm,
            'backup': BackupVendorConnectionForm,
            'wms': WMSConnectionForm,
            'module_grant': ModulePermissionGrantForm,
        }
        if action in form_map:
            form = form_map[action](request.POST)
            if form.is_valid():
                obj = form.save(commit=False)
                if action == 'notification':
                    obj.owner = request.user
                if action == 'module_grant':
                    obj.granted_by = request.user
                obj.save()
                from .audit import record_audit
                record_audit('create', action, obj.pk, actor=request.user, request=request)
                messages.success(request, 'Kayıt oluşturuldu.')
                return redirect('integration_hub_center')
            forms[action] = form
        elif action == 'sync_monitoring':
            connection = MonitoringConnection.objects.filter(pk=request.POST.get('connection_id')).first()
            if connection:
                from inventory.tasks import sync_monitoring_connection_task
                sync_monitoring_connection_task.delay(connection.id)
                messages.success(request, f'{connection.name} izleme sync kuyruğa alındı.')
                return redirect('integration_hub_center')
        elif action == 'sync_vms':
            connection = VMSConnection.objects.filter(pk=request.POST.get('connection_id')).first()
            if connection:
                from inventory.tasks import sync_vms_connection_task
                sync_vms_connection_task.delay(connection.id)
                messages.success(request, f'{connection.name} VMS sync kuyruğa alındı.')
                return redirect('integration_hub_center')
        elif action == 'poll_email_inbox':
            inbox = EmailTicketInbox.objects.filter(pk=request.POST.get('inbox_id')).first()
            if inbox:
                from inventory.tasks import poll_email_ticket_inbox_task
                poll_email_ticket_inbox_task.delay(inbox.id)
                messages.success(request, f'{inbox.name} e-posta taraması kuyruğa alındı.')
                return redirect('integration_hub_center')
        elif action == 'sync_backup':
            connection = BackupVendorConnection.objects.filter(pk=request.POST.get('connection_id')).first()
            if connection:
                from inventory.tasks import sync_backup_vendor_connection_task
                sync_backup_vendor_connection_task.delay(connection.id)
                messages.success(request, f'{connection.name} backup sync kuyruğa alındı.')
                return redirect('integration_hub_center')
        elif action == 'sync_wms':
            connection = WMSConnection.objects.filter(pk=request.POST.get('connection_id')).first()
            if connection:
                from inventory.tasks import sync_wms_connection_task
                sync_wms_connection_task.delay(connection.id)
                messages.success(request, f'{connection.name} WMS sync kuyruğa alındı.')
                return redirect('integration_hub_center')
        elif action == 'test_notification':
            channel = NotificationChannel.objects.filter(pk=request.POST.get('channel_id')).first()
            if channel:
                from .notification_dispatcher import NotificationError, send_notification
                try:
                    send_notification(channel, 'OmniOps Test', 'Entegrasyon merkezi test bildirimi.')
                    messages.success(request, f'Test bildirimi gönderildi: {channel.name}')
                except NotificationError as exc:
                    messages.error(request, str(exc))
                return redirect('integration_hub_center')

    monitoring = filter_queryset_by_site(
        MonitoringConnection.objects.select_related('factory_site').order_by('name'), request.user,
    )
    vms = filter_queryset_by_site(
        VMSConnection.objects.select_related('factory_site').order_by('name'), request.user,
    )
    notifications = filter_queryset_by_site(
        NotificationChannel.objects.select_related('factory_site', 'owner').order_by('name'), request.user,
    )
    inboxes = filter_queryset_by_site(
        EmailTicketInbox.objects.select_related('factory_site').order_by('name'), request.user,
    )
    backups = BackupVendorConnection.objects.order_by('name')
    wms_connections = filter_queryset_by_site(
        WMSConnection.objects.select_related('factory_site').order_by('name'), request.user,
    )
    module_grants = ModulePermissionGrant.objects.select_related('user', 'factory_site', 'granted_by').order_by('-created_at')[:50]

    return render(request, 'integration_hub_center.html', {
        'forms': forms,
        'monitoring_connections': monitoring,
        'vms_connections': vms,
        'notification_channels': notifications,
        'email_inboxes': inboxes,
        'backup_connections': backups,
        'wms_connections': wms_connections,
        'module_grants': module_grants,
        'metrics': {
            'monitoring': monitoring.count(),
            'vms': vms.count(),
            'notifications': notifications.count(),
            'inboxes': inboxes.count(),
            'backups': backups.count(),
            'wms': wms_connections.count(),
        },
    })


@login_required
def itsm_maturity_view(request):
    if not is_support_staff(request.user):
        return redirect('dashboard')
    if not user_has_module_permission(request.user, 'governance', 'view'):
        messages.error(request, 'ITSM olgunluk modülü için yetkiniz yok.')
        return redirect('dashboard')

    forms = {
        'problem': ProblemRecordForm(),
        'release': ReleaseRecordForm(),
        'lifecycle': AssetLifecycleEventForm(),
    }

    if request.method == 'POST':
        action = request.POST.get('action')
        form_map = {
            'problem': ProblemRecordForm,
            'release': ReleaseRecordForm,
            'lifecycle': AssetLifecycleEventForm,
        }
        if action in form_map:
            form = form_map[action](request.POST)
            if form.is_valid():
                obj = form.save(commit=False)
                if action == 'problem':
                    obj.owner = obj.owner or request.user
                elif action == 'release':
                    obj.owner = obj.owner or request.user
                elif action == 'lifecycle':
                    obj.performed_by = request.user
                obj.save()
                from .audit import record_audit
                record_audit('create', action, obj.pk, actor=request.user, request=request)
                messages.success(request, 'ITSM kaydı oluşturuldu.')
                return redirect('itsm_maturity')
            forms[action] = form
        elif action == 'resolve_problem':
            problem = ProblemRecord.objects.filter(pk=request.POST.get('problem_id')).first()
            if problem:
                problem.status = 'resolved'
                problem.resolved_at = timezone.now()
                problem.save(update_fields=['status', 'resolved_at', 'updated_at'])
                messages.success(request, f'Problem çözüldü: {problem.title}')
                return redirect('itsm_maturity')
        elif action == 'approve_release_cab':
            release = ReleaseRecord.objects.filter(pk=request.POST.get('release_id')).first()
            if release:
                release.cab_approved = True
                release.status = 'approved'
                release.save(update_fields=['cab_approved', 'status', 'updated_at'])
                messages.success(request, f'CAB onayı verildi: {release.title}')
                return redirect('itsm_maturity')

    problems_qs = filter_queryset_by_site(
        ProblemRecord.objects.select_related('factory_site', 'owner').exclude(status='closed').order_by('-updated_at'),
        request.user,
    )
    releases_qs = filter_queryset_by_site(
        ReleaseRecord.objects.select_related('factory_site', 'owner').order_by('-planned_start', '-updated_at'),
        request.user,
    )
    lifecycle_qs = filter_queryset_by_site(
        AssetLifecycleEvent.objects.select_related('factory_site', 'it_asset', 'performed_by').order_by('-event_date'),
        request.user,
    )
    audit_entries = ImmutableAuditEntry.objects.select_related('actor').order_by('-created_at')[:40]

    return render(request, 'itsm_maturity.html', {
        'forms': forms,
        'problems': problems_qs[:25],
        'releases': releases_qs[:25],
        'lifecycle_events': lifecycle_qs[:40],
        'audit_entries': audit_entries,
        'metrics': {
            'open_problems': problems_qs.exclude(status='resolved').count(),
            'pending_releases': releases_qs.filter(status__in=['planned', 'cab_review']).count(),
            'lifecycle_events': lifecycle_qs.count(),
            'audit_entries': ImmutableAuditEntry.objects.count(),
        },
    })


def prometheus_metrics_view(request):
    """Prometheus scrape uç noktası (basit metrikler)."""
    if not getattr(settings, 'PROMETHEUS_METRICS_ENABLED', True):
        return HttpResponse('disabled', status=404)
    lines = [
        '# HELP omniops_tickets_open Açık ticket sayısı',
        '# TYPE omniops_tickets_open gauge',
        f'omniops_tickets_open {Ticket.objects.filter(status="Acik").count()}',
        '# HELP omniops_factory_sites_active Aktif fabrika tesisi sayısı',
        '# TYPE omniops_factory_sites_active gauge',
        f'omniops_factory_sites_active {FactorySite.objects.filter(is_active=True).count()}',
        '# HELP omniops_devices_active Aktif ağ cihazı sayısı',
        '# TYPE omniops_devices_active gauge',
        f'omniops_devices_active {Device.objects.filter(is_active=True).count()}',
        '# HELP omniops_audit_entries_total Denetim izi kayıt sayısı',
        '# TYPE omniops_audit_entries_total counter',
        f'omniops_audit_entries_total {ImmutableAuditEntry.objects.count()}',
    ]
    return HttpResponse('\n'.join(lines) + '\n', content_type='text/plain; version=0.0.4; charset=utf-8')
