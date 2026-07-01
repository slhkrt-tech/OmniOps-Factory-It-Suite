from celery import shared_task
from django.utils import timezone
from datetime import timedelta
from django.core.mail import EmailMessage
from django.conf import settings
from django.db.models import Avg
from pathlib import Path
import csv
import os
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from django.db import transaction
from django.db import connection # YENİ: Risk 1 çözümü için
from .models import Device, IpAddress, License, VendorContract, SystemLog, User, Ticket, DevicePerformanceLog, ITAsset
from .utils import (
    scan_network, deep_discover_device, push_config_to_device, 
    backup_device_config, decrypt_vault_password, poll_device_hardware,
    check_all_devices_predictive_maintenance
)

# --- MEVCUT RUTİN GÖREVLER ---

@shared_task(name="inventory.tasks.otomatik_ag_taramasi", soft_time_limit=3600, time_limit=3660)
def otomatik_ag_taramasi(network="192.168.1.0/24"):
    """Gece 03:00'te çalışarak ağı tarar, cihazları bulur ve WMI/SNMP ile derin analiz yapar."""
    results = scan_network(network)
    if 'error' in results:
        SystemLog.objects.create(action='SYSTEM', details=f"Celery: Otomatik ağ taraması başarısız. Hata: {results['error']}")
        return "Hata"

    active_devices = results.get('active_ips', [])
    new_device_count = 0
    deep_discovery_count = 0
    
    for dev_info in active_devices:
        ip = dev_info.get('ip')
        mac = dev_info.get('mac')
        hostname = dev_info.get('hostname', 'Bilinmeyen Cihaz')
        
        if mac and mac != "ff:ff:ff:ff:ff:ff":
            device, created = Device.objects.get_or_create(
                mac_address=mac,
                defaults={'name': hostname[:100], 'device_type': 'PC', 'is_active': True}
            )
            if created:
                new_device_count += 1
                
            ip_obj, ip_created = IpAddress.objects.get_or_create(
                address=ip, defaults={'is_allocated': True, 'device': device}
            )
            if not ip_created and not ip_obj.device:
                ip_obj.device = device
                ip_obj.is_allocated = True
                ip_obj.save()

            discovery_data = deep_discover_device(ip)
            
            if discovery_data["status"] == "success":
                device.os_version = discovery_data["os_version"]
                if created:
                    device.device_type = discovery_data["device_type"]
                device.save()
                
                asset, asset_created = ITAsset.objects.get_or_create(
                    serial_number=discovery_data["serial_number"],
                    defaults={
                        'name': f"{hostname} ({discovery_data['model']})",
                        'asset_type': 'desktop',
                        'model': discovery_data["model"],
                        'status': 'active'
                    }
                )
                deep_discovery_count += 1

    if new_device_count > 0 or deep_discovery_count > 0:
        SystemLog.objects.create(
            action='SCAN', 
            details=f"ManageEngine Algoritması: Gece taramasında {new_device_count} yeni cihaz bulundu, {deep_discovery_count} cihaz WMI/SNMP ile analiz edildi."
        )
    return f"Tarama bitti. {new_device_count} yeni cihaz, {deep_discovery_count} derin analiz."

@shared_task
def otomatik_sla_ve_lisans_kontrolu():
    deadline = timezone.now().date() + timedelta(days=30)
    yaklasan_lisanslar = License.objects.filter(expiry_date__lte=deadline)
    yaklasan_sozlesmeler = VendorContract.objects.filter(end_date__lte=deadline)
    
    if yaklasan_lisanslar.exists() or yaklasan_sozlesmeler.exists():
        SystemLog.objects.create(
            action='SYSTEM',
            details=(
                "Celery Otomasyonu: Yaklaşan lisans/sözleşme uyarısı üretildi. "
                f"Lisans: {yaklasan_lisanslar.count()}, Sözleşme: {yaklasan_sozlesmeler.count()}."
            ),
        )
    return "Kontrol bitti."

@shared_task
def check_sla_and_escalate():
    now = timezone.now()
    breached_tickets = Ticket.objects.filter(status__in=['Acik', 'Inceleniyor'], sla_deadline__lt=now, is_escalated=False)
    if not breached_tickets.exists():
        return "SLA ihlali yapan yeni bilet bulunamadı."

    from .helpdesk import notify_user, notify_ticket_event
    it_manager = User.objects.filter(is_superuser=True, is_active=True).first()
    escalated_count = 0
    for ticket in breached_tickets:
        ticket.is_escalated = True
        ticket.priority = 'Kritik'
        if it_manager:
            ticket.assigned_to = it_manager
            notify_user(
                it_manager,
                f'SLA ihlali: #{ticket.id}',
                ticket.title,
                link=f'/talep/{ticket.id}/',
                notification_type='sla_breach',
                ticket=ticket,
            )
            SystemLog.objects.create(action='TICKET', details=f"SLA İHLALİ: #{ticket.id} numaralı bilet {it_manager.username} adlı yöneticiye otomatik eskale edildi.")
        notify_ticket_event(ticket, 'sla_breach')
        ticket.save()
        escalated_count += 1
    return f"{escalated_count} adet bilet başarıyla eskale edildi."

