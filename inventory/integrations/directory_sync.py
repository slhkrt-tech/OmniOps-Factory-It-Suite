"""Active Directory / LDAP / Azure AD gerçek senkronizasyonu."""
import logging

import requests
from django.conf import settings
from django.contrib.auth.models import Group, User
from django.utils import timezone

from inventory.models import DirectoryConnection, DirectoryGroup, DirectoryUser, SystemLog

logger = logging.getLogger(__name__)


class DirectorySyncError(Exception):
    """Directory senkronizasyon hatası."""


def run_directory_sync(connection, actor=None, dry_run=None):
    """Bağlantı tipine göre gerçek directory senkronizasyonu."""
    if dry_run is None:
        dry_run = getattr(settings, 'DIRECTORY_SYNC_DRY_RUN', False)

    if not connection:
        return False, 'Directory bağlantısı bulunamadı.'

    if connection.directory_type == 'manual':
        return _sync_manual_snapshot(connection, actor)

    if not connection.is_ready:
        connection.last_sync_at = timezone.now()
        connection.last_sync_status = 'warning'
        connection.last_sync_message = 'Directory bağlantı bilgileri eksik veya sync kapalı.'
        connection.save(update_fields=['last_sync_at', 'last_sync_status', 'last_sync_message', 'updated_at'])
        return False, connection.last_sync_message

    try:
        if connection.directory_type == 'azure_ad':
            message = sync_azure_ad_connection(connection, actor=actor, dry_run=dry_run)
        else:
            message = sync_ldap_connection(connection, actor=actor, dry_run=dry_run)
        connection.last_sync_at = timezone.now()
        connection.last_sync_status = 'healthy'
        connection.last_sync_message = message
        connection.save(update_fields=['last_sync_at', 'last_sync_status', 'last_sync_message', 'updated_at'])
        SystemLog.objects.create(
            user=actor,
            action='SYSTEM',
            details=f"Directory sync tamamlandı: {connection.name} - {message}",
        )
        return True, message
    except DirectorySyncError as exc:
        connection.last_sync_at = timezone.now()
        connection.last_sync_status = 'failed'
        connection.last_sync_message = str(exc)
        connection.save(update_fields=['last_sync_at', 'last_sync_status', 'last_sync_message', 'updated_at'])
        SystemLog.objects.create(
            user=actor,
            action='SYSTEM',
            details=f"Directory sync hata: {connection.name} - {exc}",
        )
        return False, str(exc)


