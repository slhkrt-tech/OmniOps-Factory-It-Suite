"""
Django settings for core project.
"""

from pathlib import Path
from datetime import timedelta # Token süresi hesaplamak için
from celery.schedules import crontab # Zamanlanmış görevler için
import os
import dj_database_url
from django.utils.translation import gettext_lazy as _
from dotenv import load_dotenv

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env')

# SECURITY: load sensitive settings from environment in production
# NOTE: Keep the fallback values only for local development/testing.
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'django-insecure-for-dev-only-please-set-env')

# DEBUG should be False in production; enable via DJANGO_DEBUG env var if needed
DEBUG = os.environ.get('DJANGO_DEBUG', 'False').lower() in ('1', 'true', 'yes')

ALLOWED_HOSTS = [host.strip() for host in os.environ.get('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',') if host.strip()]
CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in os.environ.get('CSRF_TRUSTED_ORIGINS', '').split(',')
    if origin.strip()
]

# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',
    'social_django',
    'inventory.apps.InventoryConfig',
    'rest_framework', 
    'django_filters', # API Filtreleme Motoru
    'drf_spectacular', # Swagger API Dokümantasyonu
    'guardian', # YENİ: Nesne Bazlı Yetkilendirme (OLP)
]

SITE_ID = 1

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.locale.LocaleMiddleware', # YENİ: Dil değiştirme altyapısı
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'inventory.middleware.audit_middleware.AuditMiddleware',
]

ROOT_URLCONF = 'core.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'social_django.context_processors.backends',
                'social_django.context_processors.login_redirect',
                'inventory.context_processors.notification_context',
            ],
        },
    },
]

WSGI_APPLICATION = 'core.wsgi.application'

# Database
DATABASES = {
    'default': dj_database_url.config(
        default=os.environ.get('DATABASE_URL', f'sqlite:///{BASE_DIR / "db.sqlite3"}'),
        conn_max_age=600,
        conn_health_checks=True,
    )
}

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {'min_length': 10},
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# ==========================================
# --- YENİ: I18N (ÇOKLU DİL) AYARLARI ---
# ==========================================
LANGUAGE_CODE = 'tr'

TIME_ZONE = 'Europe/Istanbul'

USE_I18N = True
USE_L10N = True
USE_TZ = True

# Desteklenen diller
LANGUAGES = [
    ('tr', _('Türkçe')),
    ('en', _('English')),
]

# Çeviri dosyalarının duracağı klasör
LOCALE_PATHS = [
    os.path.join(BASE_DIR, 'locale'),
]

# --- SSO / OAuth2 / OpenID Connect / Azure AD Ayarları ---
SOCIAL_AUTH_URL_NAMESPACE = 'social'
SOCIAL_AUTH_LOGIN_REDIRECT_URL = '/'
SOCIAL_AUTH_LOGIN_ERROR_URL = '/login/'
SOCIAL_AUTH_USERNAME_IS_FULL_EMAIL = True
SOCIAL_AUTH_ADMIN_USER_SEARCH_FIELDS = ['username', 'email']

# Azure AD / Okta / Keycloak için placeholder ayarlar
SOCIAL_AUTH_AZUREAD_OAUTH2_KEY = os.environ.get('SOCIAL_AUTH_AZUREAD_OAUTH2_KEY', '')
SOCIAL_AUTH_AZUREAD_OAUTH2_SECRET = os.environ.get('SOCIAL_AUTH_AZUREAD_OAUTH2_SECRET', '')
SOCIAL_AUTH_AZUREAD_OAUTH2_TENANT_ID = os.environ.get('SOCIAL_AUTH_AZUREAD_OAUTH2_TENANT_ID', '')

SOCIAL_AUTH_OIDC_ENABLED = True
SOCIAL_AUTH_OIDC_KEY = os.environ.get('SOCIAL_AUTH_OIDC_KEY', '')
SOCIAL_AUTH_OIDC_SECRET = os.environ.get('SOCIAL_AUTH_OIDC_SECRET', '')
SOCIAL_AUTH_OIDC_ENDPOINT = os.environ.get('SOCIAL_AUTH_OIDC_ENDPOINT', '')

