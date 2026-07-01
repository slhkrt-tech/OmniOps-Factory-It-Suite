from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.auth import login
from django.db import models
from django.db.models import Count
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from datetime import timedelta
from django.core.paginator import Paginator
from django.core.mail import send_mail
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.urls import reverse_lazy
from .decorators import role_required  # RBAC Güvenlik Kilidi
from guardian.shortcuts import get_objects_for_user  # Guardian OLP Kütüphanesi
import logging
import ipaddress
import csv
import io
import json
import difflib
from html import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

from .utils import (
    generate_device_config, calculate_subnets, scan_network, 
    push_config_to_device, backup_device_config,
    decrypt_vault_password
)
from .tasks import active_response_block_ip

from .models import (
    Device, Ticket, IpAddress, SystemLog, DeviceBackup, ITAsset, License, Port,
    KnowledgeBaseArticle, VendorContract, ChangeRequest, ServiceCatalogItem,
    TicketCategory, NetworkScan, NetworkScanHost, DirectoryConnection,
    DirectoryUser, EndpointDevice, IdentityLifecycleTask,
)

from .forms import (
    DeviceForm, TicketForm, RegisterUserForm, 
    PublicRegistrationForm, IpAddressForm, ITAssetForm, LicenseForm, CustomerTicketForm
)
from .dlp import inspect_text_for_dlp, has_blocking_dlp_event

logger = logging.getLogger(__name__)


def send_notification_email(subject, message):
    try:
        send_mail(
            subject=f"[OmniOps] {subject}",
            message=message,
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@omniops.local'),
            recipient_list=[admin[1] for admin in getattr(settings, 'ADMINS', [('Admin', 'admin@firma.com')])],
            fail_silently=True, 
        )
    except Exception:
        logger.exception("Bildirim e-postası gönderilemedi.")


@login_required
def global_search_api(request):
    """OmniOps genelinde piyasa standardı hızlı arama / komut paleti verisi."""
    query = (request.GET.get('q') or '').strip()
    limit = 6

    quick_actions = [
        {'type': 'Aksiyon', 'title': 'Yeni Ticket Aç', 'subtitle': 'Servis masası ve sistem biletleri', 'url': '/panel/', 'icon': 'mdi:ticket-plus-outline'},
        {'type': 'Aksiyon', 'title': 'Fabrika BT Komuta Merkezi', 'subtitle': 'Departman kartelası, modüller ve doküman merkezi', 'url': '/fabrika-komuta-merkezi/', 'icon': 'mdi:factory'},
        {'type': 'Aksiyon', 'title': 'QR/Barkod Tarayıcı', 'subtitle': 'Etiket okut, varlığa anında git', 'url': '/varlik-qr-tara/', 'icon': 'mdi:qrcode-scan'},
        {'type': 'Aksiyon', 'title': 'ERP & Entegrasyon', 'subtitle': 'Odoo bağlantıları ve kamera health poll', 'url': '/erp-entegrasyonlari/', 'icon': 'mdi:connection'},
        {'type': 'Aksiyon', 'title': 'Komuta Merkezi', 'subtitle': 'VPN, chat, kamera ve uygulama portalı', 'url': '/komuta-merkezi/', 'icon': 'mdi:view-dashboard-edit-outline'},
        {'type': 'Aksiyon', 'title': 'Yönetişim Merkezi', 'subtitle': 'Takvim, CMDB, denetim ve çıktılar', 'url': '/yonetisim-merkezi/', 'icon': 'mdi:calendar-check-outline'},
        {'type': 'Aksiyon', 'title': 'Kimlik & Uç Nokta Merkezi', 'subtitle': 'AD, LDAP, endpoint, MFA ve lifecycle', 'url': '/kimlik-operasyonlari/', 'icon': 'mdi:account-key-outline'},
        {'type': 'Aksiyon', 'title': 'Kurulum & Sağlık Merkezi', 'subtitle': 'Canlıya alma, readiness ve ilk kurulum kontrolleri', 'url': '/kurulum-merkezi/', 'icon': 'mdi:progress-wrench'},
        {'type': 'Aksiyon', 'title': 'Derin Ağ Keşfi', 'subtitle': 'Ping, ARP ve raw socket tarama', 'url': '/ag-tarayici/', 'icon': 'mdi:radar'},
        {'type': 'Aksiyon', 'title': 'Raporlama Merkezi', 'subtitle': 'PDF ve CSV çıktıları', 'url': '/raporlar/', 'icon': 'mdi:file-chart-outline'},
        {'type': 'Aksiyon', 'title': 'Yönetici Bilgilendirme', 'subtitle': 'Tek sayfa özet, PDF ve Word çıktıları', 'url': '/yonetici-bilgilendirme/', 'icon': 'mdi:chart-box-outline'},
    ]

    results = []

    def add_result(result_type, title, subtitle, url, icon):
        results.append({
            'type': result_type,
            'title': str(title),
            'subtitle': str(subtitle or ''),
            'url': url,
            'icon': icon,
        })

    if not query:
        return JsonResponse({'results': quick_actions})

    if request.user.is_staff:
        from .models import (
            BusinessApplication, CameraDevice, MajorIncident, Runbook,
            RemoteAccessGrant, ReportTemplate,
        )

        for device in Device.objects.filter(models.Q(name__icontains=query) | models.Q(mac_address__icontains=query)).order_by('name')[:limit]:
            add_result('Cihaz', device.name, f"{device.device_type} · {device.mac_address or 'MAC yok'}", '/topoloji/', 'mdi:router-network')

        for asset in ITAsset.objects.filter(models.Q(name__icontains=query) | models.Q(serial_number__icontains=query) | models.Q(assigned_to__icontains=query)).order_by('name')[:limit]:
            add_result('Varlık', asset.name, f"{asset.get_asset_type_display()} · {asset.assigned_to or 'Zimmet yok'}", '/it-envanter/', 'mdi:laptop')

        ticket_qs = Ticket.objects.filter(models.Q(title__icontains=query) | models.Q(description__icontains=query)).order_by('-created_at')[:limit]
    else:
        ticket_qs = Ticket.objects.filter(created_by=request.user).filter(models.Q(title__icontains=query) | models.Q(description__icontains=query)).order_by('-created_at')[:limit]

    for ticket in ticket_qs:
        add_result('Ticket', ticket.title, f"{ticket.get_status_display()} · {ticket.get_priority_display()}", f'/talep/{ticket.id}/', 'mdi:ticket-confirmation-outline')

    for article in KnowledgeBaseArticle.objects.filter(models.Q(title__icontains=query) | models.Q(content__icontains=query)).order_by('-helpful_count')[:limit]:
        add_result('Bilgi Bankası', article.title, article.get_category_display(), '/bilgi-bankasi/', 'mdi:book-open-page-variant-outline')

    if request.user.is_staff:
        for app in BusinessApplication.objects.filter(models.Q(name__icontains=query) | models.Q(owner_department__icontains=query)).order_by('name')[:limit]:
            add_result('Uygulama', app.name, f"{app.get_app_type_display()} · {app.get_status_display()}", app.url or '/komuta-merkezi/', 'mdi:apps')

        for camera in CameraDevice.objects.filter(models.Q(name__icontains=query) | models.Q(location__icontains=query) | models.Q(ip_address__icontains=query)).order_by('name')[:limit]:
            add_result('Kamera', camera.name, f"{camera.location or 'Lokasyon yok'} · {camera.get_status_display()}", camera.stream_url or '/komuta-merkezi/', 'mdi:cctv')

        for incident in MajorIncident.objects.filter(title__icontains=query).order_by('-started_at')[:limit]:
            add_result('Major Incident', incident.title, f"{incident.get_severity_display()} · {incident.get_status_display()}", '/servis-surecleri/', 'mdi:alert-decagram-outline')

        for grant in RemoteAccessGrant.objects.filter(models.Q(employee_name__icontains=query) | models.Q(target_resource__icontains=query)).order_by('-created_at')[:limit]:
            add_result('Uzaktan Erişim', grant.employee_name, f"{grant.get_access_method_display()} · {grant.target_resource}", '/komuta-merkezi/', 'mdi:vpn')

        for runbook in Runbook.objects.filter(models.Q(title__icontains=query) | models.Q(steps__icontains=query)).order_by('title')[:limit]:
            add_result('Runbook', runbook.title, runbook.get_category_display(), '/servis-surecleri/', 'mdi:book-cog-outline')

        for report in ReportTemplate.objects.filter(title__icontains=query).order_by('title')[:limit]:
            add_result('Rapor', report.title, f"{report.get_report_type_display()} · {report.output_format}", '/komuta-merkezi/', 'mdi:file-chart-outline')

        for directory_user in DirectoryUser.objects.filter(
            models.Q(username__icontains=query) |
            models.Q(display_name__icontains=query) |
            models.Q(email__icontains=query) |
            models.Q(department__icontains=query)
        ).order_by('username')[:limit]:
            add_result('Directory Kullanıcısı', directory_user.display_name or directory_user.username, f"{directory_user.department or 'Departman yok'} · {directory_user.get_status_display()}", '/kimlik-operasyonlari/', 'mdi:account-key-outline')

        for endpoint in EndpointDevice.objects.filter(
            models.Q(hostname__icontains=query) |
            models.Q(serial_number__icontains=query) |
            models.Q(assigned_to_text__icontains=query)
        ).order_by('hostname')[:limit]:
            add_result('Endpoint', endpoint.hostname, f"{endpoint.get_device_type_display()} · {endpoint.get_status_display()}", '/kimlik-operasyonlari/', 'mdi:laptop')

        from .models import FactoryDepartment, ManagedDocument, FactorySite, DepartmentInventoryItem

        for site in FactorySite.objects.filter(
            models.Q(title__icontains=query) | models.Q(code__icontains=query) |
            models.Q(customer_name__icontains=query) | models.Q(custom_industry_label__icontains=query)
        ).order_by('title')[:limit]:
            add_result('Fabrika Tesisi', site.display_title, f"{site.industry_display} · {site.code}", f'/fabrika-portfoy-envanter/?site={site.id}', 'mdi:domain')

        for item in DepartmentInventoryItem.objects.filter(
            models.Q(title__icontains=query) | models.Q(reference_code__icontains=query) |
            models.Q(serial_number__icontains=query) | models.Q(category_label__icontains=query)
        ).select_related('factory_site', 'department').order_by('title')[:limit]:
            add_result('Bölüm Envanteri', item.title, f"{item.factory_site.display_title} · {item.category_display}", f'/fabrika-portfoy-envanter/?site={item.factory_site_id}&department={item.department_id or ""}', 'mdi:package-variant')

        for department in FactoryDepartment.objects.filter(
            models.Q(name__icontains=query) | models.Q(code__icontains=query) | models.Q(manager_name__icontains=query)
        ).order_by('name')[:limit]:
            add_result('Fabrika Departmanı', department.name, f"{department.get_department_type_display()} · {department.code}", f'/fabrika-komuta-merkezi/?department={department.id}', 'mdi:office-building-outline')

        for document in ManagedDocument.objects.filter(
            models.Q(title__icontains=query) |
            models.Q(reference_code__icontains=query) |
            models.Q(description__icontains=query) |
            models.Q(tags__icontains=query)
        ).order_by('-updated_at')[:limit]:
            add_result('Doküman', document.title, f"{document.get_category_display()} · {document.get_file_type_display()}", f'/fabrika-komuta-merkezi/?document={document.id}', 'mdi:file-document-outline')

        from .models import AssetQRTag
        for tag in AssetQRTag.objects.filter(
            models.Q(code__icontains=query) | models.Q(label__icontains=query) | models.Q(location__icontains=query)
        ).order_by('code')[:limit]:
            add_result('QR Etiket', tag.display_name, f"{tag.get_tag_type_display()} · {tag.code}", tag.resolved_url, 'mdi:qrcode-scan')

    return JsonResponse({'results': results[:30]})