@shared_task
def zabbix_threshold_monitor():
    five_mins_ago = timezone.now() - timedelta(minutes=5)
    devices = Device.objects.filter(is_active=True)
    alarm_count = 0
    for dev in devices:
        recent_logs = DevicePerformanceLog.objects.filter(device=dev, recorded_at__gte=five_mins_ago)
        if recent_logs.exists():
            avg_cpu = recent_logs.aggregate(Avg('cpu_usage'))['cpu_usage__avg'] or 0
            avg_ram = recent_logs.aggregate(Avg('ram_usage'))['ram_usage__avg'] or 0
            
            alarm_reasons = []
            if avg_cpu >= dev.cpu_alarm_threshold:
                alarm_reasons.append(f"CPU Ortalaması: %{avg_cpu:.1f} (Eşik: %{dev.cpu_alarm_threshold})")
            if avg_ram >= dev.ram_alarm_threshold:
                alarm_reasons.append(f"RAM Ortalaması: %{avg_ram:.1f} (Eşik: %{dev.ram_alarm_threshold})")
                
            if alarm_reasons:
                recent_ticket_exists = Ticket.objects.filter(device=dev, title__contains="Kapasite İhlali", status__in=['Acik', 'Inceleniyor']).exists()
                if not recent_ticket_exists:
                    reasons_text = " | ".join(alarm_reasons)
                    ticket = Ticket.objects.create(
                        title=f"🚨 ALARM: {dev.name} Kapasite İhlali",
                        description=f"ZABBIX REAKTİF MOTORU:\n\nTespit Edilen İhlaller:\n{reasons_text}",
                        priority='Yuksek', category='Donanim', status='Acik', device=dev
                    )
                    SystemLog.objects.create(action='SYSTEM', details=f"PRTG Algoritması: {dev.name} adlı cihaz eşik değerlerini aştı. #{ticket.id} açıldı.")
                    alarm_count += 1
    return f"Threshold kontrolü tamamlandı. {alarm_count} yeni alarm üretildi."

@shared_task(name="inventory.tasks.otomatik_gece_yedekleme", soft_time_limit=3600, time_limit=3660)
def otomatik_gece_yedekleme():
    devices = Device.objects.filter(is_active=True).exclude(ssh_user__isnull=True).exclude(ssh_user__exact='')
    success_count = 0
    for dev in devices:
        ip_obj = dev.ipaddress_set.first()
        if not ip_obj:
            continue
        success, msg = backup_device_config(
            device_obj=dev, device_ip=ip_obj.address, username=dev.ssh_user or 'admin',
            password=decrypt_vault_password(dev.ssh_password) or 'admin',
            vendor=dev.vendor, user=None
        )
        if success:
            success_count += 1

    if success_count > 0:
        SystemLog.objects.create(action='SYSTEM', details=f'Otomatik Gece Yedeklemesi tamamlandı. {success_count} cihaz başarıyla yedeklendi.')
    return f"Otomatik gece yedekleme tamamlandı. {success_count} cihaz yedeklendi."

