# OmniOps Factory IT Suite

OmniOps Factory IT Suite, fabrika ve kurumsal bilgi işlem ekiplerinin günlük operasyonlarını tek panelden yönetebilmesi için geliştirilmiş kapsamlı bir ITSM, ITOM, ağ yönetimi, envanter, saha operasyonu, güvenlik ve raporlama platformudur.

Sistem; servis masası, ağ keşfi, cihaz yedekleme, IPAM, kamera/NVR takibi, VPN/uzaktan erişim kayıtları, fabrika alanları, sarf malzeme, personel IT süreçleri, satın alma, major incident, uyum kontrolleri, runbook, iş uygulamaları, yönetici özetleri ve PDF/Word rapor çıktıları gibi modülleri aynı modern arayüzde birleştirir.

![Python](https://img.shields.io/badge/Python-3.11-blue?style=for-the-badge&logo=python)
![Django](https://img.shields.io/badge/Django-5.x-092E20?style=for-the-badge&logo=django)
![DRF](https://img.shields.io/badge/API-Django_REST_Framework-red?style=for-the-badge)
![PostgreSQL](https://img.shields.io/badge/Database-PostgreSQL-4169E1?style=for-the-badge&logo=postgresql)
![Redis](https://img.shields.io/badge/Queue-Redis-DC382D?style=for-the-badge&logo=redis)
![Docker](https://img.shields.io/badge/Deploy-Docker-2496ED?style=for-the-badge&logo=docker)

## Öne Çıkan Modüller

- Servis masası: ticket, yorum, ek dosya, kategori, SLA, bildirim, analitik ve CSV dışa aktarım.
- Kullanıcı ve yetki: rol bazlı erişim, destek ekipleri, profil yönetimi, API token/JWT ve nesne bazlı izin altyapısı.
- Ağ ve altyapı: derin ağ tarama, topoloji, IPAM, rack görünümü, port haritaları, cihaz konfigürasyon üretimi, yedekleme ve diff.
- IT envanter: varlık, lisans, tedarikçi sözleşmesi, bakım ve zimmet süreçleri.
- Fabrika operasyonları: fabrika alanları, sarf/stok takibi, periyodik bakım, onboarding/offboarding/transfer.
- **Fabrika BT Komuta Merkezi**: departman kartelası, alt alan/sistem odası yapısı, bölüm seçince açılan modül kartları (kamera, switch, endpoint, ticket, doküman), PDF önizleme ve güvenli indirme.
- IT operasyon merkezi: satın alma, nöbet vardiyası, backup job izleme, vendor support case ve asset handover.
- Servis süreç merkezi: major incident, access request, printer fleet ve runbook/SOP yönetimi.
- Komuta merkezi: VPN/uzaktan erişim, departman kanalları, kamera/NVR cihazları, iş uygulamaları ve rapor şablonları.
- Yönetişim merkezi: change calendar, CMDB servis bağımlılıkları, entegrasyon sağlığı, compliance ve çıktı işleri.
- Offline saha: PWA, service worker, offline queue ve tekrar bağlantıda senkronizasyon.
- Global komut paleti: `Ctrl+K` ile cihaz, ticket, kamera, runbook, rapor ve hızlı aksiyon arama.
- Kurulum & Sağlık Merkezi: readiness skoru, ortam kontrolleri, modül doluluk durumu ve ilk kurulum adımları.
- Yönetici Bilgilendirme: tek sayfa operasyon özeti, risk/KPI kartları, PDF ve Word çıktıları.

## Teknoloji Yığını

- Backend: Python, Django, Django REST Framework, SimpleJWT, django-guardian
- Frontend: Django templates, Bootstrap 5, modern CSS design system, Chart.js, Leaflet, vis-network
- Asenkron işler: Celery, Redis
- Veritabanı: SQLite geliştirme, PostgreSQL production
- Raporlama: ReportLab PDF, Word uyumlu HTML `.doc` çıktısı
- Deployment: Docker, Docker Compose, Gunicorn, Nginx reverse proxy
- PWA: manifest, service worker, offline sync JavaScript

## Hızlı Docker Kurulumu

```bash
git clone https://github.com/slhkrt-tech/OmniOps-Factory-It-Suite.git
cd OmniOps-Factory-It-Suite
copy .env.example .env
```

`.env` içindeki değerleri canlı ortama göre değiştirin:

```env
APP_NAME=OmniOps
DJANGO_SECRET_KEY=replace-with-a-strong-secret
ALLOWED_HOSTS=localhost,127.0.0.1,omniops.example.com
CSRF_TRUSTED_ORIGINS=https://omniops.example.com
POSTGRES_DB=omniops
POSTGRES_USER=omniops
POSTGRES_PASSWORD=change-this-password
REMOTE_PROBE_SHARED_SECRET=change-this-probe-secret
```

Servisleri başlatın:

```bash
docker compose up --build -d
```

İlk admin kullanıcısını oluşturun:

```bash
docker compose exec web python manage.py createsuperuser
```

Sağlık kontrolü:

```bash
curl http://127.0.0.1:8000/health/
curl http://127.0.0.1:8080/health/   # nginx üzerinden
curl http://127.0.0.1:8000/metrics/  # Prometheus scrape
```

Arayüz:

```text
http://127.0.0.1:8000
http://127.0.0.1:8080   # nginx reverse proxy (docker compose)
```

## Geliştirici Kurulumu

```bash
git clone https://github.com/slhkrt-tech/OmniOps-Factory-It-Suite.git
cd OmniOps-Factory-It-Suite
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python manage.py migrate
python manage.py setup_helpdesk
python manage.py createsuperuser
python manage.py runserver
```

Celery worker:

```bash
celery -A core worker --loglevel=info --pool=solo
```

Celery beat:

```bash
celery -A core beat --loglevel=info
```

## İlk Kurulum ve Readiness

OmniOps, yeni kurulumun hazır olup olmadığını kontrol eden iki araç içerir.

Web arayüzü:

```text
/kurulum-merkezi/
```

CLI doctor komutu:

```bash
python manage.py omniops_doctor
python manage.py omniops_doctor --json
python manage.py omniops_doctor --bootstrap
```

`--bootstrap` varsayılan roller, destek ekipleri, kategoriler, temel izinler ve fabrika departman kartelasını hazırlar.

## Fabrika BT Komuta Merkezi

Departman kartelası, alt alanlar ve doküman merkezi:

```text
/fabrika-komuta-merkezi/
```

Özellikler:

- Departman kartelası (üretim, kalite, BT, depo, güvenlik vb.)
- Alt alan / sistem odası / kamera bölgesi tanımları
- Bölüm seçilince kameralar, ağ cihazları, endpointler, ticketlar ve doküman modülleri
- PDF tarayıcı önizlemesi: `/dokuman/<id>/onizleme/`
- Güvenli indirme: `/dokuman/<id>/indir/`
- Tarayıcı editörü (DOCX/XLSX/PPTX): `/dokuman/<id>/duzenle/`

İlk kartela verisi:

```bash
python manage.py omniops_doctor --bootstrap
```

Sidebar navigasyonu açılır gruplar halindedir: Komuta, Fabrika Envanteri, Ağ ve Sistem, Kimlik ve Kullanıcı, Servis Masası, Güvenlik ve Yönetişim, Rapor ve Doküman, Yönetim.

### Gelişmiş Entegrasyonlar (Paket 2)

- **OnlyOffice / Collabora**: DOCX/XLSX tarayıcı editörü (`/dokuman/<id>/duzenle/`)
- **QR/Barkod tarayıcı**: Kamera veya manuel kod ile varlık çözümleme (`/varlik-qr-tara/`)
- **QR etiket PDF yazdırma**: `/qr-etiket/<id>/pdf/` ve `/qr-etiket/toplu-pdf/`
- **Kamera/NVR health polling**: Celery ile 10 dakikada bir otomatik durum kontrolü
- **Odoo / ERPNext / SAP / Genel REST connector**: XML-RPC, REST ve OData test/sync (`/erp-entegrasyonlari/`)

Docker ile OnlyOffice ve Collabora:

```bash
docker compose up -d onlyoffice collabora
```

OnlyOffice örneği:

```env
ONLYOFFICE_DOCUMENT_SERVER_URL=http://localhost:8082
ONLYOFFICE_JWT_SECRET=omniops-jwt-secret
DOCUMENT_EDITOR_BACKEND=onlyoffice
```

Collabora örneği:

```env
COLLABORA_SERVER_URL=http://localhost:9980
DOCUMENT_EDITOR_BACKEND=collabora
WOPI_SECRET=your-wopi-secret
```

ERPNext alan eşlemesi: `username` = API Key, `api_key` = API Secret. SAP OData için `database_name` alanına servis yolu yazılabilir. `other` tipi genel REST sağlık kontrolü yapar.

### Kurumsal Tamamlama (Paket 3)

- **Fabrika portföy envanteri**: tesis bazlı bölüm envanteri (`/fabrika-portfoy-envanter/`)
- **Tesis RBAC**: kullanıcı–tesis erişim yetkisi ve modül bazlı ince yetki
- **Entegrasyon merkezi**: Zabbix/Prometheus, VMS, Teams/Slack/e-posta webhook, IMAP ticket, backup vendor, WMS (`/entegrasyon-merkezi/`)
- **ITSM olgunluk**: problem, release/CAB, varlık lifecycle, append-only denetim izi (`/itsm-olgunluk/`)
- **OT/MES köprüsü**: üretim varlık senkronizasyonu (`/ot-entegrasyonlari/`)
- **Kimlik operasyonları**: AD/LDAP/Azure sync, lifecycle otomasyonu (`/kimlik-operasyonlari/`)
- **Prometheus metrikleri**: `/metrics/`
- **Nginx reverse proxy**: Docker ile `http://127.0.0.1:8080` (web servisi arkasında)

Production güvenlik varsayılanları:

```env
ALLOW_PUBLIC_REGISTRATION=False
SITE_ACCESS_ENFORCEMENT=True
DIRECTORY_SYNC_DRY_RUN=False
FEATURE_SALES_KANBAN=True
PROMETHEUS_METRICS_ENABLED=True
PROMETHEUS_METRICS_TOKEN=replace-with-random-metrics-token
```

Prometheus scrape için isteğe bağlı bearer token kullanın: `Authorization: Bearer <token>`.

Docker nginx (`8080`) statik dosyalar için `staticfiles_data` volume paylaşır; `collectstatic` web konteynerinde çalışır.

Yardımcı komutlar:

```bash
python manage.py import_inventory_csv veriler.csv --site-code SITE-TEXTILE
python manage.py gdpr_export_user --username admin
python manage.py test_postgres_restore
```

## Yönetici Raporları

Yönetici bilgilendirme ekranı:

```text
/yonetici-bilgilendirme/
```

PDF çıktı:

```text
/yonetici-bilgilendirme/pdf/
```

Word çıktı:

```text
/yonetici-bilgilendirme/word/
```

Klasik raporlama merkezi:

```text
/raporlar/
```

Bu alanlardan ticket performansı, denetim izi, yönetici özeti, operasyon KPI'ları ve toplantı dokümanları dışa aktarılabilir.

## API ve Dokümantasyon

REST API ana yolu:

```text
/api/
```

OpenAPI schema:

```text
/api/schema/
```

Swagger UI:

```text
/api/docs/
```

JWT token:

```text
/api/token/
/api/token/refresh/
```

## Production Kontrol Listesi

- `.env` içindeki `DJANGO_SECRET_KEY`, `POSTGRES_PASSWORD`, `REMOTE_PROBE_SHARED_SECRET`, `VAULT_KEY` değerlerini değiştirin.
- `ALLOWED_HOSTS` ve `CSRF_TRUSTED_ORIGINS` alanlarına canlı domainleri ekleyin.
- SMTP ayarlarını girin: `EMAIL_HOST`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `DEFAULT_FROM_EMAIL`.
- SSO kullanılıyorsa Azure AD, OIDC veya SAML değerlerini doldurun.
- Nginx/TLS yapılandırmasını canlı domaininize göre güncelleyin.
- Kalıcı volume'leri yedekleyin: `postgres_data`, `media_data`, `logs_data`, `db_backups`.
- Derin ağ taraması için Docker Compose içinde `NET_RAW` ve `NET_ADMIN` capability kullanıldığını gözden geçirin.
- Kurulum sonrası `/kurulum-merkezi/` ekranından readiness skorunu kontrol edin.

## Doğrulama Komutları

```bash
python manage.py check
python manage.py test inventory
python manage.py spectacular --file schema.yml --validate
python manage.py makemigrations --check
```

Docker içinde:

```bash
docker compose exec web python manage.py check
docker compose exec web python manage.py test inventory
```

## Docker Servisleri

Compose proje adı ve container adları OmniOps olarak sabitlenmiştir.

- `omniops_app`: Django/Gunicorn web uygulaması
- `omniops_worker`: Celery worker
- `omniops_beat`: Celery beat scheduler
- `omniops_db`: PostgreSQL
- `omniops_redis`: Redis
- `omniops_onlyoffice`: OnlyOffice Document Server (opsiyonel, port 8082)
- `omniops_collabora`: Collabora Online CODE (opsiyonel, port 9980)

Uygulama image adı:

```text
omniops/app:latest
```

## Güvenlik Notları

- `.env` dosyasını repoya eklemeyin.
- Production ortamında `DJANGO_DEBUG=False` kullanın.
- Reverse proxy arkasında HTTPS, secure cookie ve CSRF trusted origin ayarlarını kontrol edin.
- Uzak probe entegrasyonu için `REMOTE_PROBE_SHARED_SECRET` değerini güçlü ve benzersiz belirleyin.
- Vault/cihaz parolaları için `VAULT_KEY` değerini kurulum başına ayrı üretin.

## Lisans ve Kullanım

Bu proje fabrika IT ekipleri, sistem yöneticileri, ağ ekipleri ve destek masası operasyonları için uçtan uca yönetim paneli olarak tasarlanmıştır. Canlı kullanım öncesinde kurum politikalarına göre güvenlik, yetki, yedekleme ve log saklama ayarları gözden geçirilmelidir.
