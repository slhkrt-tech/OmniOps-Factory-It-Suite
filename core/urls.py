from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from django.conf import settings
from django.conf.urls.static import static
from inventory.views import (
    config_generator, dashboard, dashboard_refresh, subnet_calculator, export_pdf,
    export_csv, network_scanner, custom_admin, user_panel,
    register_page, visual_ipam, live_monitor, get_monitor_data,
    network_topology, device_backup_view,
    bulk_config_generator,
    it_inventory_view,
    system_logs_view,
    port_mapping_view,
    port_mapping_list_view,
    sync_ad_users,
    knowledge_base_view,
    search_kb_api,
    device_alert_webhook,
    config_diff_view,
    rack_elevation_view,
    reporting_hub_view,
    global_search_api,
    executive_summary_view,
    executive_summary_export,
)
from inventory.helpdesk_views import (
    ticket_detail, helpdesk_analytics, export_tickets_csv,
    user_profile_view, notifications_api, mark_notification_read,
    mark_all_notifications_read, user_management_view,
)
from inventory.enterprise_views import (
    field_routes_view, sales_kanban_view, offline_field_app,
    dlp_events_view, optimize_field_route, topology_png_export,
    service_worker_js, health_check, factory_operations_view, it_operations_view,
    service_operations_view, command_center_view, governance_center_view,
    setup_center_view, readiness_api, identity_operations_view,
    factory_command_center_view, factory_portfolio_inventory_view, managed_document_download, managed_document_preview,
    managed_document_editor, managed_document_editor_callback,
    asset_qr_scanner_view, qr_lookup_api, erp_integrations_view, ot_integrations_view,
    integration_hub_center_view, itsm_maturity_view, prometheus_metrics_view,
    asset_qr_label_pdf, asset_qr_labels_batch_pdf,
    wopi_check_file_info, wopi_file_contents,
)

from inventory import api_views
from inventory.api_views import get_rack_devices
from rest_framework.routers import DefaultRouter

from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)

from drf_spectacular.views import (
    SpectacularAPIView, 
    SpectacularRedocView, 
    SpectacularSwaggerView
)

