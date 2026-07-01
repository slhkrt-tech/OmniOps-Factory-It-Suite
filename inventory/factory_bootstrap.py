"""Fabrika tesis portföyü ve bölüm envanter bootstrap verisi."""

from inventory.models import (
    AssetQRTag, ConsumableItem, DepartmentInventoryItem,
    FactoryArea, FactoryDepartment, FactorySite, FactoryZone, Device, ITAsset,
)


SITE_PORTFOLIO = [
    {
        'code': 'SITE-TEXTILE-01',
        'title': 'Deniz Tekstil Üretim Tesisi',
        'short_name': 'Deniz Tekstil',
        'industry_type': 'textile',
        'customer_name': 'Deniz Tekstil A.Ş.',
        'portfolio_code': 'PORT-DENIZ',
        'inventory_panel_title': 'Dokuma & Terbiye Envanteri',
        'department_label': 'Atölye',
        'zone_label': 'Hat / Bölüm',
        'city': 'Bursa',
        'departments': [
            {
                'name': 'Dokuma', 'code': 'DOKUMA', 'department_type': 'production', 'criticality': 'high',
                'manager_name': 'Dokuma Şefi', 'floor_label': 'A Blok',
                'zones': [
                    {'name': 'Airjet Hat 1', 'code': 'AIR-01', 'zone_type': 'production_line', 'criticality': 'high'},
                    {'name': 'Terbiye', 'code': 'TER-01', 'zone_type': 'production_line', 'criticality': 'medium'},
                ],
                'inventory': [
                    {'title': 'Airjet Dokuma Makinesi #3', 'item_type': 'production', 'category_label': 'Dokuma Makinesi', 'quantity': 1},
                    {'title': 'PLC Kontrol Paneli', 'item_type': 'production', 'category_label': 'Otomasyon', 'quantity': 2},
                ],
            },
            {
                'name': 'Kalite & Laboratuvar', 'code': 'KALITE', 'department_type': 'quality', 'criticality': 'medium',
                'manager_name': 'Kalite Müdürü', 'floor_label': 'B Blok',
                'zones': [{'name': 'Fiziksel Test Lab', 'code': 'LAB-01', 'zone_type': 'room', 'criticality': 'medium'}],
                'inventory': [
                    {'title': 'Renk Matching Spectrofotometre', 'item_type': 'tool', 'category_label': 'Laboratuvar', 'quantity': 1},
                ],
            },
            {
                'name': 'Bilgi İşlem', 'code': 'BIT', 'department_type': 'it', 'criticality': 'critical',
                'manager_name': 'BT Sorumlusu', 'floor_label': '2. Kat',
                'zones': [{'name': 'Sistem Odası', 'code': 'SYS-01', 'zone_type': 'server_room', 'criticality': 'critical'}],
                'inventory': [
                    {'title': 'MES Sunucusu', 'item_type': 'it_asset', 'category_label': 'Sunucu', 'quantity': 1},
                    {'title': 'Core Switch', 'item_type': 'network', 'category_label': 'Ağ', 'quantity': 1},
                ],
            },
        ],
    },
    {
        'code': 'SITE-FOOD-01',
        'title': 'Anadolu Gıda İşleme Tesisi',
        'short_name': 'Anadolu Gıda',
        'industry_type': 'food',
        'customer_name': 'Anadolu Gıda San.',
        'portfolio_code': 'PORT-ANADOLU',
        'inventory_panel_title': 'Hat & Hijyen Envanteri',
        'department_label': 'Birim',
        'zone_label': 'Hat / Oda',
        'city': 'Konya',
        'departments': [
            {
                'name': 'Pastörizasyon', 'code': 'PASTOR', 'department_type': 'production', 'criticality': 'critical',
                'manager_name': 'Hat Sorumlusu', 'floor_label': 'Üretim',
                'zones': [{'name': 'Pastörizasyon Hattı', 'code': 'HAT-01', 'zone_type': 'production_line', 'criticality': 'critical'}],
                'inventory': [
                    {'title': 'Pastörizasyon Ünitesi', 'item_type': 'production', 'category_label': 'Proses Ekipmanı', 'quantity': 1},
                    {'title': 'Sıcaklık Sensör Ağı', 'item_type': 'production', 'category_label': 'SCADA/IoT', 'quantity': 12, 'unit': 'nokta'},
                ],
            },
            {
                'name': 'Soğuk Depo', 'code': 'DEPO', 'department_type': 'warehouse', 'criticality': 'high',
                'manager_name': 'Depo Sorumlusu', 'floor_label': 'Zemin',
                'zones': [{'name': 'Soğuk Hava Deposu', 'code': 'COLD-01', 'zone_type': 'warehouse', 'criticality': 'high'}],
                'inventory': [
                    {'title': 'Forklift Termal', 'item_type': 'vehicle', 'category_label': 'Depo Aracı', 'quantity': 2},
                ],
            },
            {
                'name': 'Kalite & Gıda Güvenliği', 'code': 'GIDA-GUV', 'department_type': 'quality', 'criticality': 'high',
                'manager_name': 'Gıda Güvenliği Uzmanı', 'floor_label': '1. Kat',
                'zones': [{'name': 'Numune Laboratuvarı', 'code': 'LAB-01', 'zone_type': 'room', 'criticality': 'medium'}],
                'inventory': [
                    {'title': 'HACCP Kayıt Terminali', 'item_type': 'endpoint', 'category_label': 'Kayıt Sistemi', 'quantity': 3},
                ],
            },
        ],
    },
    {
        'code': 'SITE-AUTO-01',
        'title': 'Vega Otomotiv Yan Sanayi',
        'short_name': 'Vega Otomotiv',
        'industry_type': 'automotive',
        'customer_name': 'Vega Metal Otomotiv',
        'portfolio_code': 'PORT-VEGA',
        'inventory_panel_title': 'Pres & Montaj Envanteri',
        'department_label': 'Departman',
        'zone_label': 'Hücre / Hat',
        'city': 'Kocaeli',
        'departments': [
            {
                'name': 'Pres & Kaynak', 'code': 'PRES', 'department_type': 'production', 'criticality': 'high',
                'manager_name': 'Pres Atölye Şefi', 'floor_label': 'Hale 1',
                'zones': [{'name': 'Pres Hattı A', 'code': 'PRS-A', 'zone_type': 'production_line', 'criticality': 'high'}],
                'inventory': [
                    {'title': '500T Hidrolik Pres', 'item_type': 'production', 'category_label': 'Pres', 'quantity': 1},
                    {'title': 'Robot Kaynak Hücresi', 'item_type': 'production', 'category_label': 'Robotik', 'quantity': 2},
                ],
            },
            {
                'name': 'Montaj', 'code': 'MONTAJ', 'department_type': 'production', 'criticality': 'medium',
                'manager_name': 'Montaj Sorumlusu', 'floor_label': 'Hale 2',
                'zones': [{'name': 'Final Montaj', 'code': 'MNT-01', 'zone_type': 'production_line', 'criticality': 'medium'}],
                'inventory': [
                    {'title': 'Tork Anahtarı Seti', 'item_type': 'tool', 'category_label': 'Montaj Takım', 'quantity': 8},
                ],
            },
            {
                'name': 'Bilgi İşlem', 'code': 'BIT', 'department_type': 'it', 'criticality': 'critical',
                'manager_name': 'IT Koordinatörü', 'floor_label': 'Ofis',
                'zones': [{'name': 'Network Closet', 'code': 'NET-01', 'zone_type': 'room', 'criticality': 'high'}],
                'inventory': [
                    {'title': 'ERP Terminal Farm', 'item_type': 'endpoint', 'category_label': 'ERP Erişim', 'quantity': 15},
                ],
            },
        ],
    },
]