def sync_ldap_connection(connection, actor=None, dry_run=False):
    try:
        from ldap3 import ALL, SUBTREE, Connection, Server
        from ldap3.core.exceptions import LDAPException
    except ImportError as exc:
        raise DirectorySyncError('ldap3 paketi yüklü değil. requirements.txt içinden kurun.') from exc

    password = connection.get_bind_password_plain()
    if not password:
        raise DirectorySyncError('LDAP bind parolası tanımlı değil.')

    uri = connection.server_uri or getattr(settings, 'LDAP_SERVER_URI', '')
    base_dn = connection.base_dn or getattr(settings, 'LDAP_BASE_DN', '')
    bind_user = connection.bind_username or getattr(settings, 'LDAP_BIND_USERNAME', '')

    if not uri or not base_dn:
        raise DirectorySyncError('LDAP server_uri ve base_dn zorunludur.')

    try:
        server = Server(uri, get_info=ALL)
        ldap_conn = Connection(server, user=bind_user, password=password, auto_bind=True)
    except LDAPException as exc:
        raise DirectorySyncError(f'LDAP bağlantısı kurulamadı: {exc}') from exc

    now = timezone.now()
    seen_users = set()
    seen_groups = set()
    user_count = 0
    group_count = 0
    provisioned = 0

    user_attrs = ['sAMAccountName', 'uid', 'cn', 'mail', 'displayName', 'department', 'title', 'manager',
                  'distinguishedName', 'userAccountControl', 'memberOf']
    ldap_conn.search(
        base_dn, connection.user_filter, search_scope=SUBTREE, attributes=user_attrs,
    )
    for entry in ldap_conn.entries:
        username = _ldap_attr(entry, 'sAMAccountName') or _ldap_attr(entry, 'uid') or _ldap_attr(entry, 'cn')
        if not username:
            continue
        username = str(username).split('\\')[-1][:150]
        seen_users.add(username.lower())
        status = _ldap_user_status(entry)
        group_dns = _ldap_attr_list(entry, 'memberOf')
        if dry_run:
            user_count += 1
            continue
        directory_user, _ = DirectoryUser.objects.update_or_create(
            connection=connection,
            username=username,
            defaults={
                'display_name': _ldap_attr(entry, 'displayName') or username,
                'email': _ldap_attr(entry, 'mail') or '',
                'department': _ldap_attr(entry, 'department') or '',
                'title': _ldap_attr(entry, 'title') or '',
                'manager': _ldap_attr(entry, 'manager') or '',
                'distinguished_name': _ldap_attr(entry, 'distinguishedName') or str(entry.entry_dn),
                'status': status,
                'last_seen_at': now,
            },
        )
        user_count += 1
        if connection.auto_provision_users and status == 'active':
            provisioned += _provision_django_user(directory_user, connection)
        directory_user.groups.clear()
        for group_dn in group_dns:
            group_name = _dn_to_cn(group_dn)
            if not group_name:
                continue
            directory_group, _ = DirectoryGroup.objects.update_or_create(
                connection=connection,
                name=group_name,
                defaults={
                    'distinguished_name': group_dn,
                    'last_seen_at': now,
                },
            )
            directory_user.groups.add(directory_group)
            seen_groups.add(group_name.lower())

    ldap_conn.search(
        base_dn, connection.group_filter, search_scope=SUBTREE,
        attributes=['cn', 'name', 'description', 'distinguishedName'],
    )
    for entry in ldap_conn.entries:
        group_name = _ldap_attr(entry, 'cn') or _ldap_attr(entry, 'name')
        if not group_name:
            continue
        group_name = str(group_name)[:180]
        seen_groups.add(group_name.lower())
        if dry_run:
            group_count += 1
            continue
        DirectoryGroup.objects.update_or_create(
            connection=connection,
            name=group_name,
            defaults={
                'description': _ldap_attr(entry, 'description') or '',
                'distinguished_name': _ldap_attr(entry, 'distinguishedName') or str(entry.entry_dn),
                'last_seen_at': now,
            },
        )
        group_count += 1

    if not dry_run:
        DirectoryUser.objects.filter(connection=connection).exclude(
            username__in=[u for u in seen_users]
        ).update(status='disabled', last_seen_at=now)

    prefix = '[DRY-RUN] ' if dry_run else ''
    return (
        f"{prefix}LDAP sync: {user_count} kullanıcı, {group_count} grup; "
        f"{provisioned} OmniOps kullanıcısı güncellendi."
    )


def sync_azure_ad_connection(connection, actor=None, dry_run=False):
    tenant_id = connection.azure_tenant_id or getattr(settings, 'SOCIAL_AUTH_AZUREAD_OAUTH2_TENANT_ID', '')
    client_id = connection.bind_username or getattr(settings, 'SOCIAL_AUTH_AZUREAD_OAUTH2_KEY', '')
    client_secret = connection.get_bind_password_plain() or getattr(settings, 'SOCIAL_AUTH_AZUREAD_OAUTH2_SECRET', '')

    if not tenant_id or not client_id or not client_secret:
        raise DirectorySyncError('Azure AD için tenant_id, client_id ve client_secret gerekli.')

    token_url = f'https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token'
    token_resp = requests.post(
        token_url,
        data={
            'client_id': client_id,
            'client_secret': client_secret,
            'scope': 'https://graph.microsoft.com/.default',
            'grant_type': 'client_credentials',
        },
        timeout=30,
    )
    if token_resp.status_code >= 400:
        raise DirectorySyncError(f'Azure token alınamadı: {token_resp.text[:200]}')
    access_token = token_resp.json().get('access_token')
    if not access_token:
        raise DirectorySyncError('Azure access token boş döndü.')

    headers = {'Authorization': f'Bearer {access_token}'}
    now = timezone.now()
    user_count = 0
    group_count = 0
    provisioned = 0
    next_url = 'https://graph.microsoft.com/v1.0/users?$select=id,userPrincipalName,displayName,mail,department,jobTitle,accountEnabled'

    while next_url:
        resp = requests.get(next_url, headers=headers, timeout=30)
        if resp.status_code >= 400:
            raise DirectorySyncError(f'Graph users API hatası: {resp.text[:200]}')
        payload = resp.json()
        for item in payload.get('value', []):
            username = (item.get('userPrincipalName') or item.get('id') or '')[:150]
            if not username:
                continue
            status = 'active' if item.get('accountEnabled', True) else 'disabled'
            if dry_run:
                user_count += 1
                continue
            directory_user, _ = DirectoryUser.objects.update_or_create(
                connection=connection,
                username=username,
                defaults={
                    'display_name': item.get('displayName') or username,
                    'email': item.get('mail') or '',
                    'department': item.get('department') or '',
                    'title': item.get('jobTitle') or '',
                    'distinguished_name': item.get('id') or '',
                    'status': status,
                    'last_seen_at': now,
                },
            )
            user_count += 1
            if connection.auto_provision_users and status == 'active':
                provisioned += _provision_django_user(directory_user, connection)
        next_url = payload.get('@odata.nextLink')

    groups_url = 'https://graph.microsoft.com/v1.0/groups?$select=id,displayName,description'
    resp = requests.get(groups_url, headers=headers, timeout=30)
    if resp.status_code < 400:
        for item in resp.json().get('value', []):
            name = (item.get('displayName') or item.get('id') or '')[:180]
            if not name:
                continue
            if dry_run:
                group_count += 1
                continue
            DirectoryGroup.objects.update_or_create(
                connection=connection,
                name=name,
                defaults={
                    'description': item.get('description') or '',
                    'distinguished_name': item.get('id') or '',
                    'last_seen_at': now,
                },
            )
            group_count += 1

    prefix = '[DRY-RUN] ' if dry_run else ''
    return (
        f"{prefix}Azure AD sync: {user_count} kullanıcı, {group_count} grup; "
        f"{provisioned} OmniOps kullanıcısı güncellendi."
    )


