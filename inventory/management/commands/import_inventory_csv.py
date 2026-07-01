import csv
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from inventory.models import DepartmentInventoryItem, FactorySite


class Command(BaseCommand):
    help = 'CSV dosyasından bölüm envanter kalemlerini içe aktarır.'

    def add_arguments(self, parser):
        parser.add_argument('csv_path', type=str, help='CSV dosya yolu')
        parser.add_argument('--site-code', type=str, required=True, help='FactorySite code (ör. SITE-TEXTILE)')
        parser.add_argument('--department-code', type=str, default='', help='Opsiyonel departman kodu filtresi')

    def handle(self, *args, **options):
        csv_path = Path(options['csv_path'])
        if not csv_path.exists():
            raise CommandError(f'Dosya bulunamadı: {csv_path}')

        site = FactorySite.objects.filter(code=options['site_code']).first()
        if not site:
            raise CommandError(f'Tesis bulunamadı: {options["site_code"]}')

        created = updated = 0
        with csv_path.open(newline='', encoding='utf-8-sig') as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                code = (row.get('code') or row.get('sku') or row.get('reference_code') or '').strip()
                if not code:
                    continue
                department = None
                if options['department_code']:
                    department = site.departments.filter(code=options['department_code']).first()
                defaults = {
                    'title': (row.get('name') or row.get('title') or code)[:180],
                    'item_type': (row.get('item_type') or 'other')[:30],
                    'category_label': (row.get('category') or '')[:100],
                    'quantity': int(row.get('quantity') or 1),
                    'status': (row.get('status') or 'active')[:20],
                    'location_note': (row.get('location') or '')[:150],
                    'is_active': str(row.get('is_active', 'true')).lower() not in ('0', 'false', 'no'),
                    'department': department,
                }
                obj, was_created = DepartmentInventoryItem.objects.update_or_create(
                    factory_site=site,
                    reference_code=code[:60],
                    defaults=defaults,
                )
                if was_created:
                    created += 1
                else:
                    updated += 1

        self.stdout.write(self.style.SUCCESS(f'Import tamamlandı: {created} yeni, {updated} güncellendi.'))
