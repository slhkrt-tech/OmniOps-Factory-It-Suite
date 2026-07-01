"""SAP OData kayıtlarını CMDB harici kayıt tablosuna yazar."""
from inventory.models import ERPExternalRecord

from .sap_client import SAPODataClient


def sync_sap_to_cmdb(connection, limit=50):
    client = SAPODataClient(
        connection.base_url,
        connection.username,
        connection.api_key,
        service_path=connection.database_name or '',
    )
    client.test_connection()
    synced = 0
    if connection.sync_partners:
        partners = client.preview_business_partners(limit=limit)
        for partner in partners:
            ext_id = str(partner.get('BusinessPartner') or partner.get('ID') or synced)
            title = partner.get('BusinessPartnerName') or partner.get('Name') or ext_id
            if connection.sync_to_cmdb:
                ERPExternalRecord.objects.update_or_create(
                    connection=connection,
                    external_model='BusinessPartner',
                    external_id=ext_id,
                    defaults={'title': str(title)[:200], 'payload': partner, 'factory_site': connection.factory_site},
                )
            synced += 1
    return synced, f'SAP CMDB: {synced} partner eşlendi'