# Directory / Active Directory operasyon merkezi ayarları
LDAP_ENABLED = os.environ.get('LDAP_ENABLED', 'False').lower() in ('1', 'true', 'yes')
LDAP_SERVER_URI = os.environ.get('LDAP_SERVER_URI', '')
LDAP_BASE_DN = os.environ.get('LDAP_BASE_DN', '')
LDAP_BIND_USERNAME = os.environ.get('LDAP_BIND_USERNAME', '')
LDAP_BIND_PASSWORD = os.environ.get('LDAP_BIND_PASSWORD', '')
LDAP_USER_FILTER = os.environ.get('LDAP_USER_FILTER', '(objectClass=user)')
LDAP_GROUP_FILTER = os.environ.get('LDAP_GROUP_FILTER', '(objectClass=group)')
DIRECTORY_SYNC_DRY_RUN = os.environ.get('DIRECTORY_SYNC_DRY_RUN', 'False').lower() in ('1', 'true', 'yes')
ALLOW_PUBLIC_REGISTRATION = os.environ.get('ALLOW_PUBLIC_REGISTRATION', 'False').lower() in ('1', 'true', 'yes')
SITE_ACCESS_ENFORCEMENT = os.environ.get('SITE_ACCESS_ENFORCEMENT', 'True').lower() in ('1', 'true', 'yes')
FEATURE_SALES_KANBAN = os.environ.get('FEATURE_SALES_KANBAN', 'True').lower() in ('1', 'true', 'yes')
PROMETHEUS_METRICS_ENABLED = os.environ.get('PROMETHEUS_METRICS_ENABLED', 'True').lower() in ('1', 'true', 'yes')
PROMETHEUS_METRICS_TOKEN = os.environ.get('PROMETHEUS_METRICS_TOKEN', '')

# OnlyOffice / Collabora belge sunucusu (tarayıcı editörü)
ONLYOFFICE_DOCUMENT_SERVER_URL = os.environ.get('ONLYOFFICE_DOCUMENT_SERVER_URL', '')
ONLYOFFICE_JWT_SECRET = os.environ.get('ONLYOFFICE_JWT_SECRET', '')
DOCUMENT_EDITOR_BACKEND = os.environ.get('DOCUMENT_EDITOR_BACKEND', 'auto')
COLLABORA_SERVER_URL = os.environ.get('COLLABORA_SERVER_URL', '')
WOPI_SECRET = os.environ.get('WOPI_SECRET', '')

POSTGRES_BACKUP_DIR = os.environ.get('POSTGRES_BACKUP_DIR', os.path.join(BASE_DIR, 'db_backups'))
POSTGRES_BACKUP_FORMAT = os.environ.get('POSTGRES_BACKUP_FORMAT', 'custom')
PG_DUMP_PATH = os.environ.get('PG_DUMP_PATH', 'pg_dump')
POSTGRES_BACKUP_FILE_PREFIX = os.environ.get('POSTGRES_BACKUP_FILE_PREFIX', 'omniops_backup')

AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID', '')
AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY', '')
AWS_S3_BACKUP_BUCKET = os.environ.get('AWS_S3_BACKUP_BUCKET', '')
AWS_S3_REGION_NAME = os.environ.get('AWS_S3_REGION_NAME', '')

REMOTE_PROBE_SHARED_SECRET = os.environ.get('REMOTE_PROBE_SHARED_SECRET', '')
VAULT_KEY = os.environ.get('VAULT_KEY', '')

DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', 'noreply@omniops.local')
EMAIL_HOST = os.environ.get('EMAIL_HOST', '')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', '587'))
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
EMAIL_USE_TLS = os.environ.get('EMAIL_USE_TLS', 'True').lower() in ('1', 'true', 'yes')
EMAIL_BACKEND = (
    'django.core.mail.backends.smtp.EmailBackend'
    if EMAIL_HOST else
    'django.core.mail.backends.console.EmailBackend'
)

def _parse_admins(value):
    admins = []
    for item in value.split(','):
        item = item.strip()
        if not item:
            continue
        if ':' in item:
            name, email = item.split(':', 1)
        else:
            name, email = 'Admin', item
        admins.append((name.strip(), email.strip()))
    return admins