router = DefaultRouter()
router.register(r'devices', api_views.DeviceViewSet, basename='device')
router.register(r'ip-addresses', api_views.IpAddressViewSet, basename='ipaddress')
router.register(r'network-scans', api_views.NetworkScanViewSet, basename='network-scan')
router.register(r'tickets', api_views.TicketViewSet, basename='ticket')
router.register(r'ticket-comments', api_views.TicketCommentViewSet, basename='ticket-comment')
router.register(r'ticket-attachments', api_views.TicketAttachmentViewSet, basename='ticket-attachment')
router.register(r'ticket-categories', api_views.TicketCategoryViewSet, basename='ticket-category')
router.register(r'notifications', api_views.NotificationViewSet, basename='notification')
router.register(r'change-requests', api_views.ChangeRequestViewSet, basename='change-request')
router.register(r'performance-logs', api_views.DevicePerformanceLogViewSet, basename='performance-log')
router.register(r'users', api_views.UserViewSet, basename='user')
router.register(r'probes', api_views.RemoteProbeViewSet, basename='probe')
router.register(r'field-visits', api_views.FieldVisitViewSet, basename='field-visit')
router.register(r'sales-opportunities', api_views.SalesOpportunityViewSet, basename='sales-opportunity')
router.register(r'dlp-events', api_views.DLPEventViewSet, basename='dlp-event')
router.register(r'factory-areas', api_views.FactoryAreaViewSet, basename='factory-area')
router.register(r'consumables', api_views.ConsumableItemViewSet, basename='consumable')
router.register(r'maintenance-tasks', api_views.MaintenanceTaskViewSet, basename='maintenance-task')
router.register(r'employee-it-processes', api_views.EmployeeITProcessViewSet, basename='employee-it-process')
router.register(r'procurement-requests', api_views.ProcurementRequestViewSet, basename='procurement-request')
router.register(r'oncall-shifts', api_views.OnCallShiftViewSet, basename='oncall-shift')
router.register(r'backup-jobs', api_views.BackupJobMonitorViewSet, basename='backup-job')
router.register(r'vendor-support-cases', api_views.VendorSupportCaseViewSet, basename='vendor-support-case')
router.register(r'asset-handovers', api_views.AssetHandoverViewSet, basename='asset-handover')
router.register(r'major-incidents', api_views.MajorIncidentViewSet, basename='major-incident')
router.register(r'access-requests', api_views.AccessRequestViewSet, basename='access-request')
router.register(r'printer-fleet', api_views.PrinterFleetItemViewSet, basename='printer-fleet')
router.register(r'runbooks', api_views.RunbookViewSet, basename='runbook')
router.register(r'remote-access-grants', api_views.RemoteAccessGrantViewSet, basename='remote-access-grant')
router.register(r'department-channels', api_views.DepartmentChannelViewSet, basename='department-channel')
router.register(r'department-messages', api_views.DepartmentMessageViewSet, basename='department-message')
router.register(r'camera-devices', api_views.CameraDeviceViewSet, basename='camera-device')
router.register(r'business-applications', api_views.BusinessApplicationViewSet, basename='business-application')
router.register(r'report-templates', api_views.ReportTemplateViewSet, basename='report-template')
router.register(r'change-calendar-events', api_views.ChangeCalendarEventViewSet, basename='change-calendar-event')
router.register(r'service-dependencies', api_views.ServiceDependencyViewSet, basename='service-dependency')
router.register(r'integration-health-checks', api_views.IntegrationHealthCheckViewSet, basename='integration-health-check')
router.register(r'compliance-controls', api_views.ComplianceControlViewSet, basename='compliance-control')
router.register(r'document-output-jobs', api_views.DocumentOutputJobViewSet, basename='document-output-job')
router.register(r'directory-connections', api_views.DirectoryConnectionViewSet, basename='directory-connection')
router.register(r'directory-groups', api_views.DirectoryGroupViewSet, basename='directory-group')
router.register(r'directory-users', api_views.DirectoryUserViewSet, basename='directory-user')
router.register(r'endpoint-devices', api_views.EndpointDeviceViewSet, basename='endpoint-device')
router.register(r'identity-lifecycle-tasks', api_views.IdentityLifecycleTaskViewSet, basename='identity-lifecycle-task')
router.register(r'factory-sites', api_views.FactorySiteViewSet, basename='factory-site')
router.register(r'factory-departments', api_views.FactoryDepartmentViewSet, basename='factory-department')
router.register(r'department-inventory', api_views.DepartmentInventoryItemViewSet, basename='department-inventory')
router.register(r'factory-zones', api_views.FactoryZoneViewSet, basename='factory-zone')
router.register(r'managed-documents', api_views.ManagedDocumentViewSet, basename='managed-document')
router.register(r'factory-asset-relations', api_views.FactoryITAssetRelationViewSet, basename='factory-asset-relation')
router.register(r'asset-qr-tags', api_views.AssetQRTagViewSet, basename='asset-qr-tag')
router.register(r'erp-connections', api_views.ERPConnectionViewSet, basename='erp-connection')
router.register(r'problems', api_views.ProblemRecordViewSet, basename='problem-record')
router.register(r'releases', api_views.ReleaseRecordViewSet, basename='release-record')
router.register(r'monitoring-connections', api_views.MonitoringConnectionViewSet, basename='monitoring-connection')
router.register(r'notification-channels', api_views.NotificationChannelViewSet, basename='notification-channel')
router.register(r'module-permissions', api_views.ModulePermissionGrantViewSet, basename='module-permission')