def ensure_default_factory_structure():
    """Portföy tesisleri, bölümleri, alt alanları ve örnek envanter kayıtlarını oluşturur."""
    created_sites = 0
    created_departments = 0
    created_zones = 0
    created_inventory = 0
    factory_area = FactoryArea.objects.order_by('id').first()

    for site_item in SITE_PORTFOLIO:
        site, site_created = FactorySite.objects.get_or_create(
            code=site_item['code'],
            defaults={
                'title': site_item['title'],
                'short_name': site_item.get('short_name', ''),
                'industry_type': site_item['industry_type'],
                'customer_name': site_item.get('customer_name', ''),
                'portfolio_code': site_item.get('portfolio_code', ''),
                'inventory_panel_title': site_item.get('inventory_panel_title', 'Bölüm Envanteri'),
                'department_label': site_item.get('department_label', 'Bölüm'),
                'zone_label': site_item.get('zone_label', 'Alt Alan'),
                'city': site_item.get('city', ''),
                'is_active': True,
            },
        )
        if site_created:
            created_sites += 1

        for dept_item in site_item.get('departments', []):
            department, dept_created = FactoryDepartment.objects.get_or_create(
                factory_site=site,
                code=dept_item['code'],
                defaults={
                    'name': dept_item['name'],
                    'department_type': dept_item['department_type'],
                    'criticality': dept_item['criticality'],
                    'manager_name': dept_item.get('manager_name', ''),
                    'floor_label': dept_item.get('floor_label', ''),
                    'description': f"{site.title} · {dept_item['name']}",
                    'is_active': True,
                },
            )
            if dept_created:
                created_departments += 1

            zone_map = {}
            for zone_item in dept_item.get('zones', []):
                zone, zone_created = FactoryZone.objects.get_or_create(
                    department=department,
                    code=zone_item['code'],
                    defaults={
                        'name': zone_item['name'],
                        'zone_type': zone_item['zone_type'],
                        'criticality': zone_item['criticality'],
                        'factory_area': factory_area if zone_item['zone_type'] in ('server_room', 'production_line', 'camera_zone') else None,
                        'is_active': True,
                    },
                )
                zone_map[zone_item['code']] = zone
                if zone_created:
                    created_zones += 1

            for inv_item in dept_item.get('inventory', []):
                ref = inv_item.get('reference_code') or f"{site.code}-{dept_item['code']}-{inv_item['title'][:20].upper().replace(' ', '-')}"
                _, inv_created = DepartmentInventoryItem.objects.get_or_create(
                    factory_site=site,
                    department=department,
                    reference_code=ref,
                    defaults={
                        'title': inv_item['title'],
                        'item_type': inv_item.get('item_type', 'other'),
                        'category_label': inv_item.get('category_label', ''),
                        'quantity': inv_item.get('quantity', 1),
                        'unit': inv_item.get('unit', 'adet'),
                        'status': 'active',
                        'is_active': True,
                    },
                )
                if inv_created:
                    created_inventory += 1

    return created_sites, created_departments, created_zones, created_inventory