ADMINS = _parse_admins(os.environ.get('ADMINS', ''))

# ==========================================

# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'

STATICFILES_DIRS = [
    BASE_DIR / 'static',
]
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

FILE_UPLOAD_MAX_MEMORY_SIZE = int(os.environ.get('FILE_UPLOAD_MAX_MEMORY_SIZE', str(5 * 1024 * 1024)))
DATA_UPLOAD_MAX_MEMORY_SIZE = int(os.environ.get('DATA_UPLOAD_MAX_MEMORY_SIZE', str(10 * 1024 * 1024)))
DATA_UPLOAD_MAX_NUMBER_FIELDS = int(os.environ.get('DATA_UPLOAD_MAX_NUMBER_FIELDS', '2000'))

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# --- GİRİŞ / ÇIKIŞ YÖNLENDİRMELERİ ---
LOGIN_REDIRECT_URL = '/'  # Giriş başarılıysa ana sayfaya git
LOGIN_URL = 'login'       # Giriş yapmamış biri zorlanırsa buraya at

# --- DJANGO REST FRAMEWORK AYARLARI ---
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 10,
    'DEFAULT_FILTER_BACKENDS': ['django_filters.rest_framework.DjangoFilterBackend'],
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': os.environ.get('DRF_ANON_RATE', '20/minute'),
        'user': os.environ.get('DRF_USER_RATE', '100/minute'),
    },
}

# --- JWT (JSON Web Token) AYARLARI ---
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=60), 
    'REFRESH_TOKEN_LIFETIME': timedelta(days=1),    
}

