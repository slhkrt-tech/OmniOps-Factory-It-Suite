"""Monitoring, VMS, WMS, backup vendor, e-posta ticket senkronizasyon hub'ı."""
import json
import imaplib
import email
import urllib.error
import urllib.request

import requests
from django.utils import timezone

from inventory.models import CameraDevice, ConsumableItem, SystemLog, Ticket


class IntegrationHubError(Exception):
    pass


def sync_monitoring_connection(connection):
    token = connection.get_api_token_plain()
    synced = 0
    message = ''

    if connection.monitor_type == 'zabbix':
        payload = {
            'jsonrpc': '2.0',
            'method': 'host.get',
            'params': {'output': ['hostid', 'name', 'status'], 'limit': 100},
            'id': 1,
        }
        if token:
            payload['auth'] = token
        resp = requests.post(
            f'{connection.base_url.rstrip("/")}/api_jsonrpc.php',
            json=payload,
            timeout=20,
        )
        resp.raise_for_status()
        body = resp.json()
        if 'error' in body:
            raise IntegrationHubError(body['error'].get('data', body['error'].get('message', 'Zabbix API hatası')))
        hosts = body.get('result', [])
        synced = len(hosts)
        message = f'Zabbix: {synced} host okundu'
    elif connection.monitor_type == 'prometheus':
        headers = {'Authorization': f'Bearer {token}'} if token else {}
        resp = requests.get(
            f'{connection.base_url.rstrip("/")}/api/v1/targets',
            headers=headers,
            timeout=20,
        )
        resp.raise_for_status()
        targets = resp.json().get('data', {}).get('activeTargets', [])
        synced = len(targets)
        message = f'Prometheus: {synced} target okundu'
    else:
        headers = {'Authorization': f'Bearer {token}'} if token else {}
        resp = requests.get(connection.base_url, headers=headers, timeout=20)
        resp.raise_for_status()
        synced = 1
        message = f'Generic monitor erişilebilir (HTTP {resp.status_code})'

    connection.last_sync_at = timezone.now()
    connection.last_sync_status = 'healthy'
    connection.last_sync_message = message
    connection.records_synced = synced
    connection.save(update_fields=['last_sync_at', 'last_sync_status', 'last_sync_message', 'records_synced', 'updated_at'])
    return synced, message


def sync_vms_connection(connection):
    token = connection.get_api_token_plain()
    auth = (connection.username, token) if connection.username else None
    headers = {'Accept': 'application/json'}
    path_map = {
        'hikvision': '/ISAPI/System/deviceInfo',
        'milestone': '/api/rest/v1/cameras',
        'genetec': '/WebSdk/entity?q=entitytype:Camera',
        'generic': '/api/cameras',
    }
    path = path_map.get(connection.vms_type, '/api/cameras')
    url = connection.base_url.rstrip('/') + path
    resp = requests.get(url, headers=headers, auth=auth, timeout=20)
    resp.raise_for_status()
    synced = 0
    site_label = connection.factory_site.display_title if connection.factory_site_id else connection.name
    if connection.sync_to_cameras:
        payload = resp.json() if resp.headers.get('Content-Type', '').startswith('application/json') else {}
        cameras = payload if isinstance(payload, list) else payload.get('cameras') or payload.get('data') or []
        for item in cameras[:100]:
            name = str(item.get('name') or item.get('cameraName') or 'VMS Camera')[:120]
            external_id = str(item.get('id') or item.get('cameraId') or item.get('uuid') or synced)
            stream_url = f'vms://{connection.id}/{external_id}'[:500]
            CameraDevice.objects.update_or_create(
                stream_url=stream_url,
                defaults={
                    'name': name,
                    'status': 'online',
                    'location': site_label[:150],
                    'last_checked_at': timezone.now(),
                },
            )
            synced += 1
    connection.last_sync_at = timezone.now()
    connection.last_sync_status = 'healthy'
    connection.last_sync_message = f'VMS sync: {synced} kamera işlendi'
    connection.save(update_fields=['last_sync_at', 'last_sync_status', 'last_sync_message', 'updated_at'])
    return synced, connection.last_sync_message