@shared_task(soft_time_limit=3600, time_limit=3660)
def postgres_dump_backup_task():
    """PostgreSQL veritabanını pg_dump ile günlük olarak yedekler ve isteğe bağlı S3'e yükler.
    
    Hata aldığında otomatik olarak yöneticilere "Kritik" bilet açar.
    S3'e yüklemeden sonra 7 günden eski yedekleri temizler.
    """
    db = settings.DATABASES.get('default', {})
    if db.get('ENGINE') != 'django.db.backends.postgresql':
        return 'PostgreSQL veritabanı kullanılmıyor; yedekleme atlandı.'

    if not all([db.get('NAME'), db.get('USER'), db.get('HOST'), db.get('PORT')]):
        return 'PostgreSQL bağlantı bilgisi eksik; yedekleme atlandı.'

    backup_dir = Path(settings.POSTGRES_BACKUP_DIR)
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
    extension = 'dump' if settings.POSTGRES_BACKUP_FORMAT == 'custom' else 'sql'
    backup_file = backup_dir / f"{settings.POSTGRES_BACKUP_FILE_PREFIX}_{timestamp}.{extension}"

    cmd = [settings.PG_DUMP_PATH]
    if settings.POSTGRES_BACKUP_FORMAT == 'custom':
        cmd.append('-Fc')
    else:
        cmd.extend(['-Fp', '-O', '-x'])

    cmd.extend([
        f"--dbname=postgresql://{db['USER']}:{db['PASSWORD']}@{db['HOST']}:{db['PORT']}/{db['NAME']}",
        '-f', str(backup_file),
    ])

    env = os.environ.copy()
    env['PGPASSWORD'] = db.get('PASSWORD', '')

    try:
        subprocess.run(cmd, check=True, env=env)
        upload_message = ''
        if settings.AWS_S3_BACKUP_BUCKET and settings.AWS_S3_REGION_NAME:
            try:
                _upload_backup_to_s3(backup_file)
                upload_message = f' ve S3 yüklemesi tamamlandı: {settings.AWS_S3_BACKUP_BUCKET}/{backup_file.name}'
                
                # S3 yüklemesinden sonra eski yedekleri temizle (7 günü aşan backupları)
                cleanup_old_s3_backups()
            except Exception as exc:
                error_msg = f'PostgreSQL yedeği oluşturuldu ancak S3 yüklemesi başarısız: {exc}'
                SystemLog.objects.create(action='SYSTEM', details=error_msg)
                
                # S3 yükleme hatası: Yöneticilere "Kritik" bilet aç
                _create_backup_error_ticket(
                    title="🚨 PostgreSQL S3 Yükleme Hatası",
                    description=f"PostgreSQL yedeği yerel olarak oluşturuldu ancak S3'e yükleme başarısız oldu.\n\nHata Detayı:\n{str(exc)}\n\nYedek Dosyası: {backup_file.name}"
                )
                return error_msg

        SystemLog.objects.create(action='SYSTEM', details=f'PostgreSQL yedeği oluşturuldu: {backup_file}{upload_message}')
        return f'PostgreSQL yedeği başarıyla oluşturuldu: {backup_file}{upload_message}'
        
    except subprocess.CalledProcessError as exc:
        error_msg = f'PostgreSQL yedekleme hatası: {exc}'
        SystemLog.objects.create(action='SYSTEM', details=error_msg)
        
        # pg_dump çökmesi: Yöneticilere "Kritik" bilet aç
        _create_backup_error_ticket(
            title="🚨 PostgreSQL pg_dump Hatası",
            description=f"PostgreSQL yedekleme sırasında pg_dump komutu başarısız oldu.\n\nHata Detayı:\n{str(exc)}"
        )
        return error_msg
        
    except Exception as exc:
        error_msg = f'PostgreSQL yedekleme sırasında beklenmeyen hata: {exc}'
        SystemLog.objects.create(action='SYSTEM', details=error_msg)
        
        # Beklenmeyen hata: Yöneticilere "Kritik" bilet aç
        _create_backup_error_ticket(
            title="🚨 PostgreSQL Yedekleme Beklenmeyen Hatası",
            description=f"PostgreSQL yedekleme sırasında beklenmeyen bir hata oluştu.\n\nHata Detayı:\n{str(exc)}"
        )
        return error_msg


def _upload_backup_to_s3(backup_file: Path):
    try:
        import boto3
    except ImportError as exc:
        raise RuntimeError('Boto3 yüklü değil; AWS S3 yüklemesi yapılamadı.') from exc

    if not all([settings.AWS_ACCESS_KEY_ID, settings.AWS_SECRET_ACCESS_KEY, settings.AWS_S3_BACKUP_BUCKET, settings.AWS_S3_REGION_NAME]):
        raise RuntimeError('S3 için gerekli AWS kimlik bilgileri veya bucket adı eksik.')

    session = boto3.session.Session(
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=settings.AWS_S3_REGION_NAME,
    )
    s3 = session.resource('s3')
    bucket = s3.Bucket(settings.AWS_S3_BACKUP_BUCKET)
    bucket.upload_file(str(backup_file), backup_file.name, ExtraArgs={'ServerSideEncryption': 'AES256'})


