import json

from django.contrib.auth.models import User, Group
from django.core.management.base import BaseCommand
from django.db import connection

from inventory.helpdesk import ensure_default_categories, ensure_default_groups, ensure_default_permissions
from inventory.factory_bootstrap import ensure_default_factory_structure, ensure_default_qr_tags
from inventory.models import (
    BusinessApplication,
    Device,
    FactoryArea,
    FactoryDepartment,
    ITAsset,
    ManagedDocument,
    ReportTemplate,
    Runbook,
    Ticket,
    TicketCategory,
    AssetQRTag,
    ERPConnection,
)


class Command(BaseCommand):
    help = 'OmniOps kurulum/readiness kontrolü yapar; isteğe bağlı temel bootstrap işlemlerini çalıştırır.'

    def add_arguments(self, parser):
        parser.add_argument('--json', action='store_true', help='Sonucu JSON olarak yazdırır.')
        parser.add_argument('--bootstrap', action='store_true', help='Varsayılan roller, kategoriler ve izinleri oluşturur.')

    def handle(self, *args, **options):
        if options['bootstrap']:
            ensure_default_groups()
            ensure_default_categories()
            ensure_default_permissions()
            created_departments, created_zones = ensure_default_factory_structure()
            created_tags = ensure_default_qr_tags()
            self.stdout.write(self.style.SUCCESS(
                f"Bootstrap: {created_departments} departman, {created_zones} alt alan, {created_tags} QR etiket oluşturuldu."
            ))

        report = self._build_report(bootstrapped=options['bootstrap'])

        if options['json']:
            self.stdout.write(json.dumps(report, ensure_ascii=False, indent=2))
            return

        self.stdout.write(self.style.SUCCESS(f"OmniOps readiness skoru: %{report['score']}"))
        for check in report['checks']:
            style = self.style.SUCCESS if check['ok'] else self.style.WARNING
            self.stdout.write(style(f"- {check['title']}: {'OK' if check['ok'] else 'DİKKAT'}"))

    def _build_report(self, bootstrapped=False):
        checks = []

        try:
            with connection.cursor() as cursor:
                cursor.execute('SELECT 1')
                cursor.fetchone()
            db_ok = True
        except Exception:
            db_ok = False

        required_groups = ['Admin', 'Yönetim', 'Ağ Ekibi', 'Sistem Ekibi', 'Help Desk Ekibi']
        missing_groups = [
            name for name in required_groups
            if not Group.objects.filter(name=name).exists()
        ]

        checks.extend([
            {'title': 'Veritabanı bağlantısı', 'ok': db_ok},
            {'title': 'Superuser var', 'ok': User.objects.filter(is_superuser=True).exists()},
            {'title': 'RBAC grupları hazır', 'ok': not missing_groups, 'missing': missing_groups},
            {'title': 'Ticket kategorileri hazır', 'ok': TicketCategory.objects.exists()},
            {'title': 'İlk cihaz/veri girilmiş', 'ok': Device.objects.exists() or ITAsset.objects.exists()},
            {'title': 'Operasyon modülleri kullanılmaya başlanmış', 'ok': FactoryArea.objects.exists() or BusinessApplication.objects.exists()},
            {'title': 'Fabrika departman kartelası', 'ok': FactoryDepartment.objects.filter(is_active=True).exists()},
            {'title': 'QR/Barkod etiketleri', 'ok': AssetQRTag.objects.filter(is_active=True).exists()},
            {'title': 'ERP bağlantı kaydı', 'ok': ERPConnection.objects.exists(), 'optional': True},
            {'title': 'Runbook veya rapor şablonu var', 'ok': Runbook.objects.exists() or ReportTemplate.objects.exists()},
            {'title': 'Ticket sistemi aktif', 'ok': Ticket.objects.exists() or TicketCategory.objects.exists()},
        ])

        ok_total = len([check for check in checks if check['ok']])
        return {
            'score': int((ok_total / len(checks)) * 100),
            'bootstrapped': bootstrapped,
            'checks': checks,
        }
