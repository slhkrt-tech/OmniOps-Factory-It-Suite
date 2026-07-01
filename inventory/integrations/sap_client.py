"""SAP OData servis istemcisi (temel okuma ve bağlantı testi)."""
import requests
from requests.auth import HTTPBasicAuth

from .erp_connector import ERPClientError


class SAPODataClient:
    """SAP Gateway OData servisleri için HTTP Basic Auth istemcisi."""

    DEFAULT_CATALOG = '/sap/opu/odata/iwfnd/catalogservice;v=2/ServiceCollection'

    def __init__(self, base_url, username, password, service_path=''):
        self.base_url = base_url.rstrip('/')
        self.username = username
        self.password = password
        self.service_path = service_path.strip() or self.DEFAULT_CATALOG
        self.session = requests.Session()
        self.session.auth = HTTPBasicAuth(username, password)
        self.session.headers.update({'Accept': 'application/json'})
        self.session.timeout = 20

    def _get(self, path, params=None):
        url = f'{self.base_url}{path}'
        try:
            response = self.session.get(url, params=params or {})
            if response.status_code >= 400:
                raise ERPClientError(f'SAP OData HTTP {response.status_code}: {response.text[:200]}')
            if 'application/json' in response.headers.get('Content-Type', ''):
                return response.json()
            return {'status_code': response.status_code, 'length': len(response.content)}
        except requests.RequestException as exc:
            raise ERPClientError(f'SAP OData isteği başarısız: {exc}') from exc

    def test_connection(self):
        payload = self._get(self.service_path)
        service_count = 0
        if isinstance(payload, dict):
            results = payload.get('d', {}).get('results', [])
            service_count = len(results)
        return {
            'server_version': 'SAP OData',
            'uid': self.username,
            'partner_count': service_count,
            'service_path': self.service_path,
        }

    def preview_business_partners(self, limit=25):
        path = '/sap/opu/odata/sap/API_BUSINESS_PARTNER/A_BusinessPartner'
        payload = self._get(path, params={'$top': limit, '$format': 'json'})
        if isinstance(payload, dict):
            return payload.get('d', {}).get('results', [])
        return []


def sync_sap_connection(connection, limit=50):
    client = SAPODataClient(
        connection.base_url,
        connection.username,
        connection.api_key,
        service_path=connection.database_name or '',
    )
    synced = 0
    messages = []

    if connection.sync_partners:
        try:
            partners = client.preview_business_partners(limit=limit)
            synced += len(partners)
            messages.append(f'{len(partners)} iş ortağı okundu')
        except ERPClientError as exc:
            messages.append(f'Business Partner okunamadı: {exc}')

    if connection.sync_products:
        try:
            payload = client._get('/sap/opu/odata/sap/API_PRODUCT_SRV/A_Product', params={'$top': 1, '$format': 'json'})
            results = payload.get('d', {}).get('results', []) if isinstance(payload, dict) else []
            synced += min(len(results), limit)
            messages.append(f'Ürün servisi erişilebilir ({len(results)} örnek)')
        except ERPClientError:
            messages.append('Ürün servisi bu SAP sisteminde bulunamadı')

    if connection.sync_helpdesk:
        messages.append('SAP helpdesk sync bu sürümde manuel servis yolu gerektirir')

    return synced, '; '.join(messages) or 'Senkronizasyon tamamlandı'