# ========================================================
# --- ISI HARİTASI ALGORİTMASI ---
# ========================================================
def generate_heatmap_data():
    """Son 30 günün loglarını gün ve saat bazında sayarak Heatmap veri yapısına dönüştürür."""
    thirty_days_ago = timezone.now() - timedelta(days=30)
    recent_logs = SystemLog.objects.filter(created_at__gte=thirty_days_ago)
    
    heatmap_dict = {i: {h: 0 for h in range(24)} for i in range(7)}
    for log in recent_logs:
        loc_time = timezone.localtime(log.created_at)
        heatmap_dict[loc_time.weekday()][loc_time.hour] += 1
        
    days_tr = ['Pazartesi', 'Salı', 'Çarşamba', 'Perşembe', 'Cuma', 'Cumartesi', 'Pazar']
    heatmap_series = []
    for i in range(7):
        data_points = [{'x': f"{h}:00", 'y': heatmap_dict[i][h]} for h in range(24)]
        heatmap_series.append({'name': days_tr[i], 'data': data_points})
    return heatmap_series


@login_required
def dashboard(request):
    if not request.user.is_staff:
        return redirect('user_panel')
        
    # --- PERFORMANS OPTİMİZASYONU: PAGINATOR EKLENDİ ---
    device_list = Device.objects.all().order_by('-id')
    ticket_list = Ticket.objects.all().order_by('-created_at')
    
    device_paginator = Paginator(device_list, 10) 
    ticket_paginator = Paginator(ticket_list, 10)
    
    devices = device_paginator.get_page(request.GET.get('device_page'))
    tickets = ticket_paginator.get_page(request.GET.get('ticket_page'))
    
    root_devices = Device.objects.filter(parent_device__isnull=True)
    ip_addresses = IpAddress.objects.all()
    
    deadline = timezone.now().date() + timedelta(days=30)
    expiring_licenses = License.objects.filter(expiry_date__lte=deadline)
    kb_count = KnowledgeBaseArticle.objects.count()
    acik_bilet_sayisi = Ticket.objects.filter(status='Acik').count()

    # ========================================================
    # --- OLAY ODAKLI (EVENT-DRIVEN) TREND MATEMATİĞİ ---
    # ========================================================
    now = timezone.now()
    yesterday = now - timedelta(days=1)
    
    new_tickets_24h = Ticket.objects.filter(created_at__gte=yesterday).count()
    offline_device_count = Device.objects.filter(is_active=False).count()
    
    ticket_alert_class = 'danger' if acik_bilet_sayisi >= 3 else ('warning' if acik_bilet_sayisi > 0 else 'success')
    device_alert_class = 'danger' if offline_device_count > 0 else 'success'
    license_alert_class = 'danger' if expiring_licenses.exists() else 'success'

    # ========================================================
    # --- AIOps ZEKİ AKSİYON ÖNERİLERİ (OPERASYONEL ZEKA) ---
    # ========================================================
    action_suggestions = []
    
    critical_tickets = Ticket.objects.filter(status__in=['Acik', 'Inceleniyor'], priority='Kritik')
    if critical_tickets.exists():
        action_suggestions.append({
            'type': 'danger',
            'icon': 'mdi:alert-decagram',
            'title': 'Kritik Güvenlik İhlali / Arıza',
            'message': f'Sistemde acil müdahale bekleyen {critical_tickets.count()} kritik bilet var. Siber saldırı tespit edilmiş veya donanım çökmüş olabilir.',
            'action_text': 'Hemen İncele',
            'action_url': '/panel/'
        })
        
    offline_devices = Device.objects.filter(is_active=False)
    if offline_devices.exists():
        action_suggestions.append({
            'type': 'warning',
            'icon': 'mdi:router-wireless-off',
            'title': 'Bağlantı Kopukluğu',
            'message': f'Ağınızdaki {offline_devices.count()} cihaza erişilemiyor veya konfigürasyon hatası alındı. Disaster Recovery (DR) modülünü kullanın.',
            'action_text': 'Yedekten Dön',
            'action_url': '/yedekleme/'
        })
        
    if expiring_licenses.exists():
        action_suggestions.append({
            'type': 'info',
            'icon': 'mdi:certificate-outline',
            'title': 'Lisans Yenileme Uyarıları',
            'message': f'Önümüzdeki 30 gün içinde süresi dolacak {expiring_licenses.count()} lisans tespit edildi. SLA ihlali yememek için sözleşmeleri yenileyin.',
            'action_text': 'Envantere Git',
            'action_url': '/it-envanter/'
        })
        
    if not action_suggestions:
        action_suggestions.append({
            'type': 'success',
            'icon': 'mdi:shield-check',
            'title': 'Sistem Stabil',
            'message': 'Şu an ağınızda ve donanımlarınızda hiçbir kritik kriz bulunmuyor. AIOps arka planda izlemeye devam ediyor.',
            'action_text': 'Canlı İzleme',
            'action_url': '/monitor/'
        })

    device_labels, device_data = [], []
    for type_code, type_name in Device.DEVICE_TYPES:
        count = Device.objects.filter(device_type=type_code).count()
        if count > 0:
            device_labels.append(type_name)
            device_data.append(count)

    ticket_labels = ['Açık', 'İnceleniyor', 'Çözüldü']
    ticket_data = [acik_bilet_sayisi, Ticket.objects.filter(status='Inceleniyor').count(), Ticket.objects.filter(status='Cozuldu').count()]

    context = {
        'devices': devices, 'root_devices': root_devices, 'tickets': tickets,
        'ip_addresses': ip_addresses, 'cihaz_sayisi': devices.paginator.count,
        'suresi_biten_lisanslar': expiring_licenses.count(), 'expiring_licenses': expiring_licenses,
        'kb_count': kb_count, 'acik_bilet_sayisi': acik_bilet_sayisi, 
        'device_labels': json.dumps(device_labels), 'device_data': json.dumps(device_data),
        'ticket_labels': json.dumps(ticket_labels), 'ticket_data': json.dumps(ticket_data),
        'heatmap_data': json.dumps(generate_heatmap_data()), 
        'action_suggestions': action_suggestions, 
        'new_tickets_24h': new_tickets_24h,
        'offline_device_count': offline_device_count,
        'ticket_alert_class': ticket_alert_class,
        'device_alert_class': device_alert_class,
        'license_alert_class': license_alert_class,
    }
    return render(request, 'dashboard.html', context)

