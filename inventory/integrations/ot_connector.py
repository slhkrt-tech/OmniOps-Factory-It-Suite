"""OT/MES/SCADA REST köprüsü — üretim varlıklarını envantere aktarır."""
import json
import urllib.error
import urllib.request

from django.utils import timezone

from inventory.models import DepartmentInventoryItem, OTAssetRecord, OTConnection, SystemLog


class OTClientError(Exception):
    """OT köprü hatası."""


def test_ot_connection(connection):
    assets, _ = _fetch_ot_assets(connection, limit=1)
    return {'asset_sample': len(assets), 'endpoint': connection.base_url.rstrip('/') + connection.assets_path}


def sync_ot_connection(connection, limit=100):
    if not connection.is_ready:
        raise OTClientError('OT bağlantısı yapılandırılmamış.')

    assets, raw_count = _fetch_ot_assets(connection, limit=limit)
    now = timezone.now()
    synced = 0
    inventory_created = 0
    site = connection.factory_site

    for asset in assets:
        external_id = str(asset.get('id') or asset.get('tag') or asset.get('name') or synced)[:120]
        title = str(asset.get('name') or asset.get('title') or external_id)[:200]
        tag_name = str(asset.get('tag') or asset.get('plc_tag') or '')[:120]
        asset_type = str(asset.get('type') or asset.get('asset_type') or connection.get_ot_type_display())[:80]
        status = _map_ot_status(asset.get('status'))

        record, _ = OTAssetRecord.objects.update_or_create(
            connection=connection,
            external_id=external_id,
            defaults={
                'tag_name': tag_name,
                'title': title,
                'asset_type': asset_type,
                'status': status,
                'payload': asset,
                'last_seen_at': now,
            },
        )
        synced += 1

        if connection.sync_to_inventory and site:
            department = site.departments.filter(is_active=True).order_by('department_type').first()
            inventory_item, created = DepartmentInventoryItem.objects.update_or_create(
                factory_site=site,
                reference_code=f'OT-{connection.id}-{external_id}',
                defaults={
                    'department': department,
                    'title': title,
                    'item_type': 'production',
                    'category_label': asset_type or 'OT Varlık',
                    'quantity': 1,
                    'status': 'active' if status == 'online' else 'maintenance',
                    'location_note': tag_name,
                    'is_active': True,
                },
            )
            record.inventory_item = inventory_item
            record.department = department
            record.save(update_fields=['inventory_item', 'department', 'synced_at'])
            if created:
                inventory_created += 1

    connection.last_sync_at = now
    connection.last_sync_status = 'healthy'
    connection.last_sync_message = (
        f'{synced} OT varlık işlendi (kaynak {raw_count}); '
        f'{inventory_created} yeni envanter kalemi.'
    )
    connection.records_synced = synced
    connection.save(update_fields=[
        'last_sync_at', 'last_sync_status', 'last_sync_message', 'records_synced', 'updated_at',
    ])
    SystemLog.objects.create(
        action='SYSTEM',
        details=f'OT sync OK · {connection.name}: {connection.last_sync_message}',
    )
    return synced, connection.last_sync_message


def _fetch_ot_assets(connection, limit=100):
    url = connection.base_url.rstrip('/') + connection.assets_path
    request = urllib.request.Request(url, method='GET')
    api_key = connection.get_api_key_plain()
    if api_key:
        request.add_header('Authorization', f'Bearer {api_key}')
    request.add_header('Accept', 'application/json')
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = json.loads(response.read().decode('utf-8'))
    except urllib.error.HTTPError as exc:
        raise OTClientError(f'OT API HTTP {exc.code}: {exc.reason}') from exc
    except Exception as exc:
        raise OTClientError(f'OT API erişim hatası: {exc}') from exc

    if isinstance(payload, list):
        items = payload
    elif isinstance(payload, dict):
        items = payload.get('results') or payload.get('assets') or payload.get('data') or []
    else:
        items = []
    return items[:limit], len(items)


def _map_ot_status(value):
    raw = str(value or '').lower()
    if raw in ('online', 'running', 'ok', 'active'):
        return 'online'
    if raw in ('offline', 'stopped', 'down'):
        return 'offline'
    if raw in ('maintenance', 'service'):
        return 'maintenance'
    return 'unknown'
