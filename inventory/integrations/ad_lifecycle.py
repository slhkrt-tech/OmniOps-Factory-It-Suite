"""Active Directory hesap yaşam döngüsü otomasyonu."""
from django.utils import timezone

from inventory.models import DirectoryConnection, DirectoryUser, SystemLog


class ADLifecycleError(Exception):
    pass


def _username_from_task(task):
    if task.directory_user_id:
        return task.directory_user.username
    slug = (task.employee_name or task.title or 'user').strip().lower().replace(' ', '.')
    return slug[:150] or 'new.user'


def _connection_for_task(task):
    if task.directory_user_id:
        return task.directory_user.connection
    return DirectoryConnection.objects.filter(sync_enabled=True).order_by('id').first()


def provision_directory_user(task, actor=None):
    """Kimlik görevinden directory snapshot kullanıcı kaydı oluşturur/günceller."""
    if task.status not in ('open', 'in_progress', 'waiting_approval'):
        raise ADLifecycleError('Görev durumu uygun değil.')
    connection = _connection_for_task(task)
    if not connection:
        raise ADLifecycleError('Directory bağlantısı bulunamadı.')
    username = _username_from_task(task)
    user, created = DirectoryUser.objects.update_or_create(
        connection=connection,
        username=username,
        defaults={
            'display_name': task.employee_name or username,
            'department': task.department or '',
            'status': 'active',
            'last_seen_at': timezone.now(),
        },
    )
    task.directory_user = user
    task.status = 'done'
    task.ad_account_done = True
    task.notes = f'{(task.notes or "").strip()}\nAD: {"oluşturuldu" if created else "güncellendi"} · {username}'.strip()
    task.save(update_fields=['directory_user', 'status', 'ad_account_done', 'notes', 'updated_at'])
    SystemLog.objects.create(
        action='SYSTEM',
        details=f'AD lifecycle provision: {username} ({task.get_process_type_display()})',
        user=actor,
    )
    return user, task.notes


def disable_directory_user(task, actor=None):
    """Offboarding görevinde directory kullanıcısını pasifleştirir."""
    user = task.directory_user
    if not user:
        connection = _connection_for_task(task)
        username = _username_from_task(task)
        if not connection:
            raise ADLifecycleError('Directory bağlantısı bulunamadı.')
        user = DirectoryUser.objects.filter(connection=connection, username=username).first()
    if not user:
        raise ADLifecycleError('Directory kullanıcısı bulunamadı.')
    user.status = 'disabled'
    user.last_seen_at = timezone.now()
    user.save(update_fields=['status', 'last_seen_at', 'updated_at'])
    task.directory_user = user
    task.status = 'done'
    task.ad_account_done = True
    task.notes = f'{(task.notes or "").strip()}\nAD devre dışı: {user.username}'.strip()
    task.save(update_fields=['directory_user', 'status', 'ad_account_done', 'notes', 'updated_at'])
    SystemLog.objects.create(
        action='SYSTEM',
        details=f'AD lifecycle disable: {user.username}',
        user=actor,
    )
    return user, task.notes


def run_identity_lifecycle_task(task, actor=None):
    """Görev tipine göre uygun lifecycle işlemini çalıştırır."""
    if task.process_type in ('onboarding', 'transfer'):
        return provision_directory_user(task, actor=actor)
    if task.process_type == 'offboarding':
        return disable_directory_user(task, actor=actor)
    raise ADLifecycleError(f'Desteklenmeyen süreç tipi: {task.process_type}')