# --- SWAGGER / OPENAPI AYARLARI ---
SPECTACULAR_SETTINGS = {
    'TITLE': 'OmniOps API',
    'DESCRIPTION': 'Ağ Cihazları, IPAM, Otomatik Konfigürasyon ve Bilet Yönetim Sistemi',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'COMPONENT_SPLIT_REQUEST': True,
    'ENUM_NAME_OVERRIDES': {
        'TicketStatusEnum': 'inventory.models.Ticket.STATUS_CHOICES',
        'RemoteProbeStatusEnum': 'inventory.models.RemoteProbe.STATUS_CHOICES',
        'FieldVisitStatusEnum': 'inventory.models.FieldVisit.STATUS_CHOICES',
        'ITAssetStatusEnum': 'inventory.models.ITAsset.STATUS_CHOICES',
        'ChangeRequestStatusEnum': 'inventory.models.ChangeRequest.STATUS_CHOICES',
        'FactoryAreaCriticalityEnum': 'inventory.models.FactoryArea.CRITICALITY_CHOICES',
        'ProcurementStatusEnum': 'inventory.models.ProcurementRequest.STATUS_CHOICES',
        'ProcurementCategoryEnum': 'inventory.models.ProcurementRequest.CATEGORY_CHOICES',
        'BackupJobStatusEnum': 'inventory.models.BackupJobMonitor.STATUS_CHOICES',
        'VendorSupportStatusEnum': 'inventory.models.VendorSupportCase.STATUS_CHOICES',
        'MajorIncidentSeverityEnum': 'inventory.models.MajorIncident.SEVERITY_CHOICES',
        'MajorIncidentStatusEnum': 'inventory.models.MajorIncident.STATUS_CHOICES',
        'AccessRequestTypeEnum': 'inventory.models.AccessRequest.ACCESS_TYPE_CHOICES',
        'AccessRequestStatusEnum': 'inventory.models.AccessRequest.STATUS_CHOICES',
        'PrinterFleetKindEnum': 'inventory.models.PrinterFleetItem.DEVICE_KIND_CHOICES',
        'PrinterFleetStatusEnum': 'inventory.models.PrinterFleetItem.STATUS_CHOICES',
        'RunbookCategoryEnum': 'inventory.models.Runbook.CATEGORY_CHOICES',
        'RemoteAccessMethodEnum': 'inventory.models.RemoteAccessGrant.ACCESS_METHOD_CHOICES',
        'RemoteAccessStatusEnum': 'inventory.models.RemoteAccessGrant.STATUS_CHOICES',
        'CameraDeviceTypeEnum': 'inventory.models.CameraDevice.DEVICE_TYPE_CHOICES',
        'CameraStatusEnum': 'inventory.models.CameraDevice.STATUS_CHOICES',
        'BusinessAppTypeEnum': 'inventory.models.BusinessApplication.APP_TYPE_CHOICES',
        'BusinessAppStatusEnum': 'inventory.models.BusinessApplication.STATUS_CHOICES',
        'ReportTemplateTypeEnum': 'inventory.models.ReportTemplate.REPORT_TYPE_CHOICES',
        'ChangeCalendarEventTypeEnum': 'inventory.models.ChangeCalendarEvent.EVENT_TYPE_CHOICES',
        'ChangeCalendarStatusEnum': 'inventory.models.ChangeCalendarEvent.STATUS_CHOICES',
        'ServiceDependencyTypeEnum': 'inventory.models.ServiceDependency.DEPENDENCY_TYPE_CHOICES',
        'IntegrationHealthTypeEnum': 'inventory.models.IntegrationHealthCheck.INTEGRATION_TYPE_CHOICES',
        'IntegrationHealthStatusEnum': 'inventory.models.IntegrationHealthCheck.STATUS_CHOICES',
        'ComplianceFrameworkEnum': 'inventory.models.ComplianceControl.FRAMEWORK_CHOICES',
        'ComplianceStatusEnum': 'inventory.models.ComplianceControl.STATUS_CHOICES',
        'DocumentOutputJobTypeEnum': 'inventory.models.DocumentOutputJob.JOB_TYPE_CHOICES',
        'DocumentOutputJobStatusEnum': 'inventory.models.DocumentOutputJob.STATUS_CHOICES',
        'DirectoryConnectionTypeEnum': 'inventory.models.DirectoryConnection.DIRECTORY_TYPE_CHOICES',
        'DirectoryConnectionStatusEnum': 'inventory.models.DirectoryConnection.STATUS_CHOICES',
        'DirectoryUserStatusEnum': 'inventory.models.DirectoryUser.STATUS_CHOICES',
        'EndpointDeviceTypeEnum': 'inventory.models.EndpointDevice.DEVICE_TYPE_CHOICES',
        'EndpointDeviceStatusEnum': 'inventory.models.EndpointDevice.STATUS_CHOICES',
        'IdentityLifecycleProcessEnum': 'inventory.models.IdentityLifecycleTask.PROCESS_CHOICES',
        'IdentityLifecycleStatusEnum': 'inventory.models.IdentityLifecycleTask.STATUS_CHOICES',
        'FactoryDepartmentTypeEnum': 'inventory.models.FactoryDepartment.DEPARTMENT_TYPE_CHOICES',
        'FactoryZoneTypeEnum': 'inventory.models.FactoryZone.ZONE_TYPE_CHOICES',
        'ManagedDocumentCategoryEnum': 'inventory.models.ManagedDocument.CATEGORY_CHOICES',
        'ManagedDocumentFileTypeEnum': 'inventory.models.ManagedDocument.FILE_TYPE_CHOICES',
        'ManagedDocumentStatusEnum': 'inventory.models.ManagedDocument.STATUS_CHOICES',
        'FactoryAssetRelationTypeEnum': 'inventory.models.FactoryITAssetRelation.ASSET_TYPE_CHOICES',
        'FactoryAssetRelationRoleEnum': 'inventory.models.FactoryITAssetRelation.ROLE_CHOICES',
        'AssetQRTagTypeEnum': 'inventory.models.AssetQRTag.TAG_TYPE_CHOICES',
        'ERPConnectionTypeEnum': 'inventory.models.ERPConnection.ERP_TYPE_CHOICES',
        'ERPConnectionSyncStatusEnum': 'inventory.models.ERPConnection.SYNC_STATUS_CHOICES',
    },
}

# ==========================================
# --- CELERY & REDİS AYARLARI ---
# ==========================================
CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL', 'redis://redis:6379/0')
CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND', 'redis://redis:6379/0')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_TIMEZONE = 'Europe/Istanbul'

