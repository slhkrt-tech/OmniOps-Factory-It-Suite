"""Teams/Slack/e-posta/webhook bildirim gönderimi."""
import json
import urllib.error
import urllib.request

from django.conf import settings
from django.core.mail import EmailMessage
from django.db import models
from django.utils import timezone

from inventory.models import NotificationChannel


class NotificationError(Exception):
    pass


def send_notification(channel, title, message, payload=None):
    payload = payload or {}
    if channel.channel_type == 'email':
        _send_email(channel, title, message)
    elif channel.channel_type in ('teams', 'slack', 'webhook', 'pagerduty'):
        _send_webhook(channel, title, message, payload)
    else:
        raise NotificationError(f'Desteklenmeyen kanal tipi: {channel.channel_type}')
    channel.last_sent_at = timezone.now()
    channel.save(update_fields=['last_sent_at', 'updated_at'])


def broadcast_event(event_type, title, message, factory_site=None, payload=None):
    qs = NotificationChannel.objects.filter(is_active=True)
    if factory_site:
        qs = qs.filter(models.Q(factory_site=factory_site) | models.Q(factory_site__isnull=True))
    flag_map = {
        'ticket': 'notify_tickets',
        'incident': 'notify_incidents',
        'sla': 'notify_sla_breach',
    }
    flag = flag_map.get(event_type)
    sent = 0
    for channel in qs:
        if flag and not getattr(channel, flag, True):
            continue
        try:
            send_notification(channel, title, message, payload)
            sent += 1
        except (NotificationError, OSError, urllib.error.URLError):
            continue
    return sent


def _send_webhook(channel, title, message, payload):
    if not channel.endpoint_url:
        raise NotificationError('Webhook URL tanımlı değil.')
    body = json.dumps({'title': title, 'text': message, 'payload': payload}).encode('utf-8')
    request = urllib.request.Request(channel.endpoint_url, data=body, method='POST')
    request.add_header('Content-Type', 'application/json')
    token = channel.get_secret_plain()
    if token:
        request.add_header('Authorization', f'Bearer {token}')
    try:
        with urllib.request.urlopen(request, timeout=15):
            return
    except urllib.error.HTTPError as exc:
        raise NotificationError(f'Webhook HTTP {exc.code}') from exc


def _send_email(channel, title, message):
    recipients = [item.strip() for item in channel.email_recipients.split(',') if item.strip()]
    if not recipients:
        raise NotificationError('E-posta alıcısı yok.')
    if not settings.EMAIL_HOST:
        raise NotificationError('SMTP yapılandırılmamış.')
    email = EmailMessage(
        subject=title,
        body=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=recipients,
    )
    email.send(fail_silently=False)