def _create_backup_error_ticket(title: str, description: str):
    """PostgreSQL yedekleme hatası oluştuğunda yöneticilere otomatik "Kritik" bilet açar."""
    try:
        # Tüm yöneticileri (superuser) bul
        admin_users = User.objects.filter(is_superuser=True, is_active=True)
        
        if admin_users.exists():
            # İlk yöneticiye atama yap
            assigned_admin = admin_users.first()
            ticket = Ticket.objects.create(
                title=title,
                description=description,
                priority='Kritik',
                category='Diger',
                status='Acik',
                assigned_to=assigned_admin,
                created_by=assigned_admin
            )
            SystemLog.objects.create(
                action='TICKET',
                details=f'PostgreSQL Yedekleme Kritik Hatası: #{ticket.id} numaralı bilet otomatik açıldı ve {assigned_admin.username} adlı yöneticiye atandı.'
            )
        else:
            # Yönetici yoksa en azından log kaydı yapıl
            SystemLog.objects.create(
                action='SYSTEM',
                details=f'PostgreSQL Yedekleme Kritik Hatası Uyarısı: Yönetici kullanıcı bulunamadığı için bilet açılamadı. Sorun: {title}'
            )
    except Exception as e:
        # Bilet açma sırasında hata: İçi boş bırakan catch bloğu olmasından kaçın
        SystemLog.objects.create(
            action='SYSTEM',
            details=f'PostgreSQL Yedekleme Hatası Bilet Açma Başarısız: {str(e)}'
        )


def cleanup_old_s3_backups(days_old=7):
    """S3 bucket'ında 7 günden eski yedek dosyalarını siler (Retention Policy).
    
    Args:
        days_old: Kaç günden eski dosyaları silmek istediğini belirtir (default: 7 gün)
    """
    try:
        import boto3
    except ImportError:
        SystemLog.objects.create(
            action='SYSTEM',
            details='S3 yedek temizleme: Boto3 yüklü değil; eski yedekleri temizleyemedi.'
        )
        return

    if not all([settings.AWS_ACCESS_KEY_ID, settings.AWS_SECRET_ACCESS_KEY, settings.AWS_S3_BACKUP_BUCKET, settings.AWS_S3_REGION_NAME]):
        SystemLog.objects.create(
            action='SYSTEM',
            details='S3 yedek temizleme: AWS kimlik bilgileri eksik; eski yedekleri temizleyemedi.'
        )
        return

    try:
        session = boto3.session.Session(
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_S3_REGION_NAME,
        )
        s3 = session.client('s3')
        
        cutoff_date = timezone.now() - timedelta(days=days_old)
        deleted_count = 0
        
        # S3 bucket'ında tüm objeleri listele
        paginator = s3.get_paginator('list_objects_v2')
        pages = paginator.paginate(Bucket=settings.AWS_S3_BACKUP_BUCKET, Prefix=settings.POSTGRES_BACKUP_FILE_PREFIX)
        
        for page in pages:
            if 'Contents' not in page:
                continue
                
            for obj in page['Contents']:
                # Dosya adından timestamp'i çıkart (örn: omniops_backup_20230115_103045.dump)
                # LastModified ile eski olup olmadığını kontrol et
                if obj['LastModified'].replace(tzinfo=None) < cutoff_date.replace(tzinfo=None):
                    s3.delete_object(Bucket=settings.AWS_S3_BACKUP_BUCKET, Key=obj['Key'])
                    deleted_count += 1
        
        if deleted_count > 0:
            SystemLog.objects.create(
                action='SYSTEM',
                details=f'S3 Yedek Temizleme: {deleted_count} adet {days_old} günden eski yedek dosyası başarıyla silindi.'
            )
    except Exception as e:
        SystemLog.objects.create(
            action='SYSTEM',
            details=f'S3 Yedek Temizleme Hatası: {str(e)}'
        )

@shared_task
def distributed_probe_polling():
    """Heartbeat göndermeyen probe/agent kayıtlarını offline olarak işaretler."""
    from .models import RemoteProbe

    timeout = timezone.now() - timedelta(minutes=30)
    probes = RemoteProbe.objects.filter(last_heartbeat__lt=timeout).exclude(status='offline')
    updated = 0
    for probe in probes:
        probe.status = 'offline'
        probe.save(update_fields=['status'])
        updated += 1

    SystemLog.objects.create(action='SYSTEM', details=f'Dağıtık probe kontrolü tamamlandı. {updated} probe offline işaretlendi.')
    return f'Dağıtık probe kontrolü tamamlandı. {updated} probe offline işaretlendi.'

@shared_task
def periodic_security_poll():
    devices = Device.objects.filter(is_active=True).exclude(ssh_user__isnull=True).exclude(ssh_user__exact='')
    scanned = 0
    for dev in devices:
        ip_obj = dev.ipaddress_set.first()
        if not ip_obj:
            continue
        poll_device_hardware(dev, ip_obj.address)
        scanned += 1
    return f"Security poll tamamlandı. {scanned} cihaz tarandı."