@login_required
def dashboard_refresh(request):
    if not request.user.is_staff:
        return JsonResponse({'status': 'error', 'message': 'Unauthorized'}, status=403)

    now = timezone.now()
    yesterday = now - timedelta(days=1)
    limit_date = now.date() + timedelta(days=30)
    
    acik_bilet_sayisi = Ticket.objects.filter(status='Acik').count()
    offline_device_count = Device.objects.filter(is_active=False).count()
    suresi_biten_lisanslar = License.objects.filter(expiry_date__lte=limit_date).count()

    device_labels = []
    device_data = []
    for type_code, type_name in Device.DEVICE_TYPES:
        count = Device.objects.filter(device_type=type_code).count()
        if count > 0:
            device_labels.append(type_name)
            device_data.append(count)

    response_payload = {
        'status': 'ok',
        'device_count': Device.objects.count(),
        'open_ticket_count': acik_bilet_sayisi,
        'license_alert_count': suresi_biten_lisanslar,
        'kb_count': KnowledgeBaseArticle.objects.count(),
        'new_tickets_24h': Ticket.objects.filter(created_at__gte=yesterday).count(),
        'offline_device_count': offline_device_count,
        'ticket_alert_class': 'danger' if acik_bilet_sayisi >= 3 else ('warning' if acik_bilet_sayisi > 0 else 'success'),
        'device_alert_class': 'danger' if offline_device_count > 0 else 'success',
        'license_alert_class': 'danger' if suresi_biten_lisanslar > 0 else 'success',
        'device_labels': device_labels,
        'device_data': device_data,
        'ticket_labels': ['Açık', 'İnceleniyor', 'Çözüldü'],
        'ticket_data': [
            acik_bilet_sayisi,
            Ticket.objects.filter(status='Inceleniyor').count(),
            Ticket.objects.filter(status='Cozuldu').count(),
        ],
        'heatmap_data': generate_heatmap_data(), 
        'root_devices': list(Device.objects.filter(parent_device__isnull=True).order_by('-id').values('name', 'mac_address', 'is_active')[:4]),
    }
    return JsonResponse(response_payload)


# ========================================================
# --- NESNE BAZLI YETKİLENDİRİLMİŞ ENVANTER GÖRÜNÜMÜ ---
# ========================================================
@login_required
def it_inventory_view(request):
    if not request.user.is_staff:
        return redirect('user_panel')
    if request.method == 'POST':
        if 'submit_asset' in request.POST:
            asset_form = ITAssetForm(request.POST)
            if asset_form.is_valid():
                asset_form.save()
                messages.success(request, "Yeni donanım envantere başarıyla eklendi.")
                return redirect('it_inventory')
        elif 'submit_license' in request.POST:
            license_form = LicenseForm(request.POST)
            if license_form.is_valid():
                license_form.save()
                messages.success(request, "Yazılım lisansı başarıyla kaydedildi.")
                return redirect('it_inventory')
        elif 'submit_contract' in request.POST:
            VendorContract.objects.create(
                title=request.POST.get('title'), vendor_name=request.POST.get('vendor_name'), 
                contract_type=request.POST.get('contract_type'), sla_level=request.POST.get('sla_level'), 
                start_date=request.POST.get('start_date'), end_date=request.POST.get('end_date'),
                cost=request.POST.get('cost') or 0, description=request.POST.get('description')
            )
            messages.success(request, "Tedarikçi sözleşmesi başarıyla kaydedildi.")
            return redirect('it_inventory')

    # --- NESNE BAZLI YETKİLENDİRME (OLP) ---
    if request.user.is_superuser:
        assets_qs = ITAsset.objects.all()
        licenses_qs = License.objects.all()
        contracts_qs = VendorContract.objects.all()
    else:
        assets_qs = get_objects_for_user(request.user, 'inventory.view_itasset')
        licenses_qs = get_objects_for_user(request.user, 'inventory.view_license')
        contracts_qs = get_objects_for_user(request.user, 'inventory.view_vendorcontract')

    assets = Paginator(assets_qs.order_by('-id'), 15).get_page(request.GET.get('asset_page'))
    licenses = Paginator(licenses_qs.order_by('expiry_date'), 15).get_page(request.GET.get('license_page'))
    contracts = Paginator(contracts_qs.order_by('end_date'), 15).get_page(request.GET.get('contract_page'))

    context = {
        'assets': assets, 'licenses': licenses, 'contracts': contracts,
        'asset_form': ITAssetForm(), 'license_form': LicenseForm(),
    }
    return render(request, 'it_inventory.html', context)


@login_required
@role_required(['Ağ Ekibi', 'Yönetim'])
def config_generator(request):
    generated_config = None
    if request.method == 'POST':
        action = request.POST.get('action', 'generate')
        vendor = request.POST.get('vendor', 'cisco')
        device_type = request.POST.get('device_type', 'switch')
        hostname = request.POST.get('hostname', 'NetArch-Device')

        generated_config = generate_device_config(
            vendor, device_type, hostname, request.POST.get('vlan_id'), request.POST.get('vlan_name'), 
            request.POST.get('interface_name'), request.POST.get('enable_ospf') == 'yes', 
            request.POST.get('ospf_network', ''), request.POST.get('ospf_area', '0'), 
            request.POST.get('enable_port_security') == 'yes', request.POST.get('mac_limit', '1')
        )

        if action == 'push_config':
            target_ip = request.POST.get('target_ip')
            ChangeRequest.objects.create(
                title=f"{hostname} - Otomatik Konfigürasyon",
                target_ip=target_ip, vendor=vendor, config_payload=generated_config,
                requester=request.user, status='pending'
            )
            SystemLog.objects.create(user=request.user, action='SYSTEM', details=f"ITIL: {target_ip} cihazı için değişiklik talep edildi. CAB onayı bekleniyor.")
            messages.info(request, "🛡️ ITIL Kuralı: Sistem güvenliği gereği konfigürasyonlar doğrudan cihaza yazılamaz. Talebiniz 'Değişiklik Onay Havuzuna (CAB)' iletildi. Yetkili onayından sonra uygulanacaktır.")

        elif action == 'download_cfg':
            response = HttpResponse(generated_config, content_type='text/plain')
            response['Content-Disposition'] = f'attachment; filename="{hostname}_backup.cfg"'
            return response

    return render(request, 'generator.html', {'generated_config': generated_config})

@login_required
@role_required(['Ağ Ekibi', 'Sistem Ekibi', 'Yönetim']) 
def device_backup_view(request):
    if not request.user.is_staff:
        return redirect('user_panel')
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'restore_backup':
            backup_obj = get_object_or_404(DeviceBackup, id=request.POST.get('backup_id'))
            device = backup_obj.device
            target_ip = device.ipaddress_set.first().address if device.ipaddress_set.exists() else '192.168.1.1'
            success, msg = push_config_to_device(
                ip_address=target_ip, username=device.ssh_user or 'admin',
                password=decrypt_vault_password(device.ssh_password) or 'admin',
                enable_secret=decrypt_vault_password(device.enable_password) or '',
                vendor=device.vendor or 'cisco', config_payload=backup_obj.config_text
            )
            if success:
                SystemLog.objects.create(user=request.user, action='SYSTEM', details=f"🚀 DISASTER RECOVERY: {device.name} cihazına eski yedek geri yüklendi!")
                messages.success(request, "✅ Disaster Recovery Başarılı: Eski konfigürasyon cihaza yazıldı ve ağ saniyeler içinde kurtarıldı!")
            else:
                messages.error(request, f"❌ Kurtarma Başarısız: {msg}")
            return redirect('device_backup')
        else:
            success, msg = backup_device_config(
                device_obj=get_object_or_404(Device, id=request.POST.get('device_id')),
                device_ip=request.POST.get('target_ip'), username=request.POST.get('ssh_user'),
                password=request.POST.get('ssh_pass'), vendor=request.POST.get('vendor'), user=request.user
            )
            if success:
                messages.success(request, f"🚀 {msg}")
            else:
                messages.error(request, f"❌ {msg}")
            return redirect('device_backup')

    recent_backups = Paginator(DeviceBackup.objects.all().order_by('-created_at'), 15).get_page(request.GET.get('backup_page'))
    return render(request, 'backup.html', {'devices': Device.objects.filter(is_active=True), 'recent_backups': recent_backups})

@login_required
@role_required(['Sistem Ekibi', 'Yönetim'])
def subnet_calculator(request):
    results = None
    if request.method == 'POST':
        results = calculate_subnets(request.POST.get('network'), request.POST.get('prefix'))
    return render(request, 'subnet_calc.html', {'results': results})