def sync_wms_connection(connection):
    url = connection.base_url.rstrip('/') + connection.assets_path
    request = urllib.request.Request(url, method='GET')
    token = connection.get_api_token_plain()
    if token:
        request.add_header('Authorization', f'Bearer {token}')
    with urllib.request.urlopen(request, timeout=20) as response:
        payload = json.loads(response.read().decode('utf-8'))
    items = payload if isinstance(payload, list) else payload.get('results') or payload.get('data') or []
    location = f'WMS:{connection.pk}:{connection.factory_site_id or "global"}'
    synced = 0
    for item in items[:200]:
        sku = str(item.get('sku') or item.get('code') or item.get('id') or synced)[:80]
        name = str(item.get('name') or item.get('title') or sku)[:150]
        qty = int(item.get('quantity') or item.get('qty') or 0)
        ConsumableItem.objects.update_or_create(
            sku=sku,
            location=location[:120],
            defaults={'name': name, 'quantity': max(qty, 0), 'category': 'other'},
        )
        synced += 1
    connection.last_sync_at = timezone.now()
    connection.last_sync_status = 'healthy'
    connection.last_sync_message = f'WMS: {synced} stok kalemi güncellendi'
    connection.save(update_fields=['last_sync_at', 'last_sync_status', 'last_sync_message', 'updated_at'])
    return synced, connection.last_sync_message


def sync_backup_vendor_connection(connection):
    headers = {'Authorization': f'Bearer {connection.get_api_token_plain()}'} if connection.get_api_token_plain() else {}
    resp = requests.get(connection.base_url.rstrip('/') + '/api/jobs', headers=headers, timeout=20)
    if resp.status_code == 404:
        resp = requests.get(connection.base_url.rstrip('/') + '/api/v1/jobs', headers=headers, timeout=20)
    resp.raise_for_status()
    jobs = resp.json() if resp.headers.get('Content-Type', '').startswith('application/json') else []
    if isinstance(jobs, dict):
        jobs = jobs.get('data') or jobs.get('results') or []
    synced = len(jobs) if isinstance(jobs, list) else 1
    connection.last_sync_at = timezone.now()
    connection.last_sync_status = 'healthy'
    connection.last_sync_message = f'{connection.get_vendor_type_display()}: {synced} backup job görüldü'
    connection.save(update_fields=['last_sync_at', 'last_sync_status', 'last_sync_message', 'updated_at'])
    return synced, connection.last_sync_message


def poll_email_ticket_inbox(inbox):
    password = inbox.get_password_plain()
    mail = imaplib.IMAP4_SSL(inbox.imap_host, inbox.imap_port)
    mail.login(inbox.username, password)
    mail.select(inbox.folder)
    status, data = mail.search(None, 'UNSEEN')
    created = 0
    if status == 'OK':
        for num in data[0].split()[:20]:
            status, msg_data = mail.fetch(num, '(RFC822)')
            if status != 'OK':
                continue
            msg = email.message_from_bytes(msg_data[0][1])
            message_id = (msg.get('Message-ID') or '').strip()
            if message_id and Ticket.objects.filter(description__contains=message_id).exists():
                mail.store(num, '+FLAGS', '\\Seen')
                continue
            subject = (msg.get('Subject') or 'E-posta Ticket')[:100]
            body = ''
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == 'text/plain':
                        body = part.get_payload(decode=True).decode(errors='ignore')[:2000]
                        break
            else:
                body = msg.get_payload(decode=True).decode(errors='ignore')[:2000]
            if message_id:
                body = f'[Message-ID: {message_id}]\n{body}'
            Ticket.objects.create(
                title=subject,
                description=body or subject,
                priority=inbox.default_priority,
                category='Diger',
                status='Acik',
                factory_site=inbox.factory_site,
            )
            mail.store(num, '+FLAGS', '\\Seen')
            created += 1
    mail.logout()
    inbox.last_poll_at = timezone.now()
    inbox.tickets_created += created
    inbox.last_message = f'{created} yeni ticket oluşturuldu'
    inbox.save(update_fields=['last_poll_at', 'tickets_created', 'last_message', 'updated_at'])
    SystemLog.objects.create(action='SYSTEM', details=f'Email inbox {inbox.name}: {inbox.last_message}')
    return created, inbox.last_message