# ==========================================
# --- CELERY BEAT (ZAMANLANMIŞ GÖREVLER) ---
# ==========================================
CELERY_BEAT_SCHEDULE = {
    'otomatik-ag-taramasi-gece': {
        'task': 'inventory.tasks.otomatik_ag_taramasi',
        'schedule': crontab(hour=3, minute=0),
    },
    'sla-ve-lisans-uyarilari': {
        'task': 'inventory.tasks.otomatik_sla_ve_lisans_kontrolu',
        'schedule': crontab(hour=8, minute=0),
    },
    'sla-eskalasyon-kontrolu': {
        'task': 'inventory.tasks.check_sla_and_escalate',
        'schedule': crontab(minute='*/15'),
    },
    'zabbix-threshold-monitor-5dk': {
        'task': 'inventory.tasks.zabbix_threshold_monitor',
        'schedule': crontab(minute='*/5'),
    },
    'otomatik-gece-yedekleme': {
        'task': 'inventory.tasks.otomatik_gece_yedekleme',
        'schedule': crontab(hour=4, minute=0),
    },
    'ai-tahminleyici-bakim': {
        'task': 'inventory.tasks.run_predictive_maintenance',
        'schedule': crontab(hour=5, minute=0),
    },
    # VERİ ARŞİVLEME VE TEMİZLEME (DATA RETENTION POLICY)
    'veri-arsivleme-ve-temizleme': {
        'task': 'inventory.tasks.data_retention_policy_task',
        'schedule': crontab(day_of_month=1, hour=1, minute=0), # Her ayın 1'inde gece 1'de çalışır
    },
    'postgres-backup-db': {
        'task': 'inventory.tasks.postgres_dump_backup_task',
        'schedule': crontab(hour=4, minute=0),
    },
    'distributed-probe-polling': {
        'task': 'inventory.tasks.distributed_probe_polling',
        'schedule': crontab(minute='*/15'),
    },
    # YENİ EKLENDİ: DENETİM RAPORU (Her Pazartesi Sabah 08:00)
    'haftalik-denetim-raporu': {
        'task': 'inventory.tasks.generate_and_send_audit_report',
        'schedule': crontab(day_of_week='1', hour=8, minute=0), 
    },
    'kamera-health-poll-10dk': {
        'task': 'inventory.tasks.poll_camera_health_task',
        'schedule': crontab(minute='*/10'),  # Kamera/NVR erişilebilirlik kontrolü
    },
    'erp-sync-saatlik': {
        'task': 'inventory.tasks.sync_all_erp_connections_task',
        'schedule': crontab(minute=15),  # Odoo/ERP bağlantı senkronizasyonu
    },
    'directory-sync-saatlik': {
        'task': 'inventory.tasks.sync_all_directory_connections_task',
        'schedule': crontab(minute=45),
    },
    'ot-sync-saatlik': {
        'task': 'inventory.tasks.sync_all_ot_connections_task',
        'schedule': crontab(minute=30),
    },
    'entegrasyon-health-poll-15dk': {
        'task': 'inventory.tasks.poll_integration_health_task',
        'schedule': crontab(minute='*/15'),  # LDAP, SMTP, API vb. uç nokta sağlığı
    },
    'integration-hub-sync-saatlik': {
        'task': 'inventory.tasks.sync_all_integration_hub_task',
        'schedule': crontab(minute=5),
    },
}

# ==========================================
# --- OMNIOPS GÜVENLİK VE WEBHOOK AYARLARI ---
# ==========================================
WAZUH_API_KEY = os.environ.get('WAZUH_API_KEY', '')
WEBHOOK_ALLOWED_IPS = [ip.strip() for ip in os.environ.get('WEBHOOK_ALLOWED_IPS', '127.0.0.1,::1').split(',') if ip.strip()]