@login_required
@role_required(['Sistem Ekibi', 'Yönetim'])
def network_scanner(request):
    results = None
    selected_method = 'hybrid'
    if request.method == 'POST':
        network = request.POST.get('network')
        method = request.POST.get('method', 'hybrid')
        selected_method = method
        results = scan_network(network, method=method)
        scan = NetworkScan.objects.create(
            requested_by=request.user,
            network=network,
            method=method,
            total_hosts=results.get('total_scanned', 0),
            active_hosts=len(results.get('active_ips', [])),
            duration_ms=results.get('duration_ms', 0),
            error=results.get('error', ''),
        )
        for host in results.get('active_ips', []):
            NetworkScanHost.objects.create(
                scan=scan,
                ip_address=host.get('ip'),
                mac_address=host.get('mac', ''),
                hostname=host.get('hostname', ''),
                vendor=host.get('vendor', ''),
                detected_by=host.get('detected_by', ''),
                latency_ms=host.get('latency_ms'),
                raw_socket_open=host.get('raw_socket_open', False),
            )
        results['scan_id'] = scan.id
    recent_scans = NetworkScan.objects.select_related('requested_by').order_by('-created_at')[:5]
    return render(request, 'scanner.html', {'results': results, 'recent_scans': recent_scans, 'selected_method': selected_method})

@login_required
@role_required(['Ağ Ekibi', 'Sistem Ekibi', 'Yönetim'])
def export_csv(request):
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="devices.csv"'
    response.write('\ufeff')
    writer = csv.writer(response)
    writer.writerow(['Name', 'Type', 'Vendor', 'IP Address', 'Status'])
    for device in Device.objects.all().order_by('name'):
        ip_addr = device.ipaddress_set.first().address if device.ipaddress_set.exists() else ''
        status = 'Active' if getattr(device, 'is_active', True) else 'Inactive'
        writer.writerow([device.name, device.device_type, device.vendor, ip_addr, status])
    return response

@login_required
@role_required(['Ağ Ekibi', 'Sistem Ekibi', 'Yönetim'])
def export_pdf(request):
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="devices.pdf"'
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    elements = [Paragraph('Device Inventory Export', styles['Heading1']), Spacer(1, 12)]
    data = [['Name', 'Type', 'Vendor', 'IP Address', 'Status']]
    for device in Device.objects.all().order_by('name'):
        ip_addr = device.ipaddress_set.first().address if device.ipaddress_set.exists() else ''
        status = 'Active' if getattr(device, 'is_active', True) else 'Inactive'
        data.append([device.name, str(device.device_type), str(device.vendor), ip_addr, status])
    table = Table(data, repeatRows=1)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0b5394')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
    ]))
    elements.append(table)
    doc.build(elements)
    response.write(buffer.getvalue())
    buffer.close()
    return response

@login_required
@role_required(['Sistem Ekibi', 'Yönetim'])
def visual_ipam(request):
    ip_form = IpAddressForm(request.POST or None)
    error_msg = None
    network_input = request.GET.get('network', '10.0.0.0/24')
    if request.method == 'POST':
        if ip_form.is_valid():
            ip_form.save()
            messages.success(request, 'IP adresi başarıyla atandı ve kayıt edildi.')
            return redirect('visual_ipam')

    ip_grid = []
    try:
        network = ipaddress.ip_network(network_input.strip(), strict=False)
        used_mapping = {str(ip.address): ip.device.name if ip.device else 'Zimmetli' for ip in IpAddress.objects.select_related('device')}
        for ip in network.hosts():
            ip_str = str(ip)
            if ip_str in used_mapping:
                ip_grid.append({'ip': ip_str, 'status': 'used', 'device': used_mapping[ip_str], 'type': 'Atanmış'})
            else:
                ip_grid.append({'ip': ip_str, 'status': 'free', 'device': 'BOŞ', 'type': 'Uygun'})
    except ValueError as exc:
        ip_grid = []
        error_msg = str(exc)

    recommendations = {}
    free_ips = [item['ip'] for item in ip_grid if item['status'] == 'free']
    if free_ips:
        recommendations['İlk Boş IP'] = free_ips[0]

    return render(request, 'ipam.html', {
        'ip_form': ip_form,
        'ip_grid': ip_grid,
        'network_input': network_input,
        'recommendations': recommendations,
        'error_msg': error_msg,
    })

@login_required
def live_monitor(request):
    if not request.user.is_staff:
        return redirect('user_panel')
    devices = Device.objects.filter(is_active=True).order_by('name')
    return render(request, 'monitor.html', {'devices': devices})


@login_required
@role_required(['Ağ Ekibi', 'Sistem Ekibi', 'Yönetim'])
def get_monitor_data(request):
    import random
    
    target_ip = request.GET.get('ip', '127.0.0.1')
    
    try:
        if target_ip in ['127.0.0.1', 'localhost']:
            try:
                import psutil
                cpu_val = round(psutil.cpu_percent(interval=0.1), 1)
                ram_val = round(psutil.virtual_memory().percent, 1)
            except ImportError:
                cpu_val = random.randint(10, 30)
                ram_val = random.randint(40, 60)
                
            latency = "<1"
            status = "success"
        else:
            cpu_val = random.randint(15, 65)
            ram_val = random.randint(40, 85)
            latency = str(random.randint(2, 45))
            status = "success"
            
        payload = {
            'status': status,
            'ip': target_ip,
            'cpu': cpu_val,
            'ram': ram_val,
            'traffic_in': round(random.uniform(10.5, 120.0), 1),
            'traffic_out': round(random.uniform(5.1, 85.0), 1),
            'latency': latency,
        }
        
    except Exception as e:
        payload = {
            'status': 'error',
            'message': str(e)
        }
        
    return JsonResponse(payload)

@login_required
@role_required(['Sistem Ekibi', 'Yönetim'])
def system_logs_view(request):
    current_filter = request.GET.get('action', '')
    logs = SystemLog.objects.all()
    if current_filter:
        logs = logs.filter(action=current_filter)
    logs = Paginator(logs.order_by('-created_at'), 20).get_page(request.GET.get('page'))
    return render(request, 'system_logs.html', {
        'logs': logs,
        'current_filter': current_filter,
        'action_choices': SystemLog.ACTION_CHOICES,
    })

@login_required
@role_required(['Ağ Ekibi', 'Yönetim'])
def port_mapping_view(request, device_id):
    device = get_object_or_404(Device, id=device_id)
    if request.method == 'POST':
        port = get_object_or_404(Port, id=request.POST.get('port_id'), device=device)
        port.status = request.POST.get('status', port.status)
        connected_asset_id = request.POST.get('connected_asset')
        port.connected_asset = ITAsset.objects.filter(id=connected_asset_id).first() if connected_asset_id else None
        port.description = request.POST.get('description', port.description)
        port.save()
        messages.success(request, 'Port haritası bilgileri başarıyla güncellendi.')
        return redirect('port_mapping', device_id=device.id)

    ports = Port.objects.filter(device=device).order_by('port_number')
    assets = ITAsset.objects.filter(status='active')
    return render(request, 'port_mapping.html', {
        'device': device,
        'ports': ports,
        'assets': assets,
    })

@login_required
@role_required(['Ağ Ekibi', 'Yönetim'])
def port_mapping_list_view(request):
    devices = Device.objects.annotate(port_count=Count('ports')).filter(port_count__gt=0).order_by('name')
    return render(request, 'port_mapping_list.html', {'devices': devices})

@login_required
@role_required(['Sistem Ekibi', 'Yönetim'])
def sync_ad_users(request):
    from .enterprise_views import run_directory_sync

    connection = DirectoryConnection.objects.filter(sync_enabled=True).order_by('name').first()
    if not connection:
        connection = DirectoryConnection.objects.order_by('name').first()

    ok, message = run_directory_sync(connection, actor=request.user)
    if ok:
        messages.success(request, message)
    else:
        SystemLog.objects.create(user=request.user, action='SYSTEM', details=f'Directory sync tamamlanamadı: {message}')
        messages.warning(request, message)
    return redirect('custom_admin')

@login_required
def knowledge_base_view(request):
    query = request.GET.get('q', '').strip()
    articles = KnowledgeBaseArticle.objects.all()
    if query:
        articles = articles.filter(
            models.Q(title__icontains=query) | models.Q(content__icontains=query)
        )
    if request.method == 'POST' and request.user.is_staff:
        title = request.POST.get('title')
        content = request.POST.get('content')
        category = request.POST.get('category', 'other')
        if title and content:
            KnowledgeBaseArticle.objects.create(
                title=title,
                content=content,
                category=category,
                author=request.user,
            )
            messages.success(request, 'Yeni bilgi bankası makalesi başarıyla eklendi.')
            return redirect('knowledge_base')

    return render(request, 'knowledge_base.html', {
        'articles': articles.order_by('-created_at'),
        'query': query,
        'categories': KnowledgeBaseArticle.CATEGORY_CHOICES,
    })

@login_required
def search_kb_api(request):
    q = request.GET.get('q', '').strip()
    results = []
    if q:
        articles = KnowledgeBaseArticle.objects.filter(
            models.Q(title__icontains=q) | models.Q(content__icontains=q)
        )[:20]
        for article in articles:
            results.append({
                'id': article.id,
                'title': article.title,
                'category': article.get_category_display(),
                'excerpt': article.content[:180] + ('...' if len(article.content) > 180 else ''),
            })
    return JsonResponse({'results': results})

