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
            'factory_portfolio_inventory',
            'asset_qr_scanner',
            'erp_integrations',
            'ot_integrations',
            'integration_hub_center',
            'itsm_maturity',
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
        from inventory.models import FactorySite, DepartmentInventoryItem

        created_sites, created_departments, created_zones, created_inventory = ensure_default_factory_structure()
        self.assertGreaterEqual(created_sites, 1)
        self.assertGreaterEqual(created_departments, 1)
        self.assertGreaterEqual(created_zones, 1)
        self.assertGreaterEqual(created_inventory, 1)
        self.assertGreaterEqual(FactorySite.objects.filter(is_active=True).count(), 1)
        self.assertGreaterEqual(DepartmentInventoryItem.objects.filter(is_active=True).count(), 1)
        created_sites, created_departments, created_zones, created_inventory = ensure_default_factory_structure()
        self.assertEqual(created_sites, 0)
        self.assertEqual(created_departments, 0)
        self.assertEqual(created_zones, 0)
        self.assertEqual(created_inventory, 0)

    def test_factory_portfolio_inventory_view(self):
        from inventory.factory_bootstrap import ensure_default_factory_structure
        from inventory.models import FactorySite

        ensure_default_factory_structure()
        site = FactorySite.objects.filter(is_active=True).first()
        response = self.client.get(reverse('factory_portfolio_inventory'))
        self.assertEqual(response.status_code, 200)
        if site:
            response = self.client.get(reverse('factory_portfolio_inventory'), {'site': site.pk})
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, site.display_title)
            self.assertContains(response, site.code)

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
        self.assertIn('factory_sites', keys)
        self.assertIn('department_inventory', keys)

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


@override_settings(
    SECURE_SSL_REDIRECT=False,
    ALLOW_PUBLIC_REGISTRATION=False,
    SITE_ACCESS_ENFORCEMENT=True,
)
class ProductionHardeningTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            username='admin2',
            email='admin2@example.com',
            password='StrongPass123!',
        )
        self.client.force_login(self.admin)

    def test_public_registration_disabled_by_default(self):
        response = self.client.get(reverse('register'))
        self.assertEqual(response.status_code, 404)

    @override_settings(ALLOW_PUBLIC_REGISTRATION=True)
    def test_public_registration_enabled_when_configured(self):
        self.client.logout()
        response = self.client.get(reverse('register'))
        self.assertEqual(response.status_code, 200)

    def test_manual_directory_sync(self):
        from inventory.integrations.directory_sync import run_directory_sync
        from inventory.models import DirectoryConnection

        connection = DirectoryConnection.objects.create(
            name='Manual AD',
            directory_type='manual',
            sync_enabled=True,
        )
        ok, message = run_directory_sync(connection, actor=self.admin)
        self.assertTrue(ok)
        self.assertIn('snapshot', message.lower())

    def test_site_access_restricts_portfolio_view(self):
        from django.contrib.auth.models import Group
        from inventory.factory_bootstrap import ensure_default_factory_structure
        from inventory.models import FactorySite, UserFactorySiteAccess

        ensure_default_factory_structure()
        sites = list(FactorySite.objects.filter(is_active=True).order_by('id'))
        self.assertGreaterEqual(len(sites), 2)

        limited = User.objects.create_user(username='siteuser', password='StrongPass123!')
        group, _ = Group.objects.get_or_create(name='Help Desk Ekibi')
        limited.groups.add(group)
        UserFactorySiteAccess.objects.create(
            user=limited,
            factory_site=sites[0],
            access_level='viewer',
            granted_by=self.admin,
        )

        self.client.force_login(limited)
        blocked = self.client.get(reverse('factory_portfolio_inventory'), {'site': sites[1].pk})
        self.assertEqual(blocked.status_code, 302)
        allowed = self.client.get(reverse('factory_portfolio_inventory'), {'site': sites[0].pk})
        self.assertEqual(allowed.status_code, 200)

    def test_ot_connector_sync_with_mock_payload(self):
        from io import BytesIO
        from unittest.mock import patch

        from inventory.factory_bootstrap import ensure_default_factory_structure
        from inventory.integrations.ot_connector import sync_ot_connection
        from inventory.models import FactorySite, OTAssetRecord, OTConnection

        ensure_default_factory_structure()
        site = FactorySite.objects.filter(is_active=True).first()
        connection = OTConnection.objects.create(
            name='Mock MES',
            ot_type='mes_rest',
            base_url='https://mes.example.com',
            assets_path='/api/assets',
            factory_site=site,
            sync_enabled=True,
        )
        payload = BytesIO(b'[{"id":"PLC-01","name":"Hat 1 PLC","status":"online","type":"plc"}]')

        class MockResponse:
            def read(self):
                return payload.getvalue()

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

        with patch('inventory.integrations.ot_connector.urllib.request.urlopen', return_value=MockResponse()):
            count, message = sync_ot_connection(connection)

        self.assertGreaterEqual(count, 1)
        self.assertGreaterEqual(OTAssetRecord.objects.filter(connection=connection).count(), 1)
        self.assertIn('OT varlık', message)

    def test_erp_cmdb_sync_creates_external_record(self):
        from unittest.mock import patch

        from inventory.factory_bootstrap import ensure_default_factory_structure
        from inventory.integrations.erp_cmdb_sync import sync_erp_connection_to_cmdb
        from inventory.models import ERPConnection, ERPExternalRecord, FactorySite

        ensure_default_factory_structure()
        site = FactorySite.objects.filter(is_active=True).first()
        connection = ERPConnection.objects.create(
            name='Mock Odoo',
            erp_type='odoo',
            base_url='https://odoo.example.com',
            database_name='test',
            username='admin',
            api_key='secret',
            factory_site=site,
            sync_partners=True,
            sync_to_cmdb=True,
        )

        class FakeClient:
            def __init__(self, *args, **kwargs):
                self.uid = 1

            def authenticate(self):
                return 1

            def sync_partners_preview(self, limit=50):
                return [{'id': 7, 'name': 'ACME Partner', 'email': 'a@acme.com'}]

        with patch('inventory.integrations.odoo_client.OdooClient', FakeClient):
            count, message = sync_erp_connection_to_cmdb(connection, limit=10)

        self.assertGreaterEqual(count, 1)
        self.assertTrue(ERPExternalRecord.objects.filter(connection=connection, external_model='res.partner').exists())


class EnterpriseCompletenessTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            username='enterprise_admin',
            email='enterprise@example.com',
            password='StrongPass123!',
        )
        self.client.force_login(self.admin)

    def test_prometheus_metrics_endpoint(self):
        response = self.client.get(reverse('prometheus_metrics'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('omniops_tickets_open', response.content.decode())

    def test_immutable_audit_entry_is_append_only(self):
        from inventory.models import ImmutableAuditEntry

        entry = ImmutableAuditEntry.objects.create(
            actor=self.admin,
            action='create',
            resource_type='test',
            resource_id='1',
        )
        with self.assertRaises(ValueError):
            entry.action = 'update'
            entry.save()
        with self.assertRaises(ValueError):
            entry.delete()

    def test_module_permission_grant(self):
        from inventory.site_access import user_has_module_permission
        from inventory.models import ModulePermissionGrant

        limited = User.objects.create_user(username='moduser', password='StrongPass123!')
        self.assertFalse(user_has_module_permission(limited, 'integrations', 'view'))
        ModulePermissionGrant.objects.create(
            user=limited,
            module_code='integrations',
            permission_level='view',
            granted_by=self.admin,
        )
        self.assertTrue(user_has_module_permission(limited, 'integrations', 'view'))

    def test_ad_lifecycle_provision(self):
        from inventory.integrations.ad_lifecycle import run_identity_lifecycle_task
        from inventory.models import DirectoryConnection, IdentityLifecycleTask

        DirectoryConnection.objects.create(name='Manual', directory_type='manual', sync_enabled=True)
        task = IdentityLifecycleTask.objects.create(
            title='Yeni Personel',
            process_type='onboarding',
            employee_name='Ayse Yilmaz',
            department='IT',
        )
        user, message = run_identity_lifecycle_task(task, actor=self.admin)
        self.assertEqual(user.username, 'ayse.yilmaz')
        self.assertIn('oluşturuldu', message.lower())

    @override_settings(FEATURE_SALES_KANBAN=False)
    def test_sales_kanban_hidden_when_feature_disabled(self):
        response = self.client.get(reverse('sales_kanban'))
        self.assertEqual(response.status_code, 302)

    def test_sap_cmdb_sync_does_not_recurse(self):
        from inventory.factory_bootstrap import ensure_default_factory_structure
        from inventory.integrations.erp_cmdb_sync import sync_erp_connection_to_cmdb
        from inventory.models import ERPConnection, FactorySite
        from unittest.mock import patch

        ensure_default_factory_structure()
        site = FactorySite.objects.filter(is_active=True).first()
        connection = ERPConnection.objects.create(
            name='SAP Test',
            erp_type='sap',
            base_url='https://sap.example.com',
            username='user',
            api_key='secret',
            factory_site=site,
            sync_partners=True,
            sync_to_cmdb=True,
        )

        class FakeSAPClient:
            def __init__(self, *args, **kwargs):
                pass

            def test_connection(self):
                return {'server_version': 'SAP OData'}

            def preview_business_partners(self, limit=50):
                return [{'BusinessPartner': '100', 'BusinessPartnerName': 'ACME'}]

        with patch('inventory.integrations.sap_cmdb_sync.SAPODataClient', FakeSAPClient):
            count, message = sync_erp_connection_to_cmdb(connection, limit=5)

        self.assertGreaterEqual(count, 1)
        self.assertIn('SAP CMDB', message)


class WorkspaceEngineTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='wsuser', password='pass123')
        self.client.login(username='wsuser', password='pass123')

    def test_solar_preset_hides_identity_module(self):
        from inventory.models import OrganizationWorkspace
        from inventory.workspace_service import get_workspace_context

        OrganizationWorkspace.objects.create(
            name='Solar Ops',
            primary_industry='solar',
            is_active=True,
        )
        ctx = get_workspace_context(self.user)
        self.assertEqual(ctx['industry'], 'solar')
        self.assertFalse(ctx['modules']['identity'])
        self.assertTrue(ctx['modules']['network'])

    def test_workspace_layout_api_persists_order(self):
        order = ['events', 'heatmap', 'device_chart', 'ticket_chart', 'backbone']
        response = self.client.post(
            reverse('workspace_layout_api'),
            data={'page': 'dashboard', 'order': order},
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        from inventory.models import UserWorkspacePreference
        prefs = UserWorkspacePreference.objects.get(user=self.user)
        self.assertEqual(prefs.dashboard_layout, order)

    def test_workspace_center_requires_staff(self):
        response = self.client.get(reverse('workspace_center'))
        self.assertEqual(response.status_code, 302)

    def test_solar_site_in_bootstrap(self):
        from inventory.factory_bootstrap import ensure_default_factory_structure
        from inventory.models import FactorySite

        ensure_default_factory_structure()
        self.assertTrue(FactorySite.objects.filter(code='SITE-SOLAR-01', industry_type='solar').exists())


class I18nTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            username='i18nstaff', password='pass123', is_staff=True
        )
        self.customer = User.objects.create_user(
            username='i18ncust', password='pass123', is_staff=False
        )

    def test_set_language_switches_sidebar_to_english(self):
        self.client.login(username='i18nstaff', password='pass123')
        response = self.client.post(
            '/i18n/setlang/',
            {'language': 'en', 'next': '/'},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Main Dashboard')
        self.assertNotContains(response, 'Ana Panel')

    def test_login_page_has_language_switcher(self):
        response = self.client.get('/login/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '/i18n/setlang/')
        self.assertContains(response, 'Giriş Yap')

    def test_custom_admin_redirects_non_staff(self):
        self.client.login(username='i18ncust', password='pass123')
        response = self.client.get(reverse('custom_admin'))
        self.assertRedirects(response, reverse('user_panel'))

    def test_user_panel_redirects_staff(self):
        self.client.login(username='i18nstaff', password='pass123')
        response = self.client.get(reverse('user_panel'))
        self.assertRedirects(response, reverse('dashboard'))

    def test_logout_returns_to_login_and_clears_session(self):
        self.client.login(username='i18nstaff', password='pass123')
        response = self.client.post(reverse('logout'), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn('/login/', response.request['PATH_INFO'])
        self.assertFalse(response.context['user'].is_authenticated)

    def test_logout_button_renders_in_english(self):
        self.client.login(username='i18nstaff', password='pass123')
        self.client.post('/i18n/setlang/', {'language': 'en', 'next': '/'})
        response = self.client.get('/')
        self.assertContains(response, 'Log Out')
        self.assertNotContains(response, '<g id=')
