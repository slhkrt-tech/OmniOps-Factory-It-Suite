import csv
import json
from pathlib import Path

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError

from inventory.models import ImmutableAuditEntry, Notification, SystemLog, Ticket


class Command(BaseCommand):
    help = 'Kullanıcıya ait kişisel verileri GDPR/KVKK dışa aktarım paketi olarak yazar.'

    def add_arguments(self, parser):
        parser.add_argument('--username', type=str, required=True)
        parser.add_argument('--output-dir', type=str, default='gdpr_exports')

    def handle(self, *args, **options):
        user = User.objects.filter(username=options['username']).first()
        if not user:
            raise CommandError('Kullanıcı bulunamadı.')

        output_dir = Path(options['output_dir'])
        output_dir.mkdir(parents=True, exist_ok=True)
        prefix = output_dir / f'gdpr_{user.username}'

        profile = {
            'username': user.username,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'is_active': user.is_active,
            'date_joined': user.date_joined.isoformat(),
            'last_login': user.last_login.isoformat() if user.last_login else None,
        }
        (prefix.with_suffix('.profile.json')).write_text(json.dumps(profile, indent=2, ensure_ascii=False), encoding='utf-8')

        tickets = Ticket.objects.filter(created_by=user).values(
            'id', 'title', 'description', 'status', 'priority', 'created_at', 'updated_at',
        )
        with (prefix.with_suffix('.tickets.csv')).open('w', newline='', encoding='utf-8') as handle:
            writer = csv.DictWriter(handle, fieldnames=['id', 'title', 'description', 'status', 'priority', 'created_at', 'updated_at'])
            writer.writeheader()
            for row in tickets:
                writer.writerow(row)

        notifications = Notification.objects.filter(user=user).values('id', 'message', 'is_read', 'created_at')
        with (prefix.with_suffix('.notifications.csv')).open('w', newline='', encoding='utf-8') as handle:
            writer = csv.DictWriter(handle, fieldnames=['id', 'message', 'is_read', 'created_at'])
            writer.writeheader()
            for row in notifications:
                writer.writerow(row)

        audit_rows = ImmutableAuditEntry.objects.filter(actor=user).values(
            'action', 'resource_type', 'resource_id', 'created_at', 'payload',
        )
        (prefix.with_suffix('.audit.json')).write_text(
            json.dumps(list(audit_rows), indent=2, default=str, ensure_ascii=False),
            encoding='utf-8',
        )

        SystemLog.objects.create(action='SYSTEM', details=f'GDPR export oluşturuldu: {user.username}', user=user)
        self.stdout.write(self.style.SUCCESS(f'GDPR paketi yazıldı: {prefix}.*'))