# ==========================================
# --- GUARDIAN VE SSO YETKİLENDİRME MOTORLARI ---
# ==========================================
# Temel motorlar (Normal şifreli giriş ve Guardian) her zaman aktif olmalı
AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend', # Django'nun varsayılan motoru (Şifreli giriş)
    'guardian.backends.ObjectPermissionBackend', # Guardian OLP motoru
]
ANONYMOUS_USER_NAME = None
GUARDIAN_GET_INIT_ANONYMOUS_USER = 'guardian.management.get_init_anonymous_user'

# SADECE .env DOSYASINDA ANAHTARLAR VARSA SSO MOTORLARINI AKTİF ET!
# Bu sayede anahtarlar boşken uygulamanın (HTTP 500) çökmesini kalıcı olarak önleriz.
if os.environ.get('SOCIAL_AUTH_AZUREAD_OAUTH2_KEY'):
    AUTHENTICATION_BACKENDS.insert(0, 'social_core.backends.azuread.AzureADOAuth2')

if os.environ.get('SOCIAL_AUTH_OIDC_KEY'):
    AUTHENTICATION_BACKENDS.insert(0, 'social_core.backends.open_id_connect.OpenIdConnectAuth')

if os.environ.get('SAML_METADATA_URL'):
    AUTHENTICATION_BACKENDS.insert(0, 'social_core.backends.saml.SAMLAuth')

# ==========================================
# --- SSO / OAUTH2 / OIDC / SAML2 AYARLARI ---
# ==========================================

# OIDC (OpenID Connect) Genel Ayarları
SOCIAL_AUTH_OIDC_ENDPOINT = os.environ.get('SOCIAL_AUTH_OIDC_ENDPOINT', '')
SOCIAL_AUTH_OIDC_KEY = os.environ.get('SOCIAL_AUTH_OIDC_KEY', '')
SOCIAL_AUTH_OIDC_SECRET = os.environ.get('SOCIAL_AUTH_OIDC_SECRET', '')

# Azure AD / Azure B2C Ayarları
SOCIAL_AUTH_AZUREAD_OAUTH2_TENANT_ID = os.environ.get('SOCIAL_AUTH_AZUREAD_OAUTH2_TENANT_ID', '')
SOCIAL_AUTH_AZUREAD_OAUTH2_KEY = os.environ.get('SOCIAL_AUTH_AZUREAD_OAUTH2_KEY', '')
SOCIAL_AUTH_AZUREAD_OAUTH2_SECRET = os.environ.get('SOCIAL_AUTH_AZUREAD_OAUTH2_SECRET', '')

# Okta Ayarları (OIDC üzerinden)
SOCIAL_AUTH_OKTA_OPENID_ENDPOINT = os.environ.get('SOCIAL_AUTH_OKTA_OPENID_ENDPOINT', '')
SOCIAL_AUTH_OKTA_OPENID_KEY = os.environ.get('SOCIAL_AUTH_OKTA_OPENID_KEY', '')
SOCIAL_AUTH_OKTA_OPENID_SECRET = os.environ.get('SOCIAL_AUTH_OKTA_OPENID_SECRET', '')

# SAML 2.0 Ayarları
SOCIAL_AUTH_SAML_ORG_INFO = {
    'en-US': {
        'name': 'OmniOps',
        'displayname': 'OmniOps - Network Management System',
        'url': os.environ.get('SAML_ORG_URL', 'https://omniops.example.com/'),
    },
}

SOCIAL_AUTH_SAML_TECHNICAL_CONTACT = {
    'givenName': 'IT Support',
    'emailAddress': os.environ.get('SAML_TECH_CONTACT_EMAIL', 'support@omniops.example.com'),
}

SOCIAL_AUTH_SAML_SUPPORT_CONTACT = {
    'givenName': 'IT Support',
    'emailAddress': os.environ.get('SAML_SUPPORT_CONTACT_EMAIL', 'support@omniops.example.com'),
}

# SAML Attribute Mapping: SAML'deki attributes'ları Django user fields'ine eşle
SOCIAL_AUTH_SAML_ATTRIBUTE_MAPPING = {
    'http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress': ('email',),
    'http://schemas.xmlsoap.org/ws/2005/05/identity/claims/givenname': ('first_name',),
    'http://schemas.xmlsoap.org/ws/2005/05/identity/claims/surname': ('last_name',),
    'http://schemas.xmlsoap.org/ws/2005/05/identity/claims/upn': ('username',),
    'groups': ('groups',),  # Grup bilgisi - Just-in-Time Provisioning için
}

