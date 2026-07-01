"""ERP bağlantı yönlendiricisi: Odoo, ERPNext ve SAP OData istemcilerini birleştirir."""


class ERPClientError(Exception):
    """ERP bağlantı ve senkronizasyon hataları için ortak istisna."""


def test_erp_connection(connection):
    """ERP tipine göre bağlantı testi yapar."""
    if connection.erp_type == 'odoo':
        from .odoo_client import OdooClient
        client = OdooClient(connection.base_url, connection.database_name, connection.username, connection.api_key)
        return client.test_connection()
    if connection.erp_type == 'erpnext':
        from .erpnext_client import ERPNextClient
        client = ERPNextClient(connection.base_url, connection.username, connection.api_key)
        return client.test_connection()
    if connection.erp_type == 'sap':
        from .sap_client import SAPODataClient
        client = SAPODataClient(
            connection.base_url,
            connection.username,
            connection.api_key,
            service_path=connection.database_name or '',
        )
        return client.test_connection()
    raise ERPClientError(f'{connection.get_erp_type_display()} için test henüz desteklenmiyor.')


def sync_erp_connection(connection, limit=50):
    """ERP tipine göre önizleme senkronizasyonu yapar."""
    if connection.erp_type == 'odoo':
        from .odoo_client import sync_odoo_connection
        return sync_odoo_connection(connection, limit=limit)
    if connection.erp_type == 'erpnext':
        from .erpnext_client import sync_erpnext_connection
        return sync_erpnext_connection(connection, limit=limit)
    if connection.erp_type == 'sap':
        from .sap_client import sync_sap_connection
        return sync_sap_connection(connection, limit=limit)
    raise ERPClientError(f'{connection.get_erp_type_display()} sync henüz desteklenmiyor.')