@login_required
@role_required(['Ağ Ekibi', 'Yönetim'])
def config_diff_view(request, device_id):
    device = get_object_or_404(Device, id=device_id)
    backups = DeviceBackup.objects.filter(device=device).order_by('-created_at')
    b1_id = request.GET.get('b1')
    b2_id = request.GET.get('b2')
    diff_lines = []
    if b1_id and b2_id:
        b1 = backups.filter(id=b1_id).first()
        b2 = backups.filter(id=b2_id).first()
        if b1 and b2:
            for line in difflib.unified_diff(
                b1.config_text.splitlines(),
                b2.config_text.splitlines(),
                fromfile=f'Yedek-{b1.id}',
                tofile=f'Yedek-{b2.id}',
                lineterm=''
            ):
                if line.startswith('+++') or line.startswith('---') or line.startswith('@@'):
                    diff_type = 'header'
                elif line.startswith('+') and not line.startswith('+++'):
                    diff_type = 'add'
                elif line.startswith('-') and not line.startswith('---'):
                    diff_type = 'remove'
                else:
                    diff_type = 'info'
                diff_lines.append({'text': line, 'type': diff_type})

    return render(request, 'diff.html', {
        'device': device,
        'backups': backups,
        'diff_lines': diff_lines,
        'b1_id': int(b1_id) if b1_id else None,
        'b2_id': int(b2_id) if b2_id else None,
    })


@login_required
@role_required(['Ağ Ekibi', 'Yönetim'])
def rack_elevation_view(request):
    if request.user.is_superuser:
        devices_qs = Device.objects.filter(rack_name__isnull=False).exclude(rack_name='')
    else:
        devices_qs = get_objects_for_user(request.user, 'inventory.view_device').filter(rack_name__isnull=False).exclude(rack_name='')

    racks = {}
    for dev in devices_qs.order_by('rack_name', '-position_u'):
        racks.setdefault(dev.rack_name, []).append(dev)
        
    return render(request, 'rack.html', {
        'racks': racks,
        'u_range': range(42, 0, -1),
    })

@login_required
def network_topology(request):
    if not request.user.is_staff:
        return redirect('user_panel')
    nodes, edges = [], []
    for d in Device.objects.all():
        shape, color = 'dot', '#0ea5e9'
        if 'router' in str(d.device_type).lower():
            shape, color = 'diamond', '#ef4444'
        elif 'switch' in str(d.device_type).lower():
            shape, color = 'box', '#14b8a6'
        nodes.append({'id': d.id, 'label': d.name, 'shape': shape, 'color': color})
        if d.parent_device:
            edges.append({'from': d.parent_device.id, 'to': d.id, 'arrows': 'to', 'color': {'color': '#64748b'}})

    return render(request, 'topology.html', {'nodes_json': json.dumps(nodes), 'edges_json': json.dumps(edges)})


def register_page(request):
    from django.conf import settings as django_settings
    if not getattr(django_settings, 'ALLOW_PUBLIC_REGISTRATION', False):
        from django.http import Http404
        raise Http404('Kayıt kapalı. Lütfen yöneticinizle iletişime geçin.')
    if request.user.is_authenticated:
        return redirect('dashboard')
    form = PublicRegistrationForm()
    if request.method == 'POST':
        form = PublicRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            if request.POST.get('password'):
                user.set_password(request.POST.get('password'))
            user.save()
            from .helpdesk import assign_customer_role
            assign_customer_role(user)
            from django.conf import settings as _settings
            preferred_backend = 'django.contrib.auth.backends.ModelBackend'
            if preferred_backend not in _settings.AUTHENTICATION_BACKENDS:
                preferred_backend = _settings.AUTHENTICATION_BACKENDS[0]
            user.backend = preferred_backend
            login(request, user)
            return redirect('user_panel')
    return render(request, 'register.html', {'form': form})

@login_required
def user_panel(request):
    if request.user.is_staff:
        return redirect('dashboard')
    form = CustomerTicketForm()
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'catalog_request':
            catalog_item = get_object_or_404(ServiceCatalogItem, id=request.POST.get('catalog_id'))
            Ticket.objects.create(
                title=f"Hizmet Talebi: {catalog_item.title}",
                description=f"Otomatik Hizmet İsteği.\n\nHizmet Açıklaması: {catalog_item.description}",
                priority='Orta', category='Diger', status='Acik', created_by=request.user
            )
            messages.success(request, f"'{catalog_item.title}' talebiniz başarıyla oluşturuldu.")
            return redirect('user_panel')
        else:
            form = CustomerTicketForm(request.POST)
            if form.is_valid():
                dlp_events = inspect_text_for_dlp(
                    f"{form.cleaned_data.get('title', '')}\n{form.cleaned_data.get('description', '')}",
                    user=request.user,
                    source='customer_ticket',
                    block=True,
                )
                if has_blocking_dlp_event(dlp_events):
                    messages.error(request, "Talep metni hassas veri içerdiği için DLP politikası tarafından engellendi.")
                    return redirect('user_panel')
                ticket = form.save(commit=False)
                ticket.created_by = request.user
                ticket.save()
                messages.success(request, "Destek talebiniz başarıyla alındı.")
                return redirect('user_panel')
    context = {
        'form': form, 
        'tickets': Ticket.objects.filter(created_by=request.user).order_by('-created_at'),
        'catalog_items': ServiceCatalogItem.objects.all().order_by('category', 'title') 
    }
    return render(request, 'user_panel.html', context)


@login_required
@role_required(['Ağ Ekibi', 'Yönetim']) 
def bulk_config_generator(request):
    if not request.user.is_staff:
        return redirect('dashboard')
    if request.method == 'POST':
        selected_device_ids = request.POST.getlist('device_ids')
        config_payload = request.POST.get('config_payload')
        
        if not selected_device_ids or not config_payload:
            messages.error(request, "Cihaz ve konfigürasyon alanı boş bırakılamaz.")
            return redirect('bulk_config_generator')
            
        # Ana toplu işlem kaydını oluşturuyoruz
        bulk_cr = ChangeRequest.objects.create(
            title=f"Toplu Yapılandırma - {timezone.now().strftime('%d.%m.%y %H:%M')}",
            requester=request.user,
            status='pending',
            config_payload=config_payload
        )
        bulk_cr.target_devices.set(selected_device_ids)
        
        # YENİ: Tek tek geciktirmek yerine tüm listeyi işleyecek ana paralel görevi tetikliyoruz
        from .tasks import bulk_push_config_to_devices
        bulk_push_config_to_devices.delay(bulk_cr.id)
            
        SystemLog.objects.create(
            user=request.user, 
            action='CONFIG', 
            details=f"Toplu İşlem Başlatıldı: {len(selected_device_ids)} cihaz asenkron kuyruğa alındı. CR ID: #{bulk_cr.id}"
        )
        messages.success(request, f"Eşzamanlı pipeline tetiklendi! {len(selected_device_ids)} cihaz için işlemler arka planda paralel olarak yürütülüyor. Durumu denetim loglarından izleyebilirsiniz.")
        return redirect('custom_admin')
    
    return render(request, 'bulk_generator.html', {'devices': Device.objects.filter(is_active=True).order_by('name')})


@login_required
def custom_admin(request):
    if not request.user.is_staff:
        return redirect('dashboard')
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'approve_change':
            change_req = get_object_or_404(ChangeRequest, id=request.POST.get('request_id'))
            change_req.reviewed_by = request.user
            if request.POST.get('decision') == 'reject':
                change_req.status = 'rejected'
                change_req.execution_log = "Talep BT Yöneticisi tarafından reddedildi."
                messages.warning(request, f"ITIL: Talep reddedildi ({change_req.target_ip}).")
                change_req.save()
            else:
                target_ip = change_req.target_ip
                ip_obj = IpAddress.objects.filter(address=target_ip).first()
                device = ip_obj.device if ip_obj else None
                if device:
                    success, msg = push_config_to_device(
                        ip_address=target_ip, username=device.ssh_user or 'admin',
                        password=decrypt_vault_password(device.ssh_password) or 'admin',
                        enable_secret=decrypt_vault_password(device.enable_password) or '',
                        vendor=change_req.vendor or device.vendor, config_payload=change_req.config_payload,
                        device_obj=device, change_request_id=change_req.id
                    )
                    if success:
                        change_req.status = 'approved'
                        change_req.execution_log = "BAŞARILI: Konfigürasyon cihaza güvenli kanaldan yazıldı."
                        device.monitoring_mode = 'monitoring'
                        device.save(update_fields=['monitoring_mode'])
                        messages.success(request, f"✅ ITIL Onayı Başarılı: {target_ip} adresine uygulandı!")
                    else:
                        change_req.status = 'failed'
                        change_req.execution_log = f"BAŞARISIZ: {msg}"
                        messages.error(request, f"❌ Konfigürasyon uygulanamadı! Hata: {msg}")
                        device.monitoring_mode = 'error'
                        device.is_active = False
                        device.save(update_fields=['monitoring_mode', 'is_active'])
                        Ticket.objects.create(
                            title=f"🚨 KRİTİK: {device.name} Konfigürasyon Hatası",
                            description=f"Hata Detayı: {msg}", priority='Kritik', category='Ag', status='Acik', device=device
                        )
                change_req.save()
            return redirect('custom_admin')

        elif action == 'submit_ticket':
            form = TicketForm(request.POST)
            if form.is_valid():
                ticket = form.save(commit=False)
                ticket.created_by = request.user
                ticket.save()
                messages.success(request, f'Talep #{ticket.id} oluşturuldu.')
            else:
                messages.error(request, 'Talep formu geçersiz.')
            return redirect('custom_admin')

        elif action == 'edit_ticket':
            ticket = get_object_or_404(Ticket, pk=request.POST.get('ticket_id'))
            form = TicketForm(request.POST, instance=ticket)
            if form.is_valid():
                form.save()
                messages.success(request, f'Talep #{ticket.id} güncellendi.')
            return redirect('custom_admin')

        elif action == 'submit_user':
            form = RegisterUserForm(request.POST)
            if form.is_valid():
                user = form.save()
                from .helpdesk import ensure_default_groups
                ensure_default_groups()
                role = request.POST.get('role', 'Müşteri')
                from django.contrib.auth.models import Group
                group = Group.objects.filter(name=role).first()
                if group:
                    user.groups.add(group)
                from .models import UserProfile
                UserProfile.objects.get_or_create(user=user)
                messages.success(request, f'Kullanıcı oluşturuldu: {user.username}')
            else:
                messages.error(request, 'Kullanıcı formu geçersiz.')
            return redirect('custom_admin')

        elif action == 'submit_device':
            form = DeviceForm(request.POST)
            if form.is_valid():
                form.save()
                messages.success(request, 'Cihaz eklendi.')
            return redirect('custom_admin')

    context = {
        'device_form': DeviceForm(), 'ticket_form': TicketForm(), 'user_form': RegisterUserForm(),
        'devices': Device.objects.all().order_by('-id'),
        'tickets': Ticket.objects.select_related('created_by', 'assigned_to').all().order_by('-created_at'),
        'users': User.objects.prefetch_related('groups').all().order_by('-date_joined'),
        'change_requests': ChangeRequest.objects.all().order_by('-created_at'),
        'ticket_categories': TicketCategory.objects.filter(is_active=True),
    }
    return render(request, 'custom_admin.html', context)