# SAML Metadata dosyasının URL'si (IdP'den alınır)
SAML_METADATA_URL = os.environ.get('SAML_METADATA_URL', '')
SAML_ENTITY_ID = os.environ.get('SAML_ENTITY_ID', 'https://omniops.example.com/saml2/metadata/')
SAML_ASSERTION_CONSUMER_SERVICE_URL = os.environ.get('SAML_ACS_URL', 'https://omniops.example.com/accounts/complete/saml/')

# Social Auth Just-in-Time Provisioning Pipeline
SOCIAL_AUTH_PIPELINE = (
    'social_core.pipeline.auth.auth_allowed',
    'social_core.pipeline.auth.social_uid_from_whomami',
    'social_core.pipeline.auth.social_user',
    'social_core.pipeline.user.get_username',
    'social_core.pipeline.user.create_user',
    'inventory.sso_pipeline.update_user_role_from_sso',  # YENİ: Rol/Grup Eşleştirmesi
    'social_core.pipeline.social_auth.associate_user',
    'social_core.pipeline.social_auth.load_extra_data',
    'social_core.pipeline.user.user_details',
)

# SSO Yönlendirmeleri
SOCIAL_AUTH_LOGIN_REDIRECT_URL = '/'
SOCIAL_AUTH_NEW_USER_REDIRECT_URL = '/kullanici-paneli/'
SOCIAL_AUTH_LOGIN_ERROR_URL = '/login/'
SOCIAL_AUTH_DISCONNECT_REDIRECT_URL = '/login/'

# SSO ile giriş yapan kullanıcıları admin olarak işle (opsiyonel)
SOCIAL_AUTH_URL_NAMESPACE = 'social'
SOCIAL_AUTH_USERNAME_IS_FULL_EMAIL = True

# Kullanıcı ayrıntılarını otomatik olarak güncelle
SOCIAL_AUTH_POSTGRES_JSONFIELD = True

# ==========================================
# --- SAML2 GÜVENLİK AYARLARI ---
# ==========================================
# SAML2 sertifika ve anahtar dosyaları (üretim ortamında gerekli)
# Format: /path/to/sp.crt, /path/to/sp.key
SOCIAL_AUTH_SAML_SP_CERTIFICATE_FILE = os.environ.get('SAML_SP_CERTIFICATE_FILE', None)
SOCIAL_AUTH_SAML_SP_PRIVATE_KEY_FILE = os.environ.get('SAML_SP_PRIVATE_KEY_FILE', None)

# SAML2 imzalama ve şifreleme ayarları
SOCIAL_AUTH_SAML_SECURITY_CONFIG = {
    'nameIDFormat': 'urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress',
    'signMetadata': True,  # Metadata'yı imzala
    'wantAssertionsSigned': True,  # Assertion imzalaması iste
    'wantAssertionsEncrypted': False,  # Assertion şifrelemesi iste (mı?)
    'wantNameIDEncrypted': False,  # NameID şifrelemesi iste
}

# ==========================================
# --- OKTA / OKTA WORKFORCE İDENTİTY MANAGEMENT
# ==========================================
# Okta SAML ayarları (alternatif: OIDC)
SOCIAL_AUTH_OKTA_SAML_METADATA_URL = os.environ.get('SOCIAL_AUTH_OKTA_SAML_METADATA_URL', '')

# ==========================================
# --- OPENID CONNECT (OIDC) GENIŞLETME AYARLARI
# ==========================================
# OIDC kapsamı (scope) - hangi bilgileri talep edelim
SOCIAL_AUTH_OIDC_SCOPE = ['openid', 'profile', 'email', 'groups']

# OIDC claim mapping - IdP'den gelen claim'leri user field'lerine eşle
SOCIAL_AUTH_OIDC_ID_TOKEN_DECRYPTION_ALGORITHM = 'RS256'

