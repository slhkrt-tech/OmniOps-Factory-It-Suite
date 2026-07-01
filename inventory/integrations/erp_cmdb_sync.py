"""ERP kayıtlarını OmniOps CMDB ve envanter modellerine yazar."""

from inventory.models import ConsumableItem, DepartmentInventoryItem, ERPExternalRecord

from .erp_connector import ERPClientError


def sync_erp_connection_to_cmdb(connection, limit=50):
    """ERP verisini okur ve CMDB/envantere kalıcı yazar."""
    if connection.erp_type == 'odoo':
        return _sync_odoo_to_cmdb(connection, limit=limit)
    if connection.erp_type == 'erpnext':
        return _sync_erpnext_to_cmdb(connection, limit=limit)
    if connection.erp_type in ('sap', 'other'):
        from .erp_connector import sync_erp_connection as preview_sync
        count, message = preview_sync(connection, limit=limit)
        if connection.sync_to_cmdb:
            message = f'{message}; CMDB yazımı bu ERP tipi için harici kayıt önizlemesi ile sınırlı.'
        return count, message
    raise ERPClientError(f'{connection.get_erp_type_display()} CMDB sync desteklenmiyor.')


def _sync_odoo_to_cmdb(connection, limit=50):
    from .odoo_client import OdooClient

    client = OdooClient(connection.base_url, connection.database_name, connection.username, connection.api_key)
    client.authenticate()
    synced = 0
    messages = []
    site = connection.factory_site

    if connection.sync_partners:
        partners = client.sync_partners_preview(limit=limit)
        for partner in partners:
            ext_id = str(partner.get('id', ''))
            title = partner.get('name') or f'Partner {ext_id}'
            if connection.sync_to_cmdb:
                ERPExternalRecord.objects.update_or_create(
                    connection=connection,
                    external_model='res.partner',
                    external_id=ext_id,
                    defaults={
                        'title': title,
                        'payload': partner,
                        'factory_site': site,
                    },
                )
            synced += 1
        messages.append(f'{len(partners)} partner')

    if connection.sync_products:
        products = client.execute(
            'product.product', 'search_read',
            [[('active', '=', True)]],
            {'fields': ['name', 'default_code', 'qty_available', 'categ_id'], 'limit': limit},
        )
        for product in products:
            ext_id = str(product.get('id', ''))
            title = product.get('name') or f'Product {ext_id}'
            sku = product.get('default_code') or f'ERP-{ext_id}'
            qty = int(product.get('qty_available') or 0)
            consumable = None
            inventory_item = None
            if connection.sync_to_cmdb:
                consumable, _ = ConsumableItem.objects.update_or_create(
                    sku=sku,
                    defaults={
                        'name': title,
                        'category': 'spare',
                        'quantity': max(qty, 0),
                        'vendor': connection.name,
                    },
                )
                if site:
                    inventory_item, _ = DepartmentInventoryItem.objects.update_or_create(
                        factory_site=site,
                        reference_code=f'ERP-{connection.id}-{ext_id}',
                        defaults={
                            'title': title,
                            'item_type': 'consumable',
                            'category_label': 'ERP Stok',
                            'quantity': max(qty, 1),
                            'consumable': consumable,
                            'status': 'active',
                            'is_active': True,
                        },
                    )
                ERPExternalRecord.objects.update_or_create(
                    connection=connection,
                    external_model='product.product',
                    external_id=ext_id,
                    defaults={
                        'title': title,
                        'payload': product,
                        'factory_site': site,
                        'consumable': consumable,
                        'inventory_item': inventory_item,
                    },
                )
            synced += 1
        messages.append(f'{len(products)} ürün')

    if connection.sync_helpdesk and connection.sync_to_cmdb:
        ticket_models = ['helpdesk.ticket', 'project.task']
        for model_name in ticket_models:
            try:
                tickets = client.execute(
                    model_name, 'search_read', [[]],
                    {'fields': ['name', 'description', 'stage_id'], 'limit': min(limit, 20)},
                )
                for ticket in tickets:
                    ext_id = str(ticket.get('id', ''))
                    ERPExternalRecord.objects.update_or_create(
                        connection=connection,
                        external_model=model_name,
                        external_id=ext_id,
                        defaults={
                            'title': ticket.get('name') or f'Ticket {ext_id}',
                            'payload': ticket,
                            'factory_site': site,
                        },
                    )
                    synced += 1
                messages.append(f'{len(tickets)} {model_name}')
                break
            except Exception:
                continue

    return synced, '; '.join(messages) or 'CMDB sync tamamlandı'


def _sync_erpnext_to_cmdb(connection, limit=50):
    from .erpnext_client import ERPNextClient

    client = ERPNextClient(connection.base_url, connection.username, connection.api_key)
    synced = 0
    messages = []
    site = connection.factory_site

    if connection.sync_partners:
        partners = client.list_customers(limit=limit)
        for partner in partners:
            ext_id = str(partner.get('name', ''))
            title = partner.get('customer_name') or ext_id
            if connection.sync_to_cmdb:
                ERPExternalRecord.objects.update_or_create(
                    connection=connection,
                    external_model='Customer',
                    external_id=ext_id,
                    defaults={'title': title, 'payload': partner, 'factory_site': site},
                )
            synced += 1
        messages.append(f'{len(partners)} müşteri')

    if connection.sync_products:
        payload = client._get(
            '/api/resource/Item',
            params={'limit_page_length': limit, 'fields': '["name","item_name","item_code"]'},
        )
        items = payload.get('data', []) if isinstance(payload, dict) else []
        for item in items:
            ext_id = str(item.get('name', ''))
            title = item.get('item_name') or ext_id
            sku = ext_id
            consumable = None
            inventory_item = None
            if connection.sync_to_cmdb:
                consumable, _ = ConsumableItem.objects.update_or_create(
                    sku=sku,
                    defaults={'name': title, 'category': 'spare', 'quantity': 0, 'vendor': connection.name},
                )
                if site:
                    inventory_item, _ = DepartmentInventoryItem.objects.update_or_create(
                        factory_site=site,
                        reference_code=f'ERP-{connection.id}-{ext_id}',
                        defaults={
                            'title': title,
                            'item_type': 'consumable',
                            'category_label': 'ERPNext Stok',
                            'quantity': 1,
                            'consumable': consumable,
                            'status': 'active',
                            'is_active': True,
                        },
                    )
                ERPExternalRecord.objects.update_or_create(
                    connection=connection,
                    external_model='Item',
                    external_id=ext_id,
                    defaults={
                        'title': title,
                        'payload': item,
                        'factory_site': site,
                        'consumable': consumable,
                        'inventory_item': inventory_item,
                    },
                )
            synced += 1
        messages.append(f'{len(items)} kalem')

    return synced, '; '.join(messages) or 'ERPNext CMDB sync tamamlandı'