def _sync_manual_snapshot(connection, actor=None):
    """Manuel bağlantı tipi için lokal kullanıcı snapshot (geliştirme/CSV sonrası)."""
    now = timezone.now()
    created_users = 0
    local_users = User.objects.filter(is_active=True).order_by('username')[:200]
    for user in local_users:
        try:
            department = user.profile.department
        except Exception:
            department = ''
        directory_user, created = DirectoryUser.objects.update_or_create(
            connection=connection,
            username=user.username,
            defaults={
                'user': user,
                'display_name': user.get_full_name() or user.username,
                'email': user.email or '',
                'department': department,
                'status': 'active',
                'last_seen_at': now,
            },
        )
        if created:
            created_users += 1
    connection.last_sync_at = now
    connection.last_sync_status = 'healthy'
    connection.last_sync_message = f'Manuel snapshot: {local_users.count()} kullanıcı, {created_users} yeni.'
    connection.save(update_fields=['last_sync_at', 'last_sync_status', 'last_sync_message', 'updated_at'])
    return True, connection.last_sync_message


def _provision_django_user(directory_user, connection):
    username = directory_user.username.split('@')[0][:150]
    email = directory_user.email or ''
    user, created = User.objects.get_or_create(
        username=username,
        defaults={
            'email': email,
            'first_name': (directory_user.display_name or '')[:30],
            'is_active': directory_user.status == 'active',
        },
    )
    if not created:
        user.email = email or user.email
        user.is_active = directory_user.status == 'active'
        user.save(update_fields=['email', 'is_active'])
    directory_user.user = user
    directory_user.save(update_fields=['user', 'updated_at'])
    for group in directory_user.groups.all():
        if group.mapped_role:
            django_group, _ = Group.objects.get_or_create(name=group.mapped_role)
            user.groups.add(django_group)
    return 1 if created else 0


def _ldap_attr(entry, name):
    if name not in entry:
        return ''
    value = entry[name].value
    if value is None:
        return ''
    return str(value)


def _ldap_attr_list(entry, name):
    if name not in entry:
        return []
    value = entry[name].value
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [str(item) for item in value]
    return [str(value)]


def _ldap_user_status(entry):
    uac = _ldap_attr(entry, 'userAccountControl')
    try:
        if uac and int(uac) & 2:
            return 'disabled'
    except (TypeError, ValueError):
        pass
    return 'active'


def _dn_to_cn(distinguished_name):
    for part in str(distinguished_name).split(','):
        part = part.strip()
        if part.upper().startswith('CN='):
            return part[3:]
    return str(distinguished_name).split(',')[0][:180]
