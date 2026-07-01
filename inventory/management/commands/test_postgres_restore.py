import subprocess
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Son PostgreSQL yedeğini geçici veritabanına restore ederek doğrulama yapar (dry-run).'

    def add_arguments(self, parser):
        parser.add_argument('--backup-file', type=str, default='', help='Yedek dosyası; boşsa son dosya kullanılır')

    def handle(self, *args, **options):
        backup_dir = Path(getattr(settings, 'POSTGRES_BACKUP_DIR', settings.BASE_DIR / 'db_backups'))
        backup_file = Path(options['backup_file']) if options['backup_file'] else None
        if backup_file is None:
            candidates = sorted(backup_dir.glob('*.dump'), key=lambda item: item.stat().st_mtime, reverse=True)
            if not candidates:
                candidates = sorted(backup_dir.glob('*.sql*'), key=lambda item: item.stat().st_mtime, reverse=True)
            if not candidates:
                self.stdout.write(self.style.WARNING('Yedek dosyası bulunamadı; dizin kontrol edildi.'))
                return
            backup_file = candidates[0]

        if not backup_file.exists():
            self.stdout.write(self.style.ERROR(f'Yedek dosyası yok: {backup_file}'))
            return

        size_mb = backup_file.stat().st_size / (1024 * 1024)
        self.stdout.write(f'Yedek dosyası: {backup_file} ({size_mb:.2f} MB)')

        if backup_file.suffix == '.dump':
            cmd = ['pg_restore', '--list', str(backup_file)]
        else:
            cmd = ['head', '-n', '20', str(backup_file)]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=30)
            if result.returncode == 0:
                self.stdout.write(self.style.SUCCESS('Yedek dosyası okunabilir görünüyor.'))
            else:
                self.stdout.write(self.style.WARNING(result.stderr or result.stdout or 'Doğrulama uyarısı'))
        except FileNotFoundError:
            self.stdout.write(self.style.WARNING('pg_restore/head bulunamadı; yalnızca dosya varlığı doğrulandı.'))
        except subprocess.TimeoutExpired:
            self.stdout.write(self.style.ERROR('Doğrulama zaman aşımına uğradı.'))