# ========================================================
# --- WEBHOOK ---
# ========================================================
@csrf_exempt
def device_alert_webhook(request):
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Sadece POST desteklenir.'}, status=405)

    allowed_ips = getattr(settings, 'WEBHOOK_ALLOWED_IPS', [])
    client_ip = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR', '')).split(',')[0].strip()
    if allowed_ips and client_ip not in allowed_ips:
        SystemLog.objects.create(
            action='SYSTEM',
            details=f"Webhook IP reddedildi: {client_ip}"
        )
        return JsonResponse({'status': 'error', 'message': 'Yetkisiz IP adresi.'}, status=403)

    provided_key = request.headers.get('X-API-Key') or request.headers.get('Authorization')
    if provided_key and provided_key.startswith('Bearer '):
        provided_key = provided_key.split(' ')[1]

    expected_key = getattr(settings, 'WAZUH_API_KEY', '')
    if not expected_key or provided_key != expected_key:
        SystemLog.objects.create(
            action='SYSTEM', 
            details=f"🚨 GÜVENLİK İHLALİ: Webhook adresine geçersiz şifre ile erişim denemesi! Gelen Key: {provided_key}"
        )
        return JsonResponse({'status': 'error', 'message': 'Yetkisiz erişim. Geçersiz API Key.'}, status=401)

    try:
        payload = json.loads(request.body.decode('utf-8')) if request.body else request.POST.dict()
    except Exception as exc:
        return JsonResponse({'status': 'error', 'message': f'Geçersiz JSON: {exc}'}, status=400)

    source_ip = payload.get('ip') or payload.get('source_ip') or payload.get('device_ip')
    message = payload.get('message') or payload.get('alert') or payload.get('log') or ''
    attacker_ip = payload.get('attacker_ip') or payload.get('source_attack_ip')

    if not source_ip and not attacker_ip:
        return JsonResponse({'status': 'error', 'message': 'En az bir IP adresi gereklidir.'}, status=400)

    ip_record = None
    device = None
    if source_ip:
        ip_record = IpAddress.objects.filter(address=source_ip).select_related('device').first()
        device = ip_record.device if ip_record else None

    alert_text = message.strip() or 'Webhook üzerinden alarm alındı.'
    suspicious_keywords = ['failed', 'denied', 'brute-force', 'authentication failure', 'login failed', 'invalid user', 'error', 'critical']
    alert_severity = 'critical' if any(keyword in alert_text.lower() for keyword in suspicious_keywords) else 'info'

    SystemLog.objects.create(
        action='SYSTEM',
        details=f"Webhook Alarmı: Kaynak IP={source_ip or 'bilinmiyor'}, Cihaz={device.name if device else 'bilinmiyor'}, Mesaj={alert_text}"
    )

    ticket = None
    if alert_severity == 'critical':
        ticket = Ticket.objects.create(
            title=f"🚨 GÜVENLİK ALARMI: {source_ip or 'bilinmiyor'}",
            description=alert_text,
            priority='Kritik',
            category='Ag',
            status='Acik',
            device=device
        )
        SystemLog.objects.create(action='TICKET', details=f"Webhook alarmı için bilet oluşturuldu: #{ticket.id}")

    if attacker_ip:
        if device:
            active_response_block_ip.delay(attacker_ip, device.id)
            SystemLog.objects.create(
                action='SYSTEM',
                details=f"Active Response tetiklendi: {attacker_ip} engelleme görevi kuyruğa alındı."
            )

    response_data = {'status': 'ok', 'message': 'Alert işlendi.', 'severity': alert_severity}
    if ticket:
        response_data['ticket_id'] = ticket.id
    return JsonResponse(response_data)


def _count_open_tickets():
    return Ticket.objects.exclude(status__in=['Kapatildi', 'Cozuldu']).count()


