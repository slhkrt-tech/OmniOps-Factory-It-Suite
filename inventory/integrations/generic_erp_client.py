"""Genel REST tabanlı ERP bağlantı testi (other tipi)."""
import requests
from requests.auth import HTTPBasicAuth

from .erp_connector import ERPClientError


class GenericERPClient:
    """Herhangi bir HTTP REST ERP/API uç noktası için temel sağlık kontrolü."""

    HEALTH_PATHS = ('', '/health', '/api/health', '/api/v1/health', '/status')

    def __init__(self, base_url, username='', password=''):
        self.base_url = base_url.rstrip('/')
        self.auth = HTTPBasicAuth(username, password) if username and password else None
        self.session = requests.Session()
        self.session.timeout = 10

    def test_connection(self):
        last_error = None
        for path in self.HEALTH_PATHS:
            url = f'{self.base_url}{path}'
            try:
                response = self.session.get(url, auth=self.auth, allow_redirects=True)
                if response.status_code < 500:
                    return {
                        'server_version': 'Generic REST',
                        'uid': self.auth.username if self.auth else 'anonymous',
                        'partner_count': 0,
                        'endpoint': url,
                        'status_code': response.status_code,
                    }
                last_error = f'HTTP {response.status_code}'
            except requests.RequestException as exc:
                last_error = str(exc)
        raise ERPClientError(f'Genel ERP bağlantı testi başarısız: {last_error}')


def sync_generic_connection(connection, limit=50):
    client = GenericERPClient(connection.base_url, connection.username, connection.api_key)
    result = client.test_connection()
    synced = 1
    messages = [f"Uç nokta erişilebilir: {result.get('endpoint')} ({result.get('status_code')})"]
    if connection.sync_partners or connection.sync_products or connection.sync_helpdesk:
        messages.append('Detaylı veri sync bu ERP tipi için yalnızca erişim testi yapar')
    return synced, '; '.join(messages)