urlpatterns = [
    path('health/', health_check, name='health_check'),
    path('metrics/', prometheus_metrics_view, name='prometheus_metrics'),

    path('i18n/', include('django.conf.urls.i18n')),

    path('admin/', admin.site.urls),

    # Auth
    path('login/', auth_views.LoginView.as_view(
        template_name='login.html',
        extra_context={
            'azure_sso_enabled': bool(settings.SOCIAL_AUTH_AZUREAD_OAUTH2_KEY),
            'oidc_sso_enabled': bool(settings.SOCIAL_AUTH_OIDC_KEY),
        },
    ), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),
    path('kayit-ol/', register_page, name='register'),
    
    # Application routes
    path('uretici/', config_generator, name='generator'),
    path('subnet-hesapla/', subnet_calculator, name='subnet_calc'),
    path('indir-pdf/', export_pdf, name='export_pdf'),
    path('indir-csv/', export_csv, name='export_csv'),
    path('ag-tarayici/', network_scanner, name='network_scanner'),
    path('ipam/', visual_ipam, name='visual_ipam'),
    path('monitor/', live_monitor, name='live_monitor'),
    path('api/monitor-data/', get_monitor_data, name='get_monitor_data'),
    path('api/dashboard-refresh/', dashboard_refresh, name='dashboard_refresh'),
    path('api/global-search/', global_search_api, name='global_search_api'),
    path('api/readiness/', readiness_api, name='readiness_api'),
    path('topoloji/', network_topology, name='network_topology'),
    path('topoloji/png/', topology_png_export, name='topology_png_export'),
    
    path('yedekleme/', device_backup_view, name='device_backup'), 
    path('toplu-generator/', bulk_config_generator, name='bulk_config_generator'),
    path('konfigurasyon-karsilastir/<int:device_id>/', config_diff_view, name='config_diff'),
    
    path('veri-merkezi/', rack_elevation_view, name='rack_elevation'),

    path('raporlar/', reporting_hub_view, name='reporting_hub'),
    path('yonetici-bilgilendirme/', executive_summary_view, name='executive_summary'),
    path('yonetici-bilgilendirme/<str:export_format>/', executive_summary_export, name='executive_summary_export'),
    
    path('panel/', custom_admin, name='custom_admin'),
    path('destek-analitik/', helpdesk_analytics, name='helpdesk_analytics'),
    path('kullanici-yonetimi/', user_management_view, name='user_management'),
    path('profil/', user_profile_view, name='user_profile'),
    path('saha-rotalari/', field_routes_view, name='field_routes'),
    path('saha-rotalari/optimize/', optimize_field_route, name='optimize_field_route'),
    path('satis-kanban/', sales_kanban_view, name='sales_kanban'),
    path('fabrika-operasyonlari/', factory_operations_view, name='factory_operations'),
    path('it-operasyonlari/', it_operations_view, name='it_operations'),
    path('servis-surecleri/', service_operations_view, name='service_operations'),
    path('komuta-merkezi/', command_center_view, name='command_center'),
    path('yonetisim-merkezi/', governance_center_view, name='governance_center'),
    path('kimlik-operasyonlari/', identity_operations_view, name='identity_operations'),
    path('fabrika-komuta-merkezi/', factory_command_center_view, name='factory_command_center'),
    path('fabrika-portfoy-envanter/', factory_portfolio_inventory_view, name='factory_portfolio_inventory'),
    path('dokuman/<int:pk>/indir/', managed_document_download, name='managed_document_download'),
    path('dokuman/<int:pk>/onizleme/', managed_document_preview, name='managed_document_preview'),
    path('dokuman/<int:pk>/duzenle/', managed_document_editor, name='managed_document_editor'),
    path('dokuman/<int:pk>/editor-callback/', managed_document_editor_callback, name='managed_document_editor_callback'),
    path('varlik-qr-tara/', asset_qr_scanner_view, name='asset_qr_scanner'),
    path('qr-etiket/<int:pk>/pdf/', asset_qr_label_pdf, name='asset_qr_label_pdf'),
    path('qr-etiket/toplu-pdf/', asset_qr_labels_batch_pdf, name='asset_qr_labels_batch_pdf'),
    path('api/qr-lookup/', qr_lookup_api, name='qr_lookup_api'),
    path('wopi/files/<int:pk>', wopi_check_file_info, name='wopi_check_file_info'),
    path('wopi/files/<int:pk>/contents', wopi_file_contents, name='wopi_file_contents'),
    path('erp-entegrasyonlari/', erp_integrations_view, name='erp_integrations'),
    path('ot-entegrasyonlari/', ot_integrations_view, name='ot_integrations'),
    path('entegrasyon-merkezi/', integration_hub_center_view, name='integration_hub_center'),
    path('itsm-olgunluk/', itsm_maturity_view, name='itsm_maturity'),
    path('kurulum-merkezi/', setup_center_view, name='setup_center'),
    path('offline-saha/', offline_field_app, name='offline_field_app'),
    path('service-worker.js', service_worker_js, name='service_worker_js'),
    path('dlp-olaylari/', dlp_events_view, name='dlp_events'),
    path('talep/<int:pk>/', ticket_detail, name='ticket_detail'),
    path('indir-talepler-csv/', export_tickets_csv, name='export_tickets_csv'),
    path('api/bildirimler/', notifications_api, name='notifications_api'),
    path('api/bildirimler/<int:pk>/okundu/', mark_notification_read, name='mark_notification_read'),
    path('api/bildirimler/tumunu-okundu/', mark_all_notifications_read, name='mark_all_notifications_read'),
    path('kullanici-paneli/', user_panel, name='user_panel'),
    path('it-envanter/', it_inventory_view, name='it_inventory'),
    path('sistem-loglari/', system_logs_view, name='system_logs'),
    path('port-haritasi/', port_mapping_list_view, name='port_mapping_list'),
    path('port-haritasi/<int:device_id>/', port_mapping_view, name='port_mapping'),
    path('ad-sync/', sync_ad_users, name='sync_ad_users'), 
    
    path('bilgi-bankasi/', knowledge_base_view, name='knowledge_base'),
    path('api/kb-ara/', search_kb_api, name='search_kb_api'),

    # REST API and webhooks
    path('api/', include(router.urls)),
    path('', include('inventory.urls')),
    path('api-auth/', include('rest_framework.urls', namespace='rest_framework')), 
    path('oauth/', include('social_django.urls', namespace='social')),
    
    path('api/rack-devices/', get_rack_devices, name='rack_devices_api'),
    path('api/webhook/alert/', device_alert_webhook, name='device_alert_webhook'),

    # JWT
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    # OpenAPI docs
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
    
    # Dashboard (home)
    path('', dashboard, name='dashboard'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)