def build_executive_report_context():
    """Yöneticiye verilecek tek sayfalık OmniOps operasyon özeti."""
    from .models import (
        AccessRequest, BackupJobMonitor, BusinessApplication, CameraDevice,
        ChangeCalendarEvent, ComplianceControl, ConsumableItem, DLPEvent,
        DocumentOutputJob, EmployeeITProcess, FactoryArea, IntegrationHealthCheck,
        MajorIncident, PrinterFleetItem, ProcurementRequest, RemoteAccessGrant,
        Runbook, ServiceDependency, VendorSupportCase,
        DirectoryGroup, DirectoryUser, EndpointDevice, IdentityLifecycleTask,
        FactoryDepartment, FactoryZone, ManagedDocument, FactoryITAssetRelation,
        AssetQRTag, ERPConnection,
    )

    now = timezone.now()
    today = now.date()
    next_30_days = today + timedelta(days=30)

    low_stock_count = sum(1 for item in ConsumableItem.objects.all() if item.is_low_stock)
    printer_alert_count = sum(1 for item in PrinterFleetItem.objects.all() if item.needs_consumable)
    active_remote_count = sum(1 for grant in RemoteAccessGrant.objects.all() if grant.is_active_now)
    unhealthy_backup_count = sum(1 for job in BackupJobMonitor.objects.all() if job.is_unhealthy)
    unhealthy_integrations = sum(1 for check in IntegrationHealthCheck.objects.all() if check.is_unhealthy)

    open_ticket_count = _count_open_tickets()
    critical_incident_count = MajorIncident.objects.exclude(status='resolved').count()
    security_events_count = DLPEvent.objects.count()
    compliance_open_count = ComplianceControl.objects.exclude(status='compliant').count()
    directory_attention_count = sum(1 for user in DirectoryUser.objects.all() if user.needs_attention)
    endpoint_alert_count = sum(1 for endpoint in EndpointDevice.objects.all() if not endpoint.is_compliant or endpoint.is_stale)
    open_identity_tasks = IdentityLifecycleTask.objects.exclude(status__in=['done', 'cancelled']).count()
    review_documents_count = sum(1 for doc in ManagedDocument.objects.all() if doc.needs_review)
    offline_camera_count = CameraDevice.objects.filter(status='offline').count()
    erp_error_count = ERPConnection.objects.filter(last_sync_status='error').count()
    active_qr_tag_count = AssetQRTag.objects.filter(is_active=True).count()

    risk_score = min(
        100,
        (open_ticket_count * 3)
        + (critical_incident_count * 14)
        + (unhealthy_backup_count * 12)
        + (security_events_count * 4)
        + (compliance_open_count * 8)
        + (unhealthy_integrations * 10)
        + (directory_attention_count * 3)
        + (endpoint_alert_count * 4)
        + (review_documents_count * 2)
        + (offline_camera_count * 5)
        + (erp_error_count * 8),
    )

    readiness = 100
    if open_ticket_count:
        readiness -= min(18, open_ticket_count * 2)
    if critical_incident_count:
        readiness -= min(25, critical_incident_count * 10)
    if unhealthy_backup_count:
        readiness -= 12
    if compliance_open_count:
        readiness -= min(18, compliance_open_count * 4)
    if directory_attention_count:
        readiness -= min(12, directory_attention_count * 2)
    if endpoint_alert_count:
        readiness -= min(14, endpoint_alert_count * 3)
    readiness = max(0, readiness)

    kpis = [
        {'title': 'Operasyon Hazırlığı', 'value': f'%{readiness}', 'detail': 'Genel canlı kullanım skoru', 'icon': 'mdi:gauge', 'tone': 'success' if readiness >= 80 else 'warning'},
        {'title': 'Açık Ticket', 'value': open_ticket_count, 'detail': 'Servis masasında bekleyen iş', 'icon': 'mdi:ticket-confirmation-outline', 'tone': 'primary'},
        {'title': 'Kritik Olay', 'value': critical_incident_count, 'detail': 'Major incident ve servis kesintisi', 'icon': 'mdi:alert-decagram-outline', 'tone': 'danger' if critical_incident_count else 'success'},
        {'title': 'Risk Skoru', 'value': risk_score, 'detail': 'Yedek, güvenlik, uyum ve operasyon riski', 'icon': 'mdi:shield-alert-outline', 'tone': 'warning' if risk_score else 'success'},
    ]

    sections = [
        {
            'title': 'Altyapı ve Ağ',
            'icon': 'mdi:server-network',
            'metrics': [
                ('Cihaz', Device.objects.count()),
                ('IP kaydı', IpAddress.objects.count()),
                ('Son tarama', NetworkScan.objects.count()),
                ('Aktif kamera', CameraDevice.objects.exclude(status='offline').count()),
            ],
        },
        {
            'title': 'Servis Masası',
            'icon': 'mdi:headset',
            'metrics': [
                ('Toplam ticket', Ticket.objects.count()),
                ('Açık ticket', open_ticket_count),
                ('Kategori', TicketCategory.objects.count()),
                ('Bilgi bankası', KnowledgeBaseArticle.objects.count()),
            ],
        },
        {
            'title': 'Fabrika Operasyonları',
            'icon': 'mdi:factory',
            'metrics': [
                ('Fabrika departmanı', FactoryDepartment.objects.filter(is_active=True).count()),
                ('Alt alan', FactoryZone.objects.filter(is_active=True).count()),
                ('Fabrika alanı', FactoryArea.objects.count()),
                ('Düşük stok', low_stock_count),
                ('Personel süreci', EmployeeITProcess.objects.exclude(status='closed').count()),
                ('Printer uyarısı', printer_alert_count),
            ],
        },
        {
            'title': 'İş Sürekliliği',
            'icon': 'mdi:database-sync-outline',
            'metrics': [
                ('Sağlıksız yedek', unhealthy_backup_count),
                ('Aktif VPN/erişim', active_remote_count),
                ('İş uygulaması', BusinessApplication.objects.count()),
                ('Runbook', Runbook.objects.count()),
            ],
        },
        {
            'title': 'Yönetişim ve Uyum',
            'icon': 'mdi:clipboard-check-outline',
            'metrics': [
                ('Yaklaşan değişiklik', ChangeCalendarEvent.objects.filter(start_at__date__range=(today, next_30_days)).count()),
                ('CMDB bağımlılığı', ServiceDependency.objects.count()),
                ('Uyumsuz kontrol', compliance_open_count),
                ('Çıktı işi', DocumentOutputJob.objects.exclude(status='delivered').count()),
            ],
        },
        {
            'title': 'Tedarik ve Destek',
            'icon': 'mdi:handshake-outline',
            'metrics': [
                ('Bekleyen satın alma', ProcurementRequest.objects.filter(status='pending').count()),
                ('Vendor case', VendorSupportCase.objects.exclude(status='resolved').count()),
                ('Erişim talebi', AccessRequest.objects.filter(status='pending').count()),
                ('Entegrasyon alarmı', unhealthy_integrations),
            ],
        },
        {
            'title': 'Kimlik ve Uç Nokta',
            'icon': 'mdi:account-key-outline',
            'metrics': [
                ('Directory kullanıcı', DirectoryUser.objects.count()),
                ('Dikkat kullanıcı', directory_attention_count),
                ('Endpoint alarm', endpoint_alert_count),
                ('Açık lifecycle', open_identity_tasks),
            ],
        },
        {
            'title': 'Doküman ve Kartela',
            'icon': 'mdi:file-document-outline',
            'metrics': [
                ('Yönetilen doküman', ManagedDocument.objects.count()),
                ('İnceleme bekleyen', review_documents_count),
                ('Onaylı doküman', ManagedDocument.objects.filter(status='approved').count()),
                ('Varlık ilişkisi', FactoryITAssetRelation.objects.count()),
                ('QR etiket', active_qr_tag_count),
                ('ERP bağlantısı', ERPConnection.objects.count()),
            ],
        },
        {
            'title': 'Entegrasyon ve Saha',
            'icon': 'mdi:connection',
            'metrics': [
                ('Çevrimdışı kamera', offline_camera_count),
                ('ERP sync hatası', erp_error_count),
                ('Entegrasyon alarmı', unhealthy_integrations),
                ('Aktif QR etiket', active_qr_tag_count),
            ],
        },
    ]

    alerts = [
        {'title': 'Açık kritik olaylar', 'value': critical_incident_count, 'tone': 'danger', 'action': 'Servis Süreç Merkezi'},
        {'title': 'Sağlıksız yedek işleri', 'value': unhealthy_backup_count, 'tone': 'warning', 'action': 'IT Operasyon Merkezi'},
        {'title': 'Düşük stok kalemleri', 'value': low_stock_count, 'tone': 'warning', 'action': 'Fabrika IT Operasyonları'},
        {'title': 'Uyumsuz kontroller', 'value': compliance_open_count, 'tone': 'danger', 'action': 'Yönetişim Merkezi'},
        {'title': 'Entegrasyon alarmları', 'value': unhealthy_integrations, 'tone': 'warning', 'action': 'Yönetişim Merkezi'},
        {'title': 'Kimlik ve endpoint riskleri', 'value': directory_attention_count + endpoint_alert_count, 'tone': 'warning', 'action': 'Kimlik & Uç Nokta Merkezi'},
        {'title': 'İnceleme bekleyen dokümanlar', 'value': review_documents_count, 'tone': 'warning', 'action': 'Fabrika BT Komuta Merkezi'},
        {'title': 'Çevrimdışı kameralar', 'value': offline_camera_count, 'tone': 'danger' if offline_camera_count else 'success', 'action': 'ERP & Entegrasyon'},
        {'title': 'ERP senkron hataları', 'value': erp_error_count, 'tone': 'danger' if erp_error_count else 'success', 'action': 'ERP & Entegrasyon'},
    ]

    return {
        'generated_at': now,
        'period_label': f'{today.strftime("%d.%m.%Y")} yönetici özeti',
        'kpis': kpis,
        'sections': sections,
        'alerts': alerts,
        'recommendations': [
            'Kritik olaylar ve sağlıksız yedek işleri günlük operasyon toplantısında ilk gündem yapılmalı.',
            'Düşük stok ve printer uyarıları satın alma sürecine bağlanarak üretim hattı kesintileri önlenmeli.',
            'Uyum kontrolleri ve entegrasyon alarmları haftalık yönetici raporunda kapatma tarihiyle izlenmeli.',
            'Runbook ve bilgi bankası içerikleri artırılarak vardiya ekiplerinin bağımlılığı azaltılmalı.',
        ],
    }


def _build_executive_pdf(context):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=28, leftMargin=28, topMargin=32, bottomMargin=28)
    styles = getSampleStyleSheet()
    elements = [
        Paragraph('OmniOps Factory IT Suite - Yonetici Bilgilendirme Raporu', styles['Heading1']),
        Paragraph(context['period_label'], styles['Normal']),
        Spacer(1, 14),
    ]

    kpi_data = [['KPI', 'Deger', 'Aciklama']]
    for item in context['kpis']:
        kpi_data.append([item['title'], str(item['value']), item['detail']])
    kpi_table = Table(kpi_data, colWidths=[155, 80, 265], repeatRows=1)
    kpi_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#111827')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#d1d5db')),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f8fafc')),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    elements.append(kpi_table)
    elements.append(Spacer(1, 14))

    for section in context['sections']:
        elements.append(Paragraph(section['title'], styles['Heading2']))
        data = [['Metrik', 'Deger']] + [[name, str(value)] for name, value in section['metrics']]
        table = Table(data, colWidths=[260, 120])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#7c3aed')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#e5e7eb')),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#ffffff')),
        ]))
        elements.extend([table, Spacer(1, 10)])

    elements.append(Paragraph('Yonetim Onerileri', styles['Heading2']))
    for recommendation in context['recommendations']:
        elements.append(Paragraph(f'- {recommendation}', styles['Normal']))

    doc.build(elements)
    return buffer.getvalue()


def _build_executive_word_html(context):
    rows = []
    for section in context['sections']:
        metrics = ''.join(f'<li><strong>{escape(name)}</strong>: {escape(str(value))}</li>' for name, value in section['metrics'])
        rows.append(f'<h2>{escape(section["title"])}</h2><ul>{metrics}</ul>')
    kpis = ''.join(f'<tr><td>{escape(item["title"])}</td><td>{escape(str(item["value"]))}</td><td>{escape(item["detail"])}</td></tr>' for item in context['kpis'])
    recommendations = ''.join(f'<li>{escape(item)}</li>' for item in context['recommendations'])
    return f"""<!doctype html>
<html>
<head><meta charset="utf-8"><title>OmniOps Yönetici Raporu</title></head>
<body style="font-family:Arial,sans-serif;color:#111827;">
<h1>OmniOps Factory IT Suite - Yönetici Bilgilendirme Raporu</h1>
<p>{escape(context['period_label'])}</p>
<table border="1" cellspacing="0" cellpadding="8" style="border-collapse:collapse;width:100%;">
<thead><tr style="background:#111827;color:#fff;"><th>KPI</th><th>Değer</th><th>Açıklama</th></tr></thead>
<tbody>{kpis}</tbody>
</table>
{''.join(rows)}
<h2>Yönetim Önerileri</h2>
<ul>{recommendations}</ul>
</body>
</html>"""


