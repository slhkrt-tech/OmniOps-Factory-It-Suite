# Generated manually for workspace engine

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0015_enterprise_completeness'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(
            model_name='factorysite',
            name='industry_type',
            field=models.CharField(
                choices=[
                    ('textile', 'Tekstil'),
                    ('food', 'Gıda & İçecek'),
                    ('automotive', 'Otomotiv'),
                    ('chemical', 'Kimya & Plastik'),
                    ('electronics', 'Elektronik'),
                    ('pharma', 'İlaç & Sağlık'),
                    ('metal', 'Metal & Makine'),
                    ('logistics', 'Lojistik & Depo'),
                    ('energy', 'Enerji'),
                    ('solar', 'Güneş Enerjisi'),
                    ('paper', 'Kağıt & Ambalaj'),
                    ('generic', 'Genel Endüstri'),
                    ('custom', 'Özel Sektör Tanımı'),
                ],
                db_index=True,
                default='generic',
                max_length=30,
                verbose_name='Sektör',
            ),
        ),
        migrations.CreateModel(
            name='OrganizationWorkspace',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(default='OmniOps', max_length=120, verbose_name='Çalışma Alanı Adı')),
                ('primary_industry', models.CharField(
                    choices=[
                        ('textile', 'Tekstil'), ('food', 'Gıda & İçecek'), ('automotive', 'Otomotiv'),
                        ('chemical', 'Kimya & Plastik'), ('electronics', 'Elektronik'),
                        ('pharma', 'İlaç & Sağlık'), ('metal', 'Metal & Makine'),
                        ('logistics', 'Lojistik & Depo'), ('energy', 'Enerji'),
                        ('solar', 'Güneş Enerjisi'), ('paper', 'Kağıt & Ambalaj'),
                        ('generic', 'Genel Endüstri'), ('custom', 'Özel Sektör Tanımı'),
                    ],
                    db_index=True, default='generic', max_length=30, verbose_name='Birincil Sektör',
                )),
                ('custom_industry_label', models.CharField(blank=True, max_length=80, verbose_name='Özel Sektör Adı')),
                ('tagline', models.CharField(blank=True, max_length=160, verbose_name='Alt Başlık')),
                ('enabled_modules', models.JSONField(blank=True, default=list, verbose_name='Aktif Modüller')),
                ('module_labels', models.JSONField(blank=True, default=dict, verbose_name='Modül Etiketleri')),
                ('terminology', models.JSONField(blank=True, default=dict, verbose_name='Terminoloji')),
                ('feature_overrides', models.JSONField(blank=True, default=dict, verbose_name='Özellik Bayrakları')),
                ('is_active', models.BooleanField(db_index=True, default=True, verbose_name='Aktif Profil')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Güncelleme')),
            ],
            options={
                'verbose_name': 'Kurum Çalışma Alanı',
                'verbose_name_plural': 'Kurum Çalışma Alanları',
            },
        ),
        migrations.CreateModel(
            name='UserWorkspacePreference',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('dashboard_layout', models.JSONField(blank=True, default=list, verbose_name='Panel Widget Sırası')),
                ('sidebar_layout', models.JSONField(blank=True, default=list, verbose_name='Menü Grup Sırası')),
                ('hidden_widgets', models.JSONField(blank=True, default=list, verbose_name="Gizli Widget'lar")),
                ('drag_drop_enabled', models.BooleanField(default=True, verbose_name='Sürükle-Bırak Aktif')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Güncelleme')),
                ('active_factory_site', models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name='active_for_users', to='inventory.factorysite', verbose_name='Aktif Tesis',
                )),
                ('user', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='workspace_preference', to=settings.AUTH_USER_MODEL, verbose_name='Kullanıcı',
                )),
            ],
            options={
                'verbose_name': 'Kullanıcı Çalışma Alanı Tercihi',
                'verbose_name_plural': 'Kullanıcı Çalışma Alanı Tercihleri',
            },
        ),
    ]