def ensure_default_qr_tags():
    """Örnek QR etiketleri oluşturur (idempotent)."""
    created = 0
    for zone in FactoryZone.objects.filter(is_active=True).select_related('department__factory_site').order_by('id')[:12]:
        site_code = zone.department.factory_site.code if zone.department and zone.department.factory_site_id else 'SITE'
        code = f'OMNI-{site_code}-{zone.code}'
        _, was_created = AssetQRTag.objects.get_or_create(
            code=code,
            defaults={
                'tag_type': 'factory_zone',
                'label': zone.name,
                'location': zone.department.name if zone.department_id else '',
                'factory_zone': zone,
                'is_active': True,
            },
        )
        if was_created:
            created += 1

    for device in Device.objects.order_by('id')[:5]:
        code = f'OMNI-DEV-{device.id:04d}'
        _, was_created = AssetQRTag.objects.get_or_create(
            code=code,
            defaults={'tag_type': 'device', 'label': device.name, 'device': device, 'is_active': True},
        )
        if was_created:
            created += 1

    for asset in ITAsset.objects.order_by('id')[:5]:
        if not asset.serial_number:
            continue
        code = f'OMNI-AST-{asset.serial_number[:20]}'
        _, was_created = AssetQRTag.objects.get_or_create(
            code=code,
            defaults={'tag_type': 'it_asset', 'label': asset.name, 'it_asset': asset, 'is_active': True},
        )
        if was_created:
            created += 1

    return created