@login_required
@role_required(['Ağ Ekibi', 'Sistem Ekibi', 'Yönetim'])
def executive_summary_view(request):
    if not request.user.is_staff:
        return redirect('dashboard')
    return render(request, 'executive_summary.html', build_executive_report_context())


@login_required
@role_required(['Ağ Ekibi', 'Sistem Ekibi', 'Yönetim'])
def executive_summary_export(request, export_format):
    if not request.user.is_staff:
        return redirect('dashboard')
    context = build_executive_report_context()
    today = timezone.now().strftime('%Y%m%d')

    if export_format == 'word':
        response = HttpResponse(_build_executive_word_html(context), content_type='application/msword; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="OmniOps_Yonetici_Ozeti_{today}.doc"'
        return response

    response = HttpResponse(_build_executive_pdf(context), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="OmniOps_Yonetici_Ozeti_{today}.pdf"'
    return response


# ========================================================
# --- RAPORLAMA MERKEZİ (REPORTING HUB) ---
# ========================================================
@login_required
@role_required(['Ağ Ekibi', 'Yönetim'])
def reporting_hub_view(request):
    if not request.user.is_staff:
        return redirect('dashboard')

    if request.method == 'POST':
        report_type = request.POST.get('report_type')
        start_date_str = request.POST.get('start_date')
        end_date_str = request.POST.get('end_date')
        
        try:
            from django.utils.dateparse import parse_date
            start_date = parse_date(start_date_str) if start_date_str else timezone.now().date() - timedelta(days=30)
            end_date = parse_date(end_date_str) if end_date_str else timezone.now().date()
            
            # Bitiş tarihini gün sonuna (23:59:59) ayarla
            end_date_time = timezone.make_aware(timezone.datetime.combine(end_date, timezone.datetime.max.time()))
            start_date_time = timezone.make_aware(timezone.datetime.combine(start_date, timezone.datetime.min.time()))

            response = HttpResponse(content_type='application/pdf')
            buffer = io.BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=A4)
            styles = getSampleStyleSheet()
            elements = []

            # 1. BİLET (TICKET) PERFORMANS RAPORU
            if report_type == 'ticket_performance':
                response['Content-Disposition'] = f'attachment; filename="Bilet_Raporu_{end_date.strftime("%Y%m%d")}.pdf"'
                elements.append(Paragraph("Bilet (Ticket) Performans Raporu", styles['Heading1']))
                elements.append(Paragraph(f"Dönem: {start_date.strftime('%d.%m.%Y')} - {end_date.strftime('%d.%m.%Y')}", styles['Normal']))
                elements.append(Spacer(1, 12))
                
                tickets = Ticket.objects.filter(created_at__range=(start_date_time, end_date_time)).order_by('-created_at')
                
                if tickets.exists():
                    data = [['ID', 'Başlık', 'Durum', 'Öncelik', 'Oluşturan', 'Tarih']]
                    for t in tickets[:100]: # Max 100 kayıt
                        creator = t.created_by.username if t.created_by else 'Sistem'
                        data.append([str(t.id), t.title[:30], t.status, t.priority, creator, t.created_at.strftime('%d.%m.%Y')])
                    
                    table = Table(data, colWidths=[30, 150, 70, 60, 80, 80])
                    table.setStyle(TableStyle([
                        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0b101e')),
                        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                        ('FONTSIZE', (0, 0), (-1, 0), 10),
                        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f8fafc')),
                        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                    ]))
                    elements.append(table)
                else:
                    elements.append(Paragraph("Bu dönemde açılmış bilet bulunmuyor.", styles['Normal']))

            # 2. SİSTEM DENETİM (AUDIT) RAPORU
            elif report_type == 'audit_log':
                response['Content-Disposition'] = f'attachment; filename="Denetim_Raporu_{end_date.strftime("%Y%m%d")}.pdf"'
                elements.append(Paragraph("Sistem Denetim (Audit) Raporu", styles['Heading1']))
                elements.append(Paragraph(f"Dönem: {start_date.strftime('%d.%m.%Y')} - {end_date.strftime('%d.%m.%Y')}", styles['Normal']))
                elements.append(Spacer(1, 12))
                
                logs = SystemLog.objects.filter(created_at__range=(start_date_time, end_date_time)).order_by('-created_at')
                
                if logs.exists():
                    data = [['Tarih', 'İşlem Türü', 'Kullanıcı', 'Açıklama']]
                    for log in logs[:150]:
                        user_str = log.user.username if log.user else 'Sistem'
                        detay = log.details[:60] + '...' if len(log.details) > 60 else log.details
                        data.append([log.created_at.strftime('%d.%m.%Y %H:%M'), log.action, user_str, detay])
                        
                    table = Table(data, colWidths=[90, 80, 80, 220])
                    table.setStyle(TableStyle([
                        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0f172a')),
                        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                        ('FONTSIZE', (0, 0), (-1, 0), 10),
                        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f1f5f9')),
                        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                    ]))
                    elements.append(table)
                else:
                    elements.append(Paragraph("Bu dönemde kaydedilmiş denetim izi bulunmuyor.", styles['Normal']))
            
            doc.build(elements)
            response.write(buffer.getvalue())
            buffer.close()
            
            SystemLog.objects.create(user=request.user, action='SYSTEM', details=f"Raporlama Modülü: {report_type} raporu indirildi.")
            return response
            
        except Exception as e:
            messages.error(request, f"Rapor oluşturulurken hata oluştu: {str(e)}")
            return redirect('reporting_hub')
            
    return render(request, 'reporting_hub.html')


# ========================================================
# --- EVRENSEL (GENERIC) CRUD (DÜZENLEME VE SİLME) GÖRÜNÜMLERİ ---
# ========================================================

class StaffRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    raise_exception = True

    def test_func(self):
        return self.request.user.is_staff or self.request.user.is_superuser


# --- CİHAZ (DONANIM) ---
class DeviceUpdateView(StaffRequiredMixin, UpdateView):
    model = Device
    form_class = DeviceForm
    template_name = 'inventory/generic_form.html'
    success_url = reverse_lazy('custom_admin')

class DeviceDeleteView(StaffRequiredMixin, DeleteView):
    model = Device
    template_name = 'inventory/generic_confirm_delete.html'
    success_url = reverse_lazy('custom_admin')

# --- LİSANS ---
class LicenseUpdateView(StaffRequiredMixin, UpdateView):
    model = License
    form_class = LicenseForm
    template_name = 'inventory/generic_form.html'
    success_url = reverse_lazy('it_inventory')

class LicenseDeleteView(StaffRequiredMixin, DeleteView):
    model = License
    template_name = 'inventory/generic_confirm_delete.html'
    success_url = reverse_lazy('it_inventory')

# --- TEDARİKÇİ (VENDOR CONTRACT) ---
class VendorContractUpdateView(StaffRequiredMixin, UpdateView):
    model = VendorContract
    fields = '__all__'
    template_name = 'inventory/generic_form.html'
    success_url = reverse_lazy('it_inventory')

class VendorContractDeleteView(StaffRequiredMixin, DeleteView):
    model = VendorContract
    template_name = 'inventory/generic_confirm_delete.html'
    success_url = reverse_lazy('it_inventory')

# --- ZİMMET (IT ASSET) ---
class ITAssetUpdateView(StaffRequiredMixin, UpdateView):
    model = ITAsset
    form_class = ITAssetForm
    template_name = 'inventory/generic_form.html'
    success_url = reverse_lazy('it_inventory')

class ITAssetDeleteView(StaffRequiredMixin, DeleteView):
    model = ITAsset
    template_name = 'inventory/generic_confirm_delete.html'
    success_url = reverse_lazy('it_inventory')

# --- IP ADRESİ (IPAM) ---
class IpAddressUpdateView(StaffRequiredMixin, UpdateView):
    model = IpAddress
    form_class = IpAddressForm
    template_name = 'inventory/generic_form.html'
    success_url = reverse_lazy('visual_ipam')

class IpAddressDeleteView(StaffRequiredMixin, DeleteView):
    model = IpAddress
    template_name = 'inventory/generic_confirm_delete.html'
    success_url = reverse_lazy('visual_ipam')

# --- DESTEK BİLETİ (TICKET) ---
class TicketUpdateView(StaffRequiredMixin, UpdateView):
    model = Ticket
    form_class = TicketForm
    template_name = 'inventory/generic_form.html'
    success_url = reverse_lazy('dashboard')

class TicketDeleteView(StaffRequiredMixin, DeleteView):
    model = Ticket
    template_name = 'inventory/generic_confirm_delete.html'
    success_url = reverse_lazy('dashboard')