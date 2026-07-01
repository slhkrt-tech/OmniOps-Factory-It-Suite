"""ERPNext REST API istemcisi (Frappe token kimlik doğrulama)."""
import requests

from .erp_connector import ERPClientError


class ERPNextClient:
    """ERPNext / Frappe REST API istemcisi."""

    def __init__(self, base_url, api_key, api_secret):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.api_secret = api_secret
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'token {api_key}:{api_secret}',
            'Accept': 'application/json',
        })
        self.session.timeout = 15

    def _get(self, path, params=None):
        url = f'{self.base_url}{path}'
        try:
            response = self.session.get(url, params=params or {})
            response.raise_for_status()
            return response.json()
        except requests.RequestException as exc:
            raise ERPClientError(f'ERPNext isteği başarısız: {exc}') from exc

    def test_connection(self):
        user = self._get('/api/method/frappe.auth.get_logged_user')
        logged_user = user.get('message') if isinstance(user, dict) else 'unknown'
        customers = self._get('/api/resource/Customer', params={'limit_page_length': 1})
        customer_total = customers.get('data', []) if isinstance(customers, dict) else []
        return {
            'server_version': 'ERPNext',
            'uid': logged_user,
            'partner_count': len(customer_total),
            'logged_user': logged_user,
        }

    def list_customers(self, limit=25):
        payload = self._get('/api/resource/Customer', params={'limit_page_length': limit, 'fields': '["name","customer_name","email_id"]'})
        return payload.get('data', []) if isinstance(payload, dict) else []

    def count_items(self):
        payload = self._get('/api/resource/Item', params={'limit_page_length': 1, 'fields': '["name"]'})
        data = payload.get('data', []) if isinstance(payload, dict) else []
        return len(data)


def sync_erpnext_connection(connection, limit=50):
    client = ERPNextClient(connection.base_url, connection.username, connection.api_key)
    synced = 0
    messages = []

    if connection.sync_partners:
        customers = client.list_customers(limit=limit)
        synced += len(customers)
        messages.append(f'{len(customers)} müşteri okundu')

    if connection.sync_products:
        item_count = client.count_items()
        synced += min(item_count, limit)
        messages.append(f'{item_count} ürün kaydı görüldü')

    if connection.sync_helpdesk:
        try:
            issues = client._get('/api/resource/Issue', params={'limit_page_length': limit, 'fields': '["name","subject"]'})
            issue_rows = issues.get('data', []) if isinstance(issues, dict) else []
            synced += len(issue_rows)
            messages.append(f'{len(issue_rows)} destek kaydı okundu')
        except ERPClientError:
            messages.append('Issue modülü bulunamadı veya erişilemedi')

    return synced, '; '.join(messages) or 'Senkronizasyon tamamlandı'
