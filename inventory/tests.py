import re
import io
from pathlib import Path

from django.contrib.auth.models import User
from django.core.management import call_command
from django.contrib.staticfiles.finders import find
from django.test import TestCase, override_settings
from django.urls import NoReverseMatch, reverse
from django.conf import settings

from .models import SalesOpportunity


@override_settings(SECURE_SSL_REDIRECT=False)
class InventorySmokeTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='StrongPass123!',
        )
        self.client.force_login(self.admin)

    def test_public_runtime_endpoints(self):
        """Canlı ortam sağlık kontrolü ve PWA service worker uç noktaları çalışmalı."""
        self.assertEqual(self.client.get(reverse('health_check')).status_code, 200)
        response = self.client.get(reverse('service_worker_js'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('application/javascript', response['Content-Type'])

    def test_core_pages_render_for_admin(self):
        """Ana menüdeki sayfalar boş veritabanında bile 200 dönmeli."""
        route_names = [
            'dashboard',
            'it_inventory',
            'generator',
            'subnet_calc',
            'network_scanner',
            'visual_ipam',
            'live_monitor',
            'system_logs',
            'knowledge_base',
            'custom_admin',
            'rack_elevation',
            'network_topology',
            'device_backup',
            'bulk_config_generator',
            'reporting_hub',
            'executive_summary',
            'helpdesk_analytics',
            'user_management',
            'user_profile',
            'field_routes',
            'sales_kanban',
            'factory_operations',
            'it_operations',
            'service_operations',
            'command_center',
            'governance_center',
            'identity_operations',
            'factory_command_center',
            'asset_qr_scanner',
            'erp_integrations',
            'setup_center',
            'offline_field_app',
            'dlp_events',
            'port_mapping_list',
        ]
        for route_name in route_names:
            with self.subTest(route=route_name):
                response = self.client.get(reverse(route_name))
                self.assertEqual(response.status_code, 200)

    def test_ajax_endpoints_render_for_admin(self):
        response = self.client.get(reverse('dashboard_refresh'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json().get('status'), 'ok')

        response = self.client.get(reverse('rack_devices_api'))
        self.assertEqual(response.status_code, 200)

        response = self.client.get(reverse('notifications_api'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('notifications', response.json())

        response = self.client.get(reverse('global_search_api'), {'q': 'dashboard'})
        self.assertEqual(response.status_code, 200)
        self.assertIn('results', response.json())

        response = self.client.get(reverse('readiness_api'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('checks', response.json())

        response = self.client.get(reverse('executive_summary_export', args=['word']))
        self.assertEqual(response.status_code, 200)
        self.assertIn('application/msword', response['Content-Type'])

        response = self.client.get(reverse('executive_summary_export', args=['pdf']))
        self.assertEqual(response.status_code, 200)
        self.assertIn('application/pdf', response['Content-Type'])

    def test_omniops_doctor_command_runs(self):
        output = io.StringIO()
        call_command('omniops_doctor', '--json', stdout=output)
        self.assertIn('score', output.getvalue())

    def test_factory_bootstrap_creates_departments(self):
        from inventory.factory_bootstrap import ensure_default_factory_structure
        created_departments, created_zones = ensure_default_factory_structure()
        self.assertGreaterEqual(created_departments, 1)
        self.assertGreaterEqual(created_zones, 1)
        created_departments, created_zones = ensure_default_factory_structure()
        self.assertEqual(created_departments, 0)
        self.assertEqual(created_zones, 0)

    def test_qr_bootstrap_creates_tags(self):
        from inventory.factory_bootstrap import ensure_default_factory_structure, ensure_default_qr_tags
        from inventory.models import AssetQRTag

        ensure_default_factory_structure()
        created_tags = ensure_default_qr_tags()
        self.assertGreaterEqual(created_tags, 1)
        self.assertGreaterEqual(AssetQRTag.objects.filter(is_active=True).count(), 1)
        self.assertEqual(ensure_default_qr_tags(), 0)

    def test_camera_health_evaluate_without_network(self):
        from inventory.integrations.camera_health import evaluate_camera_health
        from inventory.models import CameraDevice

        camera = CameraDevice(name='Test Kamera', status='online')
        status, message = evaluate_camera_health(camera)
        self.assertEqual(status, 'warning')
        self.assertIn('tanımlı değil', message)

    def test_readiness_report_includes_new_checks(self):
        response = self.client.get(reverse('readiness_api'))
        self.assertEqual(response.status_code, 200)
        keys = {item['key'] for item in response.json().get('checks', [])}
        self.assertIn('qr_tags', keys)
        self.assertIn('onlyoffice', keys)
        self.assertIn('collabora', keys)

    def test_qr_label_pdf_download(self):
        from inventory.models import AssetQRTag
        tag = AssetQRTag.objects.create(code='PDF-TEST-001', tag_type='it_asset', label='PDF Test')
        response = self.client.get(reverse('asset_qr_label_pdf', args=[tag.id]))
        self.assertEqual(response.status_code, 200)
        self.assertIn('application/pdf', response['Content-Type'])

    def test_erp_connector_routes_all_supported_types(self):
        from inventory.integrations.erp_connector import ERPClientError, test_erp_connection
        from inventory.models import ERPConnection

        for erp_type, _label in ERPConnection.ERP_TYPE_CHOICES:
            connection = ERPConnection(
                name='Test ERP',
                erp_type=erp_type,
                base_url='https://127.0.0.1:1',
                database_name='test',
                username='user',
                api_key='secret',
            )
            try:
                test_erp_connection(connection)
            except ERPClientError as exc:
                self.assertNotIn('henüz desteklenmiyor', str(exc).lower())
            except (OSError, ConnectionError):
                # Ağ hatası, yönlendirme çalıştı demektir
                pass

    def test_batch_qr_labels_pdf(self):
        from inventory.models import AssetQRTag

        AssetQRTag.objects.create(code='BATCH-001', tag_type='it_asset', label='Batch 1')
        AssetQRTag.objects.create(code='BATCH-002', tag_type='device', label='Batch 2')
        response = self.client.get(reverse('asset_qr_labels_batch_pdf'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('application/pdf', response['Content-Type'])

    def test_wopi_check_file_info_requires_token(self):
        from inventory.models import ManagedDocument
        from django.core.files.base import ContentFile

        document = ManagedDocument.objects.create(
            title='WOPI Test',
            file_type='docx',
            status='draft',
        )
        document.file.save('test.docx', ContentFile(b'docx-content'), save=True)
        response = self.client.get(reverse('wopi_check_file_info', args=[document.id]))
        self.assertEqual(response.status_code, 401)

    def test_document_editor_backend_auto_without_config(self):
        from inventory.integrations.document_editor import get_document_editor_backend
        self.assertIsNone(get_document_editor_backend())

    def test_core_api_lists_render_for_admin(self):
        route_names = [
            'device-list',
            'ipaddress-list',
            'network-scan-list',
            'ticket-list',
            'ticket-category-list',
            'notification-list',
            'change-request-list',
            'performance-log-list',
            'user-list',
            'probe-list',
            'field-visit-list',
            'sales-opportunity-list',
            'dlp-event-list',
            'factory-area-list',
            'consumable-list',
            'maintenance-task-list',
            'employee-it-process-list',
            'procurement-request-list',
            'oncall-shift-list',
            'backup-job-list',
            'vendor-support-case-list',
            'asset-handover-list',
            'major-incident-list',
            'access-request-list',
            'printer-fleet-list',
            'runbook-list',
            'remote-access-grant-list',
            'department-channel-list',
            'department-message-list',
            'camera-device-list',
            'business-application-list',
            'report-template-list',
            'change-calendar-event-list',
            'service-dependency-list',
            'integration-health-check-list',
            'compliance-control-list',
            'document-output-job-list',
            'directory-connection-list',
            'directory-group-list',
            'directory-user-list',
            'endpoint-device-list',
            'identity-lifecycle-task-list',
            'factory-department-list',
            'factory-zone-list',
            'managed-document-list',
            'factory-asset-relation-list',
            'asset-qr-tag-list',
            'erp-connection-list',
        ]
        for route_name in route_names:
            with self.subTest(route=route_name):
                response = self.client.get(reverse(route_name))
                self.assertEqual(response.status_code, 200)

    def test_qr_lookup_api(self):
        """QR kod arama API'si kayıtlı etiketi bulmalı."""
        from inventory.models import AssetQRTag
        AssetQRTag.objects.create(code='TEST-QR-001', tag_type='it_asset', label='Test Etiket')
        response = self.client.get(reverse('qr_lookup_api'), {'code': 'TEST-QR-001'})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json().get('found'))

    def test_sales_move_rejects_invalid_position(self):
        opportunity = SalesOpportunity.objects.create(
            title='Test Fırsatı',
            customer_name='Test Müşteri',
            owner=self.admin,
        )
        response = self.client.patch(
            reverse('sales-opportunity-move', args=[opportunity.id]),
            data={'stage': 'proposal', 'position': 'not-a-number'},
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)

    def test_login_page_does_not_show_unconfigured_sso(self):
        self.client.logout()
        response = self.client.get(reverse('login'))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')
        if not settings.SOCIAL_AUTH_AZUREAD_OAUTH2_KEY:
            self.assertNotIn('Microsoft ile Giriş Yap', content)
        if not settings.SOCIAL_AUTH_OIDC_KEY:
            self.assertNotIn('Kurumsal SSO ile Giriş Yap', content)

    def test_template_url_and_static_references_are_valid(self):
        root = Path(settings.BASE_DIR)
        url_re = re.compile(r"\{%\s*url\s+['\"]([^'\"]+)['\"](?:\s+([^%]+?))?\s*%\}")
        static_re = re.compile(r"\{%\s*static\s+['\"]([^'\"]+)['\"]\s*%\}")
        dummy_args = {
            'ticket.id': 1,
            'b.device.id': 1,
            'd.id': 1,
            'asset.id': 1,
            'lic.id': 1,
            'contract.id': 1,
            'device.id': 1,
            'pk': 1,
        }

        for path in root.glob('inventory/templates/**/*.html'):
            text = path.read_text(encoding='utf-8', errors='ignore')
            for match in url_re.finditer(text):
                name = match.group(1)
                args_text = (match.group(2) or '').strip()
                args = []
                if name == 'social:begin':
                    args = ['azuread-oauth2']
                elif args_text:
                    for token in re.split(r'\s+', args_text):
                        token = token.strip()
                        if not token or token.startswith('as ') or '=' in token:
                            continue
                        if token.startswith(('"', "'")):
                            args.append(token.strip('"\''))
                        elif token in dummy_args:
                            args.append(dummy_args[token])
                        elif token.endswith('.id') or token == 'id':
                            args.append(1)
                try:
                    reverse(name, args=args)
                except NoReverseMatch as exc:
                    self.fail(f'{path.relative_to(root)} içindeki url çözümlenemedi: {name} {args} ({exc})')

            for match in static_re.finditer(text):
                asset = match.group(1)
                self.assertIsNotNone(find(asset), f'{path.relative_to(root)} statik dosyası bulunamadı: {asset}')