# ========================================================
# --- VERİ ARŞİVLEME VE TEMİZLEME (DATA RETENTION) ---
# ========================================================
@shared_task(soft_time_limit=3600, time_limit=3660)
def data_retention_policy_task():
    """Her ayın 1'inde 90 günden eski performans ve sistem loglarını CSV/PDF olarak arşivler ve siler."""
    cutoff_date = timezone.now() - timedelta(days=90)
    archive_dir = Path(settings.BASE_DIR) / 'archives'
    archive_dir.mkdir(parents=True, exist_ok=True)
    timestamp_str = timezone.now().strftime("%Y%m%d_%H%M%S")

    # 1. PERFORMANS LOGLARI (CPU/RAM) İÇİN ARŞİV
    old_perf_logs = DevicePerformanceLog.objects.filter(recorded_at__lt=cutoff_date)
    perf_count = 0
    if old_perf_logs.exists():
        csv_path = archive_dir / f'device_performance_archive_{timestamp_str}.csv'
        pdf_path = archive_dir / f'device_performance_archive_{timestamp_str}.pdf'

        with open(csv_path, 'w', newline='', encoding='utf-8') as csv_file:
            writer = csv.writer(csv_file)
            writer.writerow(['Device', 'CPU %', 'RAM %', 'Disk %', 'Recorded At'])
            for log in old_perf_logs.select_related('device').order_by('recorded_at'):
                writer.writerow([log.device.name if log.device else 'Unknown', log.cpu_usage, log.ram_usage, log.disk_usage, log.recorded_at.isoformat()])

        try:
            from reportlab.lib.pagesizes import letter
            from reportlab.lib import colors
            from reportlab.platypus import SimpleDocTemplate, Table, TableStyle

            rows = [['Device', 'CPU %', 'RAM %', 'Disk %', 'Recorded At']]
            for log in old_perf_logs.select_related('device').order_by('recorded_at'):
                rows.append([log.device.name if log.device else 'Unknown', log.cpu_usage, log.ram_usage, log.disk_usage, log.recorded_at.strftime('%Y-%m-%d %H:%M')])

            doc = SimpleDocTemplate(str(pdf_path), pagesize=letter)
            table = Table(rows, repeatRows=1)
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0b5394')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ]))
            doc.build([table])
        except Exception:
            pass # PDF oluşmazsa yoksay, CSV yeterli

        perf_count = old_perf_logs.count()
        old_perf_logs.delete()

    # 2. SİSTEM LOGLARI İÇİN ARŞİV
    old_system_logs = SystemLog.objects.filter(created_at__lt=cutoff_date)
    sys_count = 0
    if old_system_logs.exists():
        csv_path_sys = archive_dir / f'system_logs_archive_{timestamp_str}.csv'
        with open(csv_path_sys, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(['ID', 'Action', 'Details', 'Created_At', 'User'])
            for log in old_system_logs:
                user_str = log.user.username if log.user else 'System'
                writer.writerow([log.id, log.action, log.details, log.created_at, user_str])
        
        sys_count = old_system_logs.count()
        old_system_logs.delete()

    if perf_count > 0 or sys_count > 0:
        msg = f"[DATA RETENTION] İşlem tamamlandı. {perf_count} Performans Logu, {sys_count} Sistem Logu CSV/PDF olarak arşivlendi ve veritabanından silindi."
        SystemLog.objects.create(action='SYSTEM', details=msg)
        return msg
    return "Arşivlenecek eski veri bulunamadı."


# --- BACKWARDS-COMPATIBILITY WRAPPERS ---
@shared_task
def archive_old_performance_logs():
    """Wrapper for legacy Celery schedule name. Calls the main data retention task."""
    return data_retention_policy_task()


# ========================================================
# --- AIOPS - TAHMİNLEYİCİ BAKIM ---
# ========================================================
@shared_task(soft_time_limit=3600, time_limit=3660)
def run_predictive_maintenance():
    """Celery Beat üzerinden her gün tetiklenecek görev."""
    result = check_all_devices_predictive_maintenance()
    SystemLog.objects.create(action='SYSTEM', details=f"AIOps: {result}")
    return result

# ========================================================
# --- WAZUH ACTIVE RESPONSE (OTONOM SİBER SAVUNMA) ---
# ========================================================
@shared_task
def active_response_block_ip(attacker_ip, device_id):
    """Siber saldırı (Brute-Force) tespit edildiğinde IP bloklar."""
    device = Device.objects.filter(id=device_id).first()
    if not device:
        return "Cihaz bulunamadı."

    config_payload = f"""
    ! SOC OTONOM SAVUNMA TETİKLENDİ
    ip access-list extended WAZUH-AUTO-BLOCK
     deny ip host {attacker_ip} any
     permit ip any any
    exit
    interface GigabitEthernet0/1
     ip access-group WAZUH-AUTO-BLOCK in
    exit
    """

    device_ip = device.ipaddress_set.first().address if device.ipaddress_set.exists() else '192.168.1.1'

    success, msg = push_config_to_device(
        ip_address=device_ip,
        username=device.ssh_user or 'admin',
        password=decrypt_vault_password(device.ssh_password) or 'admin',
        enable_secret=decrypt_vault_password(device.enable_password) or '',
        vendor=device.vendor,
        config_payload=config_payload,
        device_obj=device
    )

    if success:
        SystemLog.objects.create(action='SYSTEM', details=f"🛡️ ACTIVE RESPONSE: {attacker_ip} saldırgan IP adresi, {device.name} cihazında başarıyla karantinaya alındı!")
        return f"Savunma Başarılı: {attacker_ip} engellendi."
    else:
        SystemLog.objects.create(action='SYSTEM', details=f"❌ ACTIVE RESPONSE HATASI: {attacker_ip} IP'si engellenemedi. Hata: {msg}")
        return f"Savunma Başarısız: {msg}"


# ========================================================
# --- KAMERA / NVR HEALTH POLLING ---
# ========================================================
@shared_task(name='inventory.tasks.poll_camera_health_task')
def poll_camera_health_task():
    """Celery Beat: kamera/NVR cihazlarının TCP ve HTTP erişilebilirliğini periyodik kontrol eder."""
    from .models import CameraDevice, SystemLog
    from .integrations.camera_health import poll_camera_devices

    summary, stale_count = poll_camera_devices(CameraDevice.objects.all())
    message = (
        f"Kamera sağlık taraması: çevrimiçi={summary.get('online', 0)}, "
        f"uyarı={summary.get('warning', 0)}, çevrimdışı={summary.get('offline', 0)}, "
        f"eski_kayıt={stale_count}"
    )
    SystemLog.objects.create(action='SYSTEM', details=message)
    return message


# ========================================================
# --- ODOO / ERP CONNECTOR SYNC ---
# ========================================================
@shared_task(name='inventory.tasks.sync_erp_connection_task')
def sync_erp_connection_task(connection_id):
    """Tek bir ERP bağlantısı için senkronizasyon görevini çalıştırır."""
    from .models import ERPConnection, SystemLog
    from .integrations.erp_connector import ERPClientError, sync_erp_connection

    connection = ERPConnection.objects.filter(pk=connection_id).first()
    if not connection or not connection.sync_enabled:
        return 'ERP bağlantısı bulunamadı veya sync kapalı.'

    try:
        count, message = sync_erp_connection(connection)
        connection.last_sync_at = timezone.now()
        connection.last_sync_status = 'healthy'
        connection.last_sync_message = message
        connection.records_synced = count
        connection.save(update_fields=[
            'last_sync_at', 'last_sync_status', 'last_sync_message', 'records_synced', 'updated_at',
        ])
        SystemLog.objects.create(action='SYSTEM', details=f'ERP sync OK · {connection.name}: {message}')
        return message
    except ERPClientError as exc:
        connection.last_sync_status = 'error'
        connection.last_sync_message = str(exc)
        connection.save(update_fields=['last_sync_status', 'last_sync_message', 'updated_at'])
        SystemLog.objects.create(action='SYSTEM', details=f'ERP sync hata · {connection.name}: {exc}')
        return str(exc)


@shared_task(name='inventory.tasks.sync_all_erp_connections_task')
def sync_all_erp_connections_task():
    """Aktif tüm ERP bağlantıları için senkronizasyon işlerini kuyruğa alır."""
    from .models import ERPConnection

    queued = 0
    for connection in ERPConnection.objects.filter(sync_enabled=True):
        sync_erp_connection_task.delay(connection.id)
        queued += 1
    return f'{queued} ERP sync işi kuyruğa alındı.'


@shared_task(name='inventory.tasks.poll_integration_health_task')
def poll_integration_health_task():
    """Entegrasyon sağlık kayıtlarının uç noktalarına HTTP HEAD ile periyodik erişim testi yapar."""
    import time
    import urllib.error
    import urllib.request
    from .models import IntegrationHealthCheck, SystemLog

    updated = 0
    for check in IntegrationHealthCheck.objects.exclude(endpoint_url=''):
        start = time.time()
        status = 'down'
        try:
            request = urllib.request.Request(check.endpoint_url, method='HEAD')
            with urllib.request.urlopen(request, timeout=5) as response:
                elapsed = int((time.time() - start) * 1000)
                check.response_time_ms = elapsed
                status = 'healthy' if response.status < 400 else 'degraded'
                # 2 saniyeden yavaş yanıtlar sorunlu kabul edilir
                if elapsed > 2000:
                    status = 'degraded'
        except urllib.error.HTTPError as exc:
            check.response_time_ms = int((time.time() - start) * 1000)
            status = 'degraded' if exc.code < 500 else 'down'
        except Exception:
            check.response_time_ms = 0
            status = 'down'
        check.last_status = status
        check.last_checked_at = timezone.now()
        check.save(update_fields=['last_status', 'last_checked_at', 'response_time_ms', 'updated_at'])
        updated += 1

    SystemLog.objects.create(action='SYSTEM', details=f'Entegrasyon sağlık taraması tamamlandı. {updated} kayıt güncellendi.')
    return f'{updated} entegrasyon kontrol edildi.'


# ========================================================
# --- BULK KONFİGÜRASYON (ASENKRON VE PARALEL YAPI) ---
# ========================================================

def _atomic_device_config_push(device_id, config_payload, vendor, change_request_id):
    """Her bir cihaz için paralel iş parçacığında tetiklenecek atomik SSH fonksiyonu."""
    from .models import Device, Ticket
    from .utils import push_config_to_device, decrypt_vault_password
    try:
        device = Device.objects.get(id=device_id)
        target_ip = device.ipaddress_set.first().address if device.ipaddress_set.exists() else None
        
        if not target_ip:
            return f"❌ {device.name}: Başarısız - Cihaza tanımlı IP adresi bulunamadı."
        
        success, msg = push_config_to_device(
            ip_address=target_ip,
            username=device.ssh_user or 'admin',
            password=decrypt_vault_password(device.ssh_password) or 'admin',
            enable_secret=decrypt_vault_password(device.enable_password) or '',
            vendor=vendor or device.vendor or 'cisco',
            config_payload=config_payload
        )
        
        with transaction.atomic():
            if success:
                device.monitoring_mode = 'monitoring'
                device.is_active = True
                device.save(update_fields=['monitoring_mode', 'is_active'])
                return f"✅ {device.name} ({target_ip}): Yapılandırma başarıyla uygulandı."
            else:
                device.monitoring_mode = 'error'
                device.is_active = False
                device.save(update_fields=['monitoring_mode', 'is_active'])
                
                Ticket.objects.create(
                    title=f"🚨 TOPLU İŞLEM HATASI: {device.name}",
                    description=f"Toplu konfigürasyon basımı sırasında cihaz hata döndürdü.\n\nHata Detayı: {msg}",
                    priority='Yuksek',
                    category='Ag',
                    status='Acik',
                    device=device
                )
                return f"❌ {device.name} ({target_ip}): Başarısız - {msg}"
                
    except Device.DoesNotExist:
        return f"❌ ID #{device_id}: Cihaz veritabanında bulunamadı."
    except Exception as e:
        return f"❌ ID #{device_id}: Kritik Sistem Hatası - {str(e)}"
    finally:
        # RİSK 1 ÇÖZÜMÜ: Thread bittiğinde DB bağlantısını zorla kapat!
        connection.close()

@shared_task(name="inventory.tasks.bulk_push_config_to_devices", soft_time_limit=1800, time_limit=1860)
def bulk_push_config_to_devices(change_request_id):
    """
    Seçilen tüm envanter cihazlarına paralel kanallardan bağlanarak 
    toplu konfigürasyon push işlemini asenkron olarak yönetir.
    """
    from .models import ChangeRequest, SystemLog
    try:
        change_req = ChangeRequest.objects.get(id=change_request_id)
        devices = change_req.target_devices.all()
        
        if not devices.exists():
            change_req.status = 'failed'
            change_req.execution_log = "Hata: Hedef cihaz listesi boş."
            change_req.save(update_fields=['status', 'execution_log'])
            return "No devices selected for bulk operation."
        
        config_payload = change_req.config_payload
        vendor = change_req.vendor
        
        log_results = []
        success_count = 0
        failed_count = 0
        
        max_workers = min(devices.count(), 20)
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_device = {
                executor.submit(
                    _atomic_device_config_push, 
                    device.id, 
                    config_payload, 
                    vendor, 
                    change_request_id
                ): device for device in devices
            }
            
            for future in as_completed(future_to_device):
                result_text = future.result()
                log_results.append(result_text)
                if "✅" in result_text:
                    success_count += 1
                else:
                    failed_count += 1
                    
        full_execution_log = f"--- Toplu İşlem Raporu ({timezone.now().strftime('%d.%m.%Y %H:%M:%S')}) ---\n"
        full_execution_log += f"Toplam Cihaz: {devices.count()} | Başarılı: {success_count} | Başarısız: {failed_count}\n\n"
        full_execution_log += "\n".join(log_results)
        
        change_req.execution_log = full_execution_log
        
        if failed_count == 0:
            change_req.status = 'approved'
        elif success_count == 0:
            change_req.status = 'failed'
        else:
            change_req.status = 'failed'  
            
        change_req.save(update_fields=['status', 'execution_log'])
        
        SystemLog.objects.create(
            action='CONFIG',
            details=f"Toplu Konfigürasyon Dağıtımı Tamamlandı. CR: #{change_request_id}. Başarı: {success_count}/{devices.count()}"
        )
        
        return f"Bulk configuration pipeline executed. CR #{change_request_id} processed."
        
    except ChangeRequest.DoesNotExist:
        return f"Error: ChangeRequest ID #{change_request_id} not found."

# ========================================================
# --- DENETİM VE UYUMLULUK RAPORU (AUDIT REPORT) ---
# ========================================================
@shared_task(soft_time_limit=3600, time_limit=3660)
def generate_and_send_audit_report():
    """Haftalık denetim raporu (Audit Report) oluşturur ve yöneticilere PDF olarak e-postalar."""
    end_date = timezone.now()
    start_date = end_date - timedelta(days=7)
    
    recent_logs = SystemLog.objects.filter(created_at__gte=start_date).order_by('-created_at')
    
    archive_dir = Path(settings.BASE_DIR) / 'archives'
    archive_dir.mkdir(parents=True, exist_ok=True)
    pdf_filename = f"OmniOps_Haftalik_Denetim_Raporu_{end_date.strftime('%Y%m%d')}.pdf"
    pdf_path = archive_dir / pdf_filename

    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib import colors
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet

        doc = SimpleDocTemplate(str(pdf_path), pagesize=A4)
        styles = getSampleStyleSheet()
        elements = []

        elements.append(Paragraph("Haftalık Sistem Denetim Raporu (ISO 27001 / KVKK)", styles['Heading1']))
        elements.append(Paragraph(f"Tarih Aralığı: {start_date.strftime('%d.%m.%Y')} - {end_date.strftime('%d.%m.%Y')}", styles['Normal']))
        elements.append(Spacer(1, 12))

        rows = [['Tarih', 'İşlem', 'Kullanıcı', 'Detay']]
        for log in recent_logs[:150]: # En son 150 hareketi rapora koy
            user_str = log.user.username if log.user else 'Sistem'
            detay = log.details[:80] + "..." if len(log.details) > 80 else log.details
            rows.append([log.created_at.strftime('%Y-%m-%d %H:%M'), log.action, user_str, detay])

        if len(rows) > 1:
            table = Table(rows, colWidths=[100, 80, 80, 250])
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#113231')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
                ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f8fafc')),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ]))
            elements.append(table)
        else:
            elements.append(Paragraph("Bu hafta için kaydedilmiş denetim logu bulunmuyor.", styles['Normal']))

        doc.build(elements)

        admin_emails = [admin[1] for admin in getattr(settings, 'ADMINS', [('Admin', 'admin@omniops.local')])]
        if not admin_emails:
            admin_emails = ['admin@firma.com'] 

        email = EmailMessage(
            subject=f"[OmniOps] Haftalık Denetim Raporu - {end_date.strftime('%d.%m.%Y')}",
            body="Merhaba,\n\nSon 7 güne ait sistem hareketlerini, cihaz değişiklik taleplerini ve güvenlik ihlallerini içeren haftalık denetim raporu (Audit Report) ektedir.\n\nİyi çalışmalar,\nOmniOps AIOps Sistemi",
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@omniops.local'),
            to=admin_emails,
        )
        email.attach_file(str(pdf_path))
        email.send(fail_silently=True)

        SystemLog.objects.create(action='SYSTEM', details="Haftalık denetim raporu (Audit Report) PDF olarak oluşturuldu ve yöneticilere e-postalandı.")
        return "Denetim Raporu başarıyla gönderildi."

    except Exception as e:
        SystemLog.objects.create(action='SYSTEM', details=f"Denetim raporu oluşturulurken hata: {e}")
        return f"Hata: {e}"