# Google OAuth2 (Opsiyonel)
SOCIAL_AUTH_GOOGLE_OAUTH2_KEY = os.environ.get('SOCIAL_AUTH_GOOGLE_OAUTH2_KEY', '')
SOCIAL_AUTH_GOOGLE_OAUTH2_SECRET = os.environ.get('SOCIAL_AUTH_GOOGLE_OAUTH2_SECRET', '')

# GitHub OAuth2 (Opsiyonel)
SOCIAL_AUTH_GITHUB_KEY = os.environ.get('SOCIAL_AUTH_GITHUB_KEY', '')
SOCIAL_AUTH_GITHUB_SECRET = os.environ.get('SOCIAL_AUTH_GITHUB_SECRET', '')

# ==========================================
# --- SSO EXTENDED SECURITY
# ==========================================
# Sosyal auth ile birden fazla bağlantıya izin ver
SOCIAL_AUTH_ALLOW_REDIRECT_AFTER_DISCONNECT = True

# SAML sertifikası doğrulaması zorunlu
SOCIAL_AUTH_SAML_STRICT_METADATA_VALIDATION = os.environ.get('SOCIAL_AUTH_SAML_STRICT_VALIDATION', 'True').lower() == 'true'

# Kullanıcı kaydında email doğrulaması gerekliliği
SOCIAL_AUTH_EMAIL_VALIDATION_FUNCTION = 'social_core.utils.silent_email_validator'
SOCIAL_AUTH_EMAIL_REQUIRED = True

# ==========================================
# --- ÜRETİM GÜVENLİK AYARLARI ---
# ==========================================
if not DEBUG:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    CSRF_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    CSRF_COOKIE_SAMESITE = 'Lax'
    SECURE_SSL_REDIRECT = os.environ.get('SECURE_SSL_REDIRECT', 'True').lower() in ('1', 'true', 'yes')
    SECURE_HSTS_SECONDS = int(os.environ.get('SECURE_HSTS_SECONDS', '31536000'))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = os.environ.get('SECURE_HSTS_PRELOAD', 'False').lower() in ('1', 'true', 'yes')
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_BROWSER_XSS_FILTER = True
    X_FRAME_OPTIONS = 'DENY'
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

SESSION_COOKIE_AGE = int(os.environ.get('SESSION_COOKIE_AGE', str(60 * 60 * 8)))
SESSION_SAVE_EVERY_REQUEST = os.environ.get('SESSION_SAVE_EVERY_REQUEST', 'False').lower() in ('1', 'true', 'yes')

LOG_LEVEL = os.environ.get('DJANGO_LOG_LEVEL', 'INFO')
LOG_DIR = BASE_DIR / 'logs'
LOG_DIR.mkdir(exist_ok=True)

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'standard': {
            'format': '[{asctime}] {levelname} {name}: {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'standard',
        },
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': LOG_DIR / 'omniops.log',
            'maxBytes': int(os.environ.get('DJANGO_LOG_MAX_BYTES', str(10 * 1024 * 1024))),
            'backupCount': int(os.environ.get('DJANGO_LOG_BACKUP_COUNT', '5')),
            'formatter': 'standard',
            'encoding': 'utf-8',
        },
    },
    'root': {
        'handlers': ['console', 'file'],
        'level': LOG_LEVEL,
    },
    'loggers': {
        'django.security': {
            'handlers': ['console', 'file'],
            'level': 'WARNING',
            'propagate': False,
        },
        'inventory': {
            'handlers': ['console', 'file'],
            'level': LOG_LEVEL,
            'propagate': False,
        },
    },
}

# SSO ile kayıtlı olsa da yerel şifre değişikliğine izin ver
SOCIAL_AUTH_DEFAULT_USERNAME_FUNCTION = 'social_core.utils.slugify'

import sys
if not DEBUG and 'test' not in sys.argv:
    insecure_markers = ('dev-only', 'change-me', 'insecure', 'please-set-env')
    if not SECRET_KEY or any(marker in SECRET_KEY.lower() for marker in insecure_markers):
        from django.core.exceptions import ImproperlyConfigured
        raise ImproperlyConfigured('Production ortamında güvenli bir DJANGO_SECRET_KEY zorunludur.')