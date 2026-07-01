from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated, IsAdminUser, AllowAny
from rest_framework import status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema
from drf_spectacular.types import OpenApiTypes
from django.contrib.auth.models import User
from django.utils import timezone
from django.conf import settings
from django.db.models import Q, Count
from guardian.shortcuts import get_objects_for_user

# Filtreleme, Arama ve Sıralama araçları
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter

from .models import (
    Device, IpAddress, Ticket, DevicePerformanceLog, ChangeRequest, RemoteProbe, SystemLog,
    TicketComment, TicketAttachment, TicketCategory, Notification,
    NetworkScan, NetworkScanHost, FieldVisit, SalesOpportunity, DLPEvent,
    FactoryArea, ConsumableItem, MaintenanceTask, EmployeeITProcess,
    ProcurementRequest, OnCallShift, BackupJobMonitor, VendorSupportCase, AssetHandover,
    MajorIncident, AccessRequest, PrinterFleetItem, Runbook,
    RemoteAccessGrant, DepartmentChannel, DepartmentMessage, CameraDevice,
    BusinessApplication, ReportTemplate,
    ChangeCalendarEvent, ServiceDependency, IntegrationHealthCheck,
    ComplianceControl, DocumentOutputJob,
    DirectoryConnection, DirectoryGroup, DirectoryUser, EndpointDevice,
    IdentityLifecycleTask,
    FactoryDepartment, FactoryZone, ManagedDocument, FactoryITAssetRelation,
    FactorySite, DepartmentInventoryItem,
    AssetQRTag, ERPConnection,
    ProblemRecord, ReleaseRecord, NotificationChannel, MonitoringConnection,
    ModulePermissionGrant,
)
from .serializers import (
    DeviceSerializer, IpAddressSerializer, TicketSerializer, UserSerializer, UserCreateSerializer,
    DevicePerformanceLogSerializer, ChangeRequestSerializer, RemoteProbeSerializer,
    TicketCommentSerializer, TicketAttachmentSerializer, TicketCategorySerializer,
    NotificationSerializer, NetworkScanSerializer, FieldVisitSerializer,
    SalesOpportunitySerializer, DLPEventSerializer, FactoryAreaSerializer,
    ConsumableItemSerializer, MaintenanceTaskSerializer, EmployeeITProcessSerializer,
    ProcurementRequestSerializer, OnCallShiftSerializer, BackupJobMonitorSerializer,
    VendorSupportCaseSerializer, AssetHandoverSerializer, MajorIncidentSerializer,
    AccessRequestSerializer, PrinterFleetItemSerializer, RunbookSerializer,
    RemoteAccessGrantSerializer, DepartmentChannelSerializer, DepartmentMessageSerializer,
    CameraDeviceSerializer, BusinessApplicationSerializer, ReportTemplateSerializer,
    ChangeCalendarEventSerializer, ServiceDependencySerializer,
    IntegrationHealthCheckSerializer, ComplianceControlSerializer,
    DocumentOutputJobSerializer,
    DirectoryConnectionSerializer, DirectoryGroupSerializer, DirectoryUserSerializer,
    EndpointDeviceSerializer, IdentityLifecycleTaskSerializer,
    FactoryDepartmentSerializer, FactoryZoneSerializer,
    FactorySiteSerializer, DepartmentInventoryItemSerializer,
    ManagedDocumentSerializer, FactoryITAssetRelationSerializer,
    AssetQRTagSerializer, ERPConnectionSerializer,
    ProblemRecordSerializer, ReleaseRecordSerializer, MonitoringConnectionSerializer,
    NotificationChannelSerializer, ModulePermissionGrantSerializer,
)
from .permissions import IsSupportStaff, TicketObjectPermission, NotificationOwnerPermission
from .helpdesk import is_support_staff, can_access_ticket, get_helpdesk_analytics
from .site_access import filter_queryset_by_site, get_accessible_sites

# Konfigürasyon motorunu içe aktarıyoruz
from .utils import generate_device_config, scan_network

class UserViewSet(viewsets.ModelViewSet):
    """Kullanıcı yönetimi API'si."""
    queryset = User.objects.prefetch_related('groups', 'profile').order_by('id')
    permission_classes = [IsAdminUser]
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ['username', 'email', 'first_name', 'last_name']
    ordering_fields = ['date_joined', 'username']

    def get_serializer_class(self):
        if self.action == 'create':
            return UserCreateSerializer
        return UserSerializer

    def get_permissions(self):
        if self.action == 'me':
            return [IsAuthenticated()]
        return [IsAdminUser()]

    @action(detail=False, methods=['get'], url_path='me')
    def me(self, request):
        serializer = UserSerializer(request.user)
        return Response(serializer.data)

class DeviceViewSet(viewsets.ModelViewSet):
    """Cihaz envanterine API üzerinden CRUD işlemi yapar."""
    queryset = Device.objects.order_by('id')
    serializer_class = DeviceSerializer
    permission_classes = [IsAuthenticated]

    # Cihazlarda filtreleme, arama ve sıralama
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['device_type', 'is_active', 'parent_device'] 
    search_fields = ['name', 'mac_address'] 
    ordering_fields = ['name', 'id']

    # ==================================================
    # API UÇ NOKTASI (CUSTOM ACTION)
    # ==================================================
    @action(detail=False, methods=['post'], url_path='generate-config')
    def generate_config(self, request):
        """
        Dışarıdan JSON olarak gelen cihaz parametrelerini alır
        ve üretilmiş CLI konfigürasyonunu JSON olarak geri döndürür.
        """
        # Gelen JSON verilerini request.data'dan alıyoruz
        vendor = request.data.get('vendor', 'cisco')
        device_type = request.data.get('device_type', 'switch')
        hostname = request.data.get('hostname', 'API-Device')
        vlan_id = request.data.get('vlan_id', '10')
        vlan_name = request.data.get('vlan_name', 'API_VLAN')
        interface_name = request.data.get('interface_name', 'GigabitEthernet0/1')
        
        # Checkbox/Boolean değerler string, boolean veya integer gelebileceği için güvenli dönüşüm
        enable_ospf_raw = request.data.get('enable_ospf', False)
        enable_ospf = str(enable_ospf_raw).lower() in ['yes', 'true', '1']
        
        ospf_network = request.data.get('ospf_network', '')
        ospf_area = request.data.get('ospf_area', '0')
        
        enable_port_security_raw = request.data.get('enable_port_security', False)
        enable_port_security = str(enable_port_security_raw).lower() in ['yes', 'true', '1']
        
        mac_limit = request.data.get('mac_limit', '1')

        # utils.py içindeki asıl motoru çalıştırıyoruz
        generated_code = generate_device_config(
            vendor=vendor, 
            device_type=device_type, 
            hostname=hostname, 
            vlan_id=vlan_id, 
            vlan_name=vlan_name, 
            interface_name=interface_name, 
            enable_ospf=enable_ospf, 
            ospf_network=ospf_network, 
            ospf_area=ospf_area, 
            enable_port_security=enable_port_security, 
            mac_limit=mac_limit
        )

        return Response({
            "status": "success",
            "message": f"{vendor.capitalize()} {device_type.capitalize()} için konfigürasyon başarıyla üretildi.",
            "configuration": generated_code
        })

class IpAddressViewSet(viewsets.ModelViewSet):
    """IP adresi haritasını ve atamalarını JSON döner."""
    queryset = IpAddress.objects.order_by('id')
    serializer_class = IpAddressSerializer
    permission_classes = [IsAuthenticated]
    
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ['device']
    search_fields = ['address']


class NetworkScanViewSet(viewsets.ModelViewSet):
    """Ping/ARP/raw-socket destekli ağ tarama geçmişi ve tetikleyici API."""
    queryset = NetworkScan.objects.select_related('requested_by').prefetch_related('hosts').all()
    serializer_class = NetworkScanSerializer
    permission_classes = [IsAuthenticated, IsSupportStaff]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['method', 'requested_by']
    search_fields = ['network', 'hosts__ip_address', 'hosts__mac_address', 'hosts__vendor']
    ordering_fields = ['created_at', 'active_hosts', 'duration_ms']
    http_method_names = ['get', 'post', 'head', 'options']

    def create(self, request, *args, **kwargs):
        network = request.data.get('network', '192.168.1.0/24')
        method = request.data.get('method', 'hybrid')
        result = scan_network(network, method=method)

        scan = NetworkScan.objects.create(
            requested_by=request.user,
            network=network,
            method=method,
            total_hosts=result.get('total_scanned', 0),
            active_hosts=len(result.get('active_ips', [])),
            duration_ms=result.get('duration_ms', 0),
            error=result.get('error', ''),
        )
        for host in result.get('active_ips', []):
            NetworkScanHost.objects.create(
                scan=scan,
                ip_address=host.get('ip'),
                mac_address=host.get('mac', ''),
                hostname=host.get('hostname', ''),
                vendor=host.get('vendor', ''),
                detected_by=host.get('detected_by', ''),
                latency_ms=host.get('latency_ms'),
                raw_socket_open=host.get('raw_socket_open', False),
            )
        return Response(NetworkScanSerializer(scan).data, status=status.HTTP_201_CREATED)


class TicketViewSet(viewsets.ModelViewSet):
    """Destek biletlerini API üzerinden yönetir."""
    queryset = Ticket.objects.none()
    serializer_class = TicketSerializer
    permission_classes = [IsAuthenticated, TicketObjectPermission]

    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['status', 'priority', 'category', 'device', 'assigned_to', 'is_escalated']
    search_fields = ['title', 'description']
    ordering_fields = ['created_at', 'priority', 'sla_deadline']

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Ticket.objects.none()
        user = self.request.user
        qs = Ticket.objects.select_related(
            'created_by', 'assigned_to', 'device', 'ticket_category', 'factory_site',
        )
        if user.is_staff or is_support_staff(user):
            return filter_queryset_by_site(qs, user)
        return qs.filter(Q(created_by=user) | Q(assigned_to=user))

    def perform_create(self, serializer):
        from rest_framework.exceptions import PermissionDenied
        from .dlp import inspect_text_for_dlp, has_blocking_dlp_event

        title = serializer.validated_data.get('title', '')
        description = serializer.validated_data.get('description', '')
        dlp_events = inspect_text_for_dlp(
            f"{title}\n{description}",
            user=self.request.user,
            source='ticket_api',
            block=True,
        )
        if has_blocking_dlp_event(dlp_events):
            raise PermissionDenied('DLP politikası: Talep metni hassas veri içeriyor.')
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=['post'], url_path='assign')
    def assign(self, request, pk=None):
        if not is_support_staff(request.user):
            return Response({'error': 'Yetkisiz'}, status=status.HTTP_403_FORBIDDEN)
        ticket = self.get_object()
        assignee_id = request.data.get('assigned_to')
        if not assignee_id:
            return Response({'error': 'assigned_to gerekli'}, status=status.HTTP_400_BAD_REQUEST)
        assignee = User.objects.filter(pk=assignee_id, is_active=True).first()
        if not assignee:
            return Response({'error': 'Kullanıcı bulunamadı'}, status=status.HTTP_404_NOT_FOUND)
        ticket.assigned_to = assignee
        ticket.save()
        from .helpdesk import notify_user
        notify_user(assignee, f'Talep atandı: #{ticket.id}', ticket.title,
                    link=f'/talep/{ticket.id}/', notification_type='assignment', ticket=ticket)
        return Response(TicketSerializer(ticket).data)

    @action(detail=True, methods=['post'], url_path='close')
    def close(self, request, pk=None):
        ticket = self.get_object()
        if not can_access_ticket(request.user, ticket):
            return Response({'error': 'Yetkisiz'}, status=status.HTTP_403_FORBIDDEN)
        ticket.status = request.data.get('status', 'Kapatildi')
        ticket.save()
        return Response(TicketSerializer(ticket).data)

    @action(detail=False, methods=['get'], url_path='analytics')
    def analytics(self, request):
        if not is_support_staff(request.user):
            return Response({'error': 'Yetkisiz'}, status=status.HTTP_403_FORBIDDEN)
        return Response(get_helpdesk_analytics())


class TicketCommentViewSet(viewsets.ModelViewSet):
    queryset = TicketComment.objects.none()
    serializer_class = TicketCommentSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['ticket']
    ordering_fields = ['created_at']

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return TicketComment.objects.none()
        qs = TicketComment.objects.select_related('author', 'ticket')
        user = self.request.user
        if is_support_staff(user):
            return qs
        return qs.filter(ticket__created_by=user, is_internal=False)

    def perform_create(self, serializer):
        ticket = serializer.validated_data['ticket']
        if not can_access_ticket(self.request.user, ticket):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('Bu talebe yorum ekleyemezsiniz.')
        serializer.save(author=self.request.user)


class TicketAttachmentViewSet(viewsets.ModelViewSet):
    queryset = TicketAttachment.objects.none()
    serializer_class = TicketAttachmentSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['ticket']
    http_method_names = ['get', 'post', 'delete', 'head', 'options']

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return TicketAttachment.objects.none()
        user = self.request.user
        qs = TicketAttachment.objects.select_related('uploaded_by', 'ticket')
        if is_support_staff(user):
            return qs
        return qs.filter(ticket__created_by=user)

    def perform_create(self, serializer):
        ticket = serializer.validated_data['ticket']
        if not can_access_ticket(self.request.user, ticket):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('Bu talebe dosya ekleyemezsiniz.')
        serializer.save(uploaded_by=self.request.user)


class TicketCategoryViewSet(viewsets.ModelViewSet):
    queryset = TicketCategory.objects.filter(is_active=True)
    serializer_class = TicketCategorySerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [SearchFilter]
    search_fields = ['name', 'slug']

    def get_permissions(self):
        if self.action in ('create', 'update', 'partial_update', 'destroy'):
            return [IsAdminUser()]
        return super().get_permissions()


class NotificationViewSet(viewsets.ModelViewSet):
    queryset = Notification.objects.none()
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated, NotificationOwnerPermission]
    http_method_names = ['get', 'patch', 'head', 'options']

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Notification.objects.none()
        return Notification.objects.filter(user=self.request.user).order_by('-created_at')

    @action(detail=False, methods=['post'], url_path='mark-all-read')
    def mark_all_read(self, request):
        self.get_queryset().filter(is_read=False).update(is_read=True)
        return Response({'status': 'ok'})

    @action(detail=False, methods=['get'], url_path='unread-count')
    def unread_count(self, request):
        count = self.get_queryset().filter(is_read=False).count()
        return Response({'unread_count': count})


class FieldVisitViewSet(viewsets.ModelViewSet):
    queryset = FieldVisit.objects.none()
    serializer_class = FieldVisitSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['status', 'technician']
    search_fields = ['title', 'customer_name', 'address']
    ordering_fields = ['order_index', 'scheduled_at', 'distance_km']

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return FieldVisit.objects.none()
        qs = FieldVisit.objects.select_related('technician', 'ticket')
        if is_support_staff(self.request.user):
            return qs.all()
        return qs.filter(technician=self.request.user)

    def perform_create(self, serializer):
        technician_id = self.request.data.get('technician')
        technician = User.objects.filter(id=technician_id).first() if technician_id and is_support_staff(self.request.user) else self.request.user
        serializer.save(technician=technician)

    @action(detail=False, methods=['post'], url_path='optimize-route')
    def optimize_route(self, request):
        visit_ids = request.data.get('visit_ids', [])
        visits = list(self.get_queryset().filter(id__in=visit_ids))
        # Basit nearest-neighbor: coğrafi koordinat varsa bir önceki noktaya en yakın sıraya dizer.
        ordered = []
        current = None
        remaining = visits[:]
        while remaining:
            if not current:
                next_visit = remaining.pop(0)
            else:
                next_visit = min(
                    remaining,
                    key=lambda v: ((v.latitude or 0) - (current.latitude or 0)) ** 2 + ((v.longitude or 0) - (current.longitude or 0)) ** 2,
                )
                remaining.remove(next_visit)
            ordered.append(next_visit)
            current = next_visit
        for idx, visit in enumerate(ordered):
            visit.order_index = idx + 1
            visit.save(update_fields=['order_index', 'updated_at'])
        return Response(FieldVisitSerializer(ordered, many=True).data)


class SalesOpportunityViewSet(viewsets.ModelViewSet):
    queryset = SalesOpportunity.objects.none()
    serializer_class = SalesOpportunitySerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['stage', 'owner']
    search_fields = ['title', 'customer_name', 'notes']
    ordering_fields = ['position', 'potential_revenue', 'updated_at']

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return SalesOpportunity.objects.none()
        qs = SalesOpportunity.objects.select_related('owner')
        if is_support_staff(self.request.user):
            return qs.all()
        return qs.filter(owner=self.request.user)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

    @action(detail=True, methods=['patch'], url_path='move')
    def move(self, request, pk=None):
        opportunity = self.get_object()
        stage = request.data.get('stage')
        if stage not in dict(SalesOpportunity.STAGE_CHOICES):
            return Response({'error': 'Geçersiz aşama'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            position = int(request.data.get('position', opportunity.position))
        except (TypeError, ValueError):
            return Response({'error': 'Geçersiz pozisyon'}, status=status.HTTP_400_BAD_REQUEST)
        opportunity.stage = stage
        opportunity.position = position
        opportunity.save(update_fields=['stage', 'position', 'updated_at'])
        return Response(SalesOpportunitySerializer(opportunity).data)


class DLPEventViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = DLPEventSerializer
    permission_classes = [IsAuthenticated, IsSupportStaff]
    queryset = DLPEvent.objects.select_related('user').all()
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['severity', 'blocked', 'source']
    search_fields = ['rule', 'excerpt', 'user__username']
    ordering_fields = ['created_at', 'severity']


class FactoryAreaViewSet(viewsets.ModelViewSet):
    queryset = FactoryArea.objects.order_by('name')
    serializer_class = FactoryAreaSerializer
    permission_classes = [IsAuthenticated, IsSupportStaff]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['criticality']
    search_fields = ['name', 'code', 'manager_name']
    ordering_fields = ['name', 'criticality', 'created_at']


class ConsumableItemViewSet(viewsets.ModelViewSet):
    queryset = ConsumableItem.objects.order_by('category', 'name')
    serializer_class = ConsumableItemSerializer
    permission_classes = [IsAuthenticated, IsSupportStaff]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['category', 'location', 'vendor']
    search_fields = ['name', 'sku', 'compatible_with', 'location', 'vendor']
    ordering_fields = ['name', 'quantity', 'minimum_quantity', 'updated_at']


class MaintenanceTaskViewSet(viewsets.ModelViewSet):
    queryset = MaintenanceTask.objects.select_related('factory_area', 'device', 'asset', 'owner').order_by('next_due_at')
    serializer_class = MaintenanceTaskSerializer
    permission_classes = [IsAuthenticated, IsSupportStaff]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['task_type', 'status', 'factory_area', 'owner']
    search_fields = ['title', 'checklist', 'notes', 'factory_area__name']
    ordering_fields = ['next_due_at', 'status', 'task_type', 'updated_at']

    @action(detail=True, methods=['post'], url_path='mark-done')
    def mark_done(self, request, pk=None):
        task = self.get_object()
        task.mark_done()
        return Response(self.get_serializer(task).data)


class EmployeeITProcessViewSet(viewsets.ModelViewSet):
    queryset = EmployeeITProcess.objects.select_related('factory_area', 'requester', 'assigned_to').order_by('status', 'due_date')
    serializer_class = EmployeeITProcessSerializer
    permission_classes = [IsAuthenticated, IsSupportStaff]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['process_type', 'status', 'factory_area', 'assigned_to']
    search_fields = ['employee_name', 'department', 'notes']
    ordering_fields = ['due_date', 'status', 'created_at', 'updated_at']

    def perform_create(self, serializer):
        serializer.save(requester=self.request.user)


class ProcurementRequestViewSet(viewsets.ModelViewSet):
    queryset = ProcurementRequest.objects.select_related('requester', 'approved_by', 'factory_area').order_by('-created_at')
    serializer_class = ProcurementRequestSerializer
    permission_classes = [IsAuthenticated, IsSupportStaff]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['category', 'status', 'factory_area']
    search_fields = ['title', 'description', 'vendor_name']
    ordering_fields = ['created_at', 'needed_by', 'estimated_cost']

    def perform_create(self, serializer):
        serializer.save(requester=self.request.user)

    @action(detail=True, methods=['post'], url_path='approve')
    def approve(self, request, pk=None):
        procurement = self.get_object()
        procurement.status = 'approved'
        procurement.approved_by = request.user
        procurement.save(update_fields=['status', 'approved_by', 'updated_at'])
        return Response(self.get_serializer(procurement).data)


class OnCallShiftViewSet(viewsets.ModelViewSet):
    queryset = OnCallShift.objects.select_related('engineer').order_by('-start_at')
    serializer_class = OnCallShiftSerializer
    permission_classes = [IsAuthenticated, IsSupportStaff]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['engineer', 'is_primary']
    search_fields = ['engineer__username', 'phone', 'notes']
    ordering_fields = ['start_at', 'end_at']


class BackupJobMonitorViewSet(viewsets.ModelViewSet):
    queryset = BackupJobMonitor.objects.select_related('owner').order_by('last_status', 'next_run_at')
    serializer_class = BackupJobMonitorSerializer
    permission_classes = [IsAuthenticated, IsSupportStaff]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['system_type', 'last_status', 'is_active', 'owner']
    search_fields = ['name', 'target_host', 'schedule_description', 'notes']
    ordering_fields = ['next_run_at', 'last_run_at', 'name']

    @action(detail=True, methods=['post'], url_path='mark-success')
    def mark_success(self, request, pk=None):
        job = self.get_object()
        job.last_status = 'success'
        job.last_run_at = timezone.now()
        job.save(update_fields=['last_status', 'last_run_at', 'updated_at'])
        return Response(self.get_serializer(job).data)


class VendorSupportCaseViewSet(viewsets.ModelViewSet):
    queryset = VendorSupportCase.objects.select_related('vendor_contract', 'assigned_to').order_by('status', '-opened_at')
    serializer_class = VendorSupportCaseSerializer
    permission_classes = [IsAuthenticated, IsSupportStaff]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['priority', 'status', 'assigned_to', 'vendor_name']
    search_fields = ['title', 'vendor_name', 'case_number', 'description']
    ordering_fields = ['opened_at', 'priority', 'status']

    @action(detail=True, methods=['post'], url_path='resolve')
    def resolve(self, request, pk=None):
        case = self.get_object()
        case.status = 'resolved'
        case.resolved_at = timezone.now()
        case.save(update_fields=['status', 'resolved_at', 'updated_at'])
        return Response(self.get_serializer(case).data)


class AssetHandoverViewSet(viewsets.ModelViewSet):
    queryset = AssetHandover.objects.select_related('asset', 'factory_area', 'performed_by').order_by('-handover_date')
    serializer_class = AssetHandoverSerializer
    permission_classes = [IsAuthenticated, IsSupportStaff]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['action', 'factory_area', 'asset']
    search_fields = ['employee_name', 'department', 'asset__name', 'condition_notes']
    ordering_fields = ['handover_date', 'created_at']

    def perform_create(self, serializer):
        serializer.save(performed_by=self.request.user)


class MajorIncidentViewSet(viewsets.ModelViewSet):
    queryset = MajorIncident.objects.select_related('factory_area', 'ticket', 'incident_commander').order_by('status', '-started_at')
    serializer_class = MajorIncidentSerializer
    permission_classes = [IsAuthenticated, IsSupportStaff]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['severity', 'status', 'factory_area', 'incident_commander']
    search_fields = ['title', 'impact_summary', 'root_cause', 'corrective_actions']
    ordering_fields = ['started_at', 'resolved_at', 'severity', 'status']

    @action(detail=True, methods=['post'], url_path='resolve')
    def resolve(self, request, pk=None):
        incident = self.get_object()
        incident.status = 'resolved'
        incident.resolved_at = timezone.now()
        incident.save(update_fields=['status', 'resolved_at', 'updated_at'])
        return Response(self.get_serializer(incident).data)


class AccessRequestViewSet(viewsets.ModelViewSet):
    queryset = AccessRequest.objects.select_related('requester', 'approved_by').order_by('status', '-created_at')
    serializer_class = AccessRequestSerializer
    permission_classes = [IsAuthenticated, IsSupportStaff]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['access_type', 'status', 'department']
    search_fields = ['employee_name', 'department', 'target_system', 'justification']
    ordering_fields = ['created_at', 'expires_at', 'status']

    def perform_create(self, serializer):
        serializer.save(requester=self.request.user)

    @action(detail=True, methods=['post'], url_path='approve')
    def approve(self, request, pk=None):
        access_request = self.get_object()
        access_request.status = 'approved'
        access_request.approved_by = request.user
        access_request.save(update_fields=['status', 'approved_by', 'updated_at'])
        return Response(self.get_serializer(access_request).data)

    @action(detail=True, methods=['post'], url_path='provision')
    def provision(self, request, pk=None):
        access_request = self.get_object()
        access_request.status = 'provisioned'
        access_request.provisioned_at = timezone.now()
        access_request.save(update_fields=['status', 'provisioned_at', 'updated_at'])
        return Response(self.get_serializer(access_request).data)


class PrinterFleetItemViewSet(viewsets.ModelViewSet):
    queryset = PrinterFleetItem.objects.select_related('factory_area', 'consumable').order_by('status', 'name')
    serializer_class = PrinterFleetItemSerializer
    permission_classes = [IsAuthenticated, IsSupportStaff]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['device_kind', 'status', 'factory_area', 'consumable']
    search_fields = ['name', 'ip_address', 'serial_number', 'model', 'notes']
    ordering_fields = ['name', 'page_counter', 'toner_level_percent', 'updated_at']

    @action(detail=True, methods=['post'], url_path='maintenance-done')
    def maintenance_done(self, request, pk=None):
        printer = self.get_object()
        printer.status = 'online'
        printer.last_maintenance_at = timezone.now()
        printer.save(update_fields=['status', 'last_maintenance_at', 'updated_at'])
        return Response(self.get_serializer(printer).data)


class RunbookViewSet(viewsets.ModelViewSet):
    queryset = Runbook.objects.select_related('owner').order_by('category', 'title')
    serializer_class = RunbookSerializer
    permission_classes = [IsAuthenticated, IsSupportStaff]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['category', 'is_active', 'owner']
    search_fields = ['title', 'steps', 'rollback_steps', 'related_device_type']
    ordering_fields = ['title', 'category', 'updated_at', 'last_reviewed_at']


class RemoteAccessGrantViewSet(viewsets.ModelViewSet):
    queryset = RemoteAccessGrant.objects.select_related('approved_by').order_by('status', 'expires_at')
    serializer_class = RemoteAccessGrantSerializer
    permission_classes = [IsAuthenticated, IsSupportStaff]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['access_method', 'status', 'department', 'mfa_required']
    search_fields = ['employee_name', 'department', 'target_resource', 'gateway', 'allowed_source']
    ordering_fields = ['created_at', 'expires_at', 'status']

    @action(detail=True, methods=['post'], url_path='activate')
    def activate(self, request, pk=None):
        grant = self.get_object()
        grant.status = 'active'
        grant.approved_by = request.user
        grant.save(update_fields=['status', 'approved_by', 'updated_at'])
        return Response(self.get_serializer(grant).data)


class DepartmentChannelViewSet(viewsets.ModelViewSet):
    queryset = DepartmentChannel.objects.order_by('department', 'name')
    serializer_class = DepartmentChannelSerializer
    permission_classes = [IsAuthenticated, IsSupportStaff]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['department', 'is_active']
    search_fields = ['name', 'department', 'description']
    ordering_fields = ['name', 'department', 'created_at']


class DepartmentMessageViewSet(viewsets.ModelViewSet):
    queryset = DepartmentMessage.objects.select_related('channel', 'author').order_by('-created_at')
    serializer_class = DepartmentMessageSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['channel', 'is_announcement']
    search_fields = ['message', 'author__username', 'channel__name']
    ordering_fields = ['created_at']

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)


class CameraDeviceViewSet(viewsets.ModelViewSet):
    queryset = CameraDevice.objects.select_related('factory_area').order_by('status', 'location', 'name')
    serializer_class = CameraDeviceSerializer
    permission_classes = [IsAuthenticated, IsSupportStaff]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['device_type', 'status', 'factory_area']
    search_fields = ['name', 'ip_address', 'location', 'notes']
    ordering_fields = ['name', 'status', 'updated_at', 'recording_days']


class BusinessApplicationViewSet(viewsets.ModelViewSet):
    queryset = BusinessApplication.objects.select_related('technical_owner').order_by('app_type', 'name')
    serializer_class = BusinessApplicationSerializer
    permission_classes = [IsAuthenticated, IsSupportStaff]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['app_type', 'status', 'sso_enabled', 'owner_department']
    search_fields = ['name', 'url', 'owner_department', 'notes']
    ordering_fields = ['name', 'app_type', 'status', 'updated_at']


class ReportTemplateViewSet(viewsets.ModelViewSet):
    queryset = ReportTemplate.objects.select_related('owner').order_by('report_type', 'title')
    serializer_class = ReportTemplateSerializer
    permission_classes = [IsAuthenticated, IsSupportStaff]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['report_type', 'is_active', 'owner']
    search_fields = ['title', 'description', 'query_notes', 'output_format']
    ordering_fields = ['title', 'report_type', 'updated_at']


class ChangeCalendarEventViewSet(viewsets.ModelViewSet):
    queryset = ChangeCalendarEvent.objects.select_related('factory_area', 'change_request', 'owner').order_by('start_at')
    serializer_class = ChangeCalendarEventSerializer
    permission_classes = [IsAuthenticated, IsSupportStaff]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['event_type', 'risk_level', 'status', 'factory_area', 'owner']
    search_fields = ['title', 'expected_impact', 'rollback_plan']
    ordering_fields = ['start_at', 'end_at', 'risk_level', 'status']

    @action(detail=True, methods=['post'], url_path='complete')
    def complete(self, request, pk=None):
        event = self.get_object()
        event.status = 'completed'
        event.save(update_fields=['status', 'updated_at'])
        return Response(self.get_serializer(event).data)


class ServiceDependencyViewSet(viewsets.ModelViewSet):
    queryset = ServiceDependency.objects.select_related('business_application', 'device').order_by('criticality', 'business_application__name')
    serializer_class = ServiceDependencySerializer
    permission_classes = [IsAuthenticated, IsSupportStaff]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['business_application', 'device', 'dependency_type', 'criticality']
    search_fields = ['name', 'business_application__name', 'device__name', 'impact_description']
    ordering_fields = ['criticality', 'created_at']


class IntegrationHealthCheckViewSet(viewsets.ModelViewSet):
    queryset = IntegrationHealthCheck.objects.select_related('owner').order_by('last_status', 'name')
    serializer_class = IntegrationHealthCheckSerializer
    permission_classes = [IsAuthenticated, IsSupportStaff]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['integration_type', 'last_status', 'owner']
    search_fields = ['name', 'endpoint_url', 'notes']
    ordering_fields = ['last_status', 'last_checked_at', 'response_time_ms', 'updated_at']

    @action(detail=True, methods=['post'], url_path='mark-healthy')
    def mark_healthy(self, request, pk=None):
        check = self.get_object()
        check.last_status = 'healthy'
        check.last_checked_at = timezone.now()
        check.save(update_fields=['last_status', 'last_checked_at', 'updated_at'])
        return Response(self.get_serializer(check).data)


class ComplianceControlViewSet(viewsets.ModelViewSet):
    queryset = ComplianceControl.objects.select_related('owner').order_by('status', 'due_date')
    serializer_class = ComplianceControlSerializer
    permission_classes = [IsAuthenticated, IsSupportStaff]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['framework', 'status', 'owner']
    search_fields = ['title', 'evidence', 'remediation_plan']
    ordering_fields = ['due_date', 'status', 'updated_at']

    @action(detail=True, methods=['post'], url_path='mark-compliant')
    def mark_compliant(self, request, pk=None):
        control = self.get_object()
        control.status = 'compliant'
        control.last_checked_at = timezone.now().date()
        control.save(update_fields=['status', 'last_checked_at', 'updated_at'])
        return Response(self.get_serializer(control).data)


class DocumentOutputJobViewSet(viewsets.ModelViewSet):
    queryset = DocumentOutputJob.objects.select_related('requested_by', 'template').order_by('status', '-created_at')
    serializer_class = DocumentOutputJobSerializer
    permission_classes = [IsAuthenticated, IsSupportStaff]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['job_type', 'status', 'output_format', 'template']
    search_fields = ['title', 'notes', 'template__title']
    ordering_fields = ['created_at', 'updated_at', 'status']

    def perform_create(self, serializer):
        serializer.save(requested_by=self.request.user)

    @action(detail=True, methods=['post'], url_path='mark-ready')
    def mark_ready(self, request, pk=None):
        job = self.get_object()
        job.status = 'ready'
        job.save(update_fields=['status', 'updated_at'])
        return Response(self.get_serializer(job).data)


class DevicePerformanceLogViewSet(viewsets.ReadOnlyModelViewSet):
    """Cihaz performans geçmişini API olarak sunar."""
    queryset = DevicePerformanceLog.objects.select_related('device').all()
    serializer_class = DevicePerformanceLogSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['device']
    search_fields = ['device__name']
    ordering_fields = ['recorded_at']

# ==================================================
# --- DAĞITIK PROBE (AJAN) UÇ NOKTALARI ---
# ==================================================
class RemoteProbeViewSet(viewsets.ModelViewSet):
    """Uzak Ajanların (Probe) merkez sunucuyla iletişim kurduğu API noktası."""
    queryset = RemoteProbe.objects.all()
    serializer_class = RemoteProbeSerializer
    permission_classes = [IsAdminUser]
    
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['status', 'location']
    search_fields = ['name', 'location', 'ip_address']
    ordering_fields = ['last_heartbeat']

    def get_permissions(self):
        # Ajanlar standart kullanıcı olmadığından sadece heartbeat/sync-data
        # uçları shared-secret ile dış dünyaya açıktır.
        if self.action in ['heartbeat', 'sync_data']:
            return [AllowAny()]
        return [IsAdminUser()]

    def _verify_probe_secret(self, request):
        """Güvenlik: Gelen isteğin gerçekten bizim ajanımızdan gelip gelmediğini doğrula."""
        client_secret = request.headers.get('X-Remote-Probe-Secret') or request.data.get('secret')
        server_secret = getattr(settings, 'REMOTE_PROBE_SHARED_SECRET', None)
        if not server_secret or client_secret != server_secret:
            return False
        return True

    @action(detail=False, methods=['post'], url_path='heartbeat')
    def heartbeat(self, request):
        """Ajanın her 15 dakikada bir 'Ben Hayattayım' dediği ve yeni görevleri aldığı uç nokta."""
        if not self._verify_probe_secret(request):
            return Response({'error': 'Unauthorized Probe'}, status=status.HTTP_401_UNAUTHORIZED)

        probe_name = request.data.get('name')
        ip_addr = request.data.get('ip_address')
        if not probe_name or not ip_addr:
            return Response({'error': 'Name and IP required'}, status=status.HTTP_400_BAD_REQUEST)

        probe, created = RemoteProbe.objects.update_or_create(
            name=probe_name,
            defaults={
                'ip_address': ip_addr,
                'location': request.data.get('location', ''),
                'target_subnet': request.data.get('target_subnet', ''),
                'agent_version': request.data.get('agent_version', '1.0.0'),
                'status': 'online',
                'last_heartbeat': timezone.now(),
            }
        )

        if created:
            SystemLog.objects.create(action='SYSTEM', details=f"Yeni Ajan (Probe) Sisteme Eklendi: {probe.name}")

        tasks = self._get_pending_tasks_for_probe(probe)

        return Response({
            'status': 'success',
            'probe_id': probe.id,
            'created': created,
            'last_heartbeat': probe.last_heartbeat.isoformat(),
            'tasks': tasks,
        })

    @action(detail=False, methods=['post'], url_path='sync-data')
    def sync_data(self, request):
        """Ajanın bulduğu IP'leri, performans verilerini ve konfigürasyonları merkeze kaydeder."""
        if not self._verify_probe_secret(request):
            return Response({'error': 'Unauthorized Probe'}, status=status.HTTP_401_UNAUTHORIZED)

        probe_id = request.data.get('probe_id')
        discovered_ips = request.data.get('discovered_ips', [])
        performance_metrics = request.data.get('performance_metrics', {})
        device_configs = request.data.get('device_configs', [])

        if not isinstance(discovered_ips, list):
            return Response({'error': 'discovered_ips liste olmalıdır'}, status=status.HTTP_400_BAD_REQUEST)
        if not isinstance(performance_metrics, dict):
            return Response({'error': 'performance_metrics nesne olmalıdır'}, status=status.HTTP_400_BAD_REQUEST)
        if not isinstance(device_configs, list):
            return Response({'error': 'device_configs liste olmalıdır'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            probe = RemoteProbe.objects.get(id=probe_id)
        except RemoteProbe.DoesNotExist:
            return Response({'error': 'Probe not found'}, status=status.HTTP_404_NOT_FOUND)

        processed_ips = 0
        processed_configs = 0

        # 1. IP Adreslerini Kaydet
        for ip in discovered_ips:
            obj, created = IpAddress.objects.get_or_create(
                address=ip,
                defaults={'is_allocated': True}
            )
            if created:
                processed_ips += 1

        # 2. Cihaz Konfigürasyonlarını Yedekle
        from .models import DeviceBackup, DevicePerformanceLog
        for config_data in device_configs:
            ip_addr = config_data.get('ip')
            config_text = config_data.get('config')
            
            if ip_addr and config_text:
                # Gelen IP sistemde kayıtlı bir 'Cihaz' (Device) ile eşleşiyorsa yedeği al
                ip_record = IpAddress.objects.filter(address=ip_addr).select_related('device').first()
                if ip_record and ip_record.device:
                    DeviceBackup.objects.create(
                        device=ip_record.device,
                        config_text=config_text,
                        backed_up_by=None # Otomatik ajan yedeği
                    )
                    processed_configs += 1

        # 3. Probe Performans Verisi (AIOps Tahminlemesi İçin)
        if performance_metrics:
            # Ajanın kurulu olduğu sunucu da bizim envanterimizde kayıtlı bir Device ise logla
            probe_ip_record = IpAddress.objects.filter(address=probe.ip_address).select_related('device').first()
            if probe_ip_record and probe_ip_record.device:
                DevicePerformanceLog.objects.create(
                    device=probe_ip_record.device,
                    cpu_usage=performance_metrics.get('cpu_usage', 0),
                    ram_usage=performance_metrics.get('ram_usage', 0),
                    disk_usage=performance_metrics.get('disk_usage', 0)
                )

        if processed_ips > 0 or processed_configs > 0:
            SystemLog.objects.create(
                action='SCAN',
                details=f"Dağıtık Mimari: '{probe.name}' ajanı {processed_ips} yeni IP keşfetti ve {processed_configs} cihazın konfigürasyon yedeğini aldı."
            )

        return Response({
            'status': 'success',
            'message': 'Probe verisi başarıyla alındı ve işlendi.',
            'processed_ips': processed_ips,
            'processed_configs': processed_configs
        })

    def _get_pending_tasks_for_probe(self, probe):
        tasks = []
        if probe.target_subnet:
            tasks.append({
                'id': f"scan_{probe.id}_{int(timezone.now().timestamp())}",
                'type': 'network_scan',
                'target': probe.target_subnet,
                'priority': 'high'
            })
        return tasks

class ChangeRequestViewSet(viewsets.ModelViewSet):
    """ChangeRequest nesnesini API ile yöneten viewset."""
    queryset = ChangeRequest.objects.all()
    serializer_class = ChangeRequestSerializer
    permission_classes = [IsAuthenticated, IsSupportStaff]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['status', 'requester', 'target_ip', 'vendor']
    search_fields = ['title', 'config_payload']
    ordering_fields = ['created_at', 'status']

    def get_queryset(self):
        if self.request.user.is_staff:
            return ChangeRequest.objects.all()
        return ChangeRequest.objects.filter(requester=self.request.user)

    def perform_create(self, serializer):
        serializer.save(requester=self.request.user)

    @action(detail=False, methods=['post'], url_path='bulk-create')
    def bulk_create(self, request):
        """Bulk konfigürasyon talebini API üzerinden yaratır ve Celery kuyruğuna alır."""
        target_device_ids = request.data.get('target_devices', [])
        config_payload = request.data.get('config_payload', '')
        vendor = request.data.get('vendor', '')
        title = request.data.get('title', f"Toplu Konfigürasyon Talebi - {timezone.now().strftime('%d.%m.%Y %H:%M')}")

        if not target_device_ids or not config_payload:
            return Response(
                {'status': 'error', 'message': 'target_devices ve config_payload alanları zorunludur.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        change_request = ChangeRequest.objects.create(
            title=title,
            requester=request.user,
            status='pending',
            vendor=vendor,
            config_payload=config_payload
        )
        change_request.target_devices.set(Device.objects.filter(id__in=target_device_ids))

        from .tasks import bulk_push_config_to_devices
        bulk_push_config_to_devices.delay(change_request.id)

        serializer = self.get_serializer(change_request)
        return Response(
            {'status': 'success', 'message': 'Bulk operation queued.', 'change_request': serializer.data},
            status=status.HTTP_201_CREATED
        )


class DirectoryConnectionViewSet(viewsets.ModelViewSet):
    queryset = DirectoryConnection.objects.select_related('owner').order_by('name')
    serializer_class = DirectoryConnectionSerializer
    permission_classes = [IsAuthenticated, IsSupportStaff]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['directory_type', 'sync_enabled', 'last_sync_status']
    search_fields = ['name', 'server_uri', 'base_dn']
    ordering_fields = ['name', 'last_sync_at', 'last_sync_status']

    @action(detail=True, methods=['post'], url_path='sync')
    def sync(self, request, pk=None):
        connection = self.get_object()
        connection.last_sync_at = timezone.now()
        if connection.is_ready:
            connection.last_sync_status = 'healthy'
            connection.last_sync_message = 'Sync isteği alındı. LDAP worker entegrasyonu için hazır.'
        else:
            connection.last_sync_status = 'warning'
            connection.last_sync_message = 'Bağlantı bilgileri eksik veya sync kapalı.'
        connection.save(update_fields=['last_sync_at', 'last_sync_status', 'last_sync_message', 'updated_at'])
        SystemLog.objects.create(
            user=request.user,
            action='SYSTEM',
            details=f"Directory sync tetiklendi: {connection.name} ({connection.last_sync_status})"
        )
        return Response(DirectoryConnectionSerializer(connection).data)


class DirectoryGroupViewSet(viewsets.ModelViewSet):
    serializer_class = DirectoryGroupSerializer
    permission_classes = [IsAuthenticated, IsSupportStaff]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['connection', 'risk_level', 'is_privileged', 'mapped_role']
    search_fields = ['name', 'description', 'mapped_system', 'distinguished_name']
    ordering_fields = ['name', 'risk_level', 'last_seen_at']

    def get_queryset(self):
        return DirectoryGroup.objects.select_related('connection', 'owner').annotate(member_count=Count('members')).order_by('-is_privileged', 'name')


class DirectoryUserViewSet(viewsets.ModelViewSet):
    queryset = DirectoryUser.objects.select_related('connection', 'user').prefetch_related('groups').order_by('status', 'username')
    serializer_class = DirectoryUserSerializer
    permission_classes = [IsAuthenticated, IsSupportStaff]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['connection', 'status', 'department', 'mfa_enabled']
    search_fields = ['username', 'display_name', 'email', 'department', 'title']
    ordering_fields = ['username', 'department', 'last_login_at', 'last_seen_at']

    @action(detail=True, methods=['post'], url_path='mark-reviewed')
    def mark_reviewed(self, request, pk=None):
        directory_user = self.get_object()
        note = request.data.get('risk_note') or 'Erişim gözden geçirildi.'
        directory_user.risk_note = note
        directory_user.last_seen_at = timezone.now()
        directory_user.save(update_fields=['risk_note', 'last_seen_at', 'updated_at'])
        return Response(DirectoryUserSerializer(directory_user).data)


class EndpointDeviceViewSet(viewsets.ModelViewSet):
    queryset = EndpointDevice.objects.select_related('asset', 'assigned_user', 'factory_area').order_by('status', 'hostname')
    serializer_class = EndpointDeviceSerializer
    permission_classes = [IsAuthenticated, IsSupportStaff]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['device_type', 'status', 'factory_area', 'antivirus_ok', 'disk_encrypted']
    search_fields = ['hostname', 'serial_number', 'assigned_to_text', 'os_name', 'ip_address']
    ordering_fields = ['hostname', 'status', 'last_seen_at', 'updated_at']

    @action(detail=True, methods=['post'], url_path='mark-compliant')
    def mark_compliant(self, request, pk=None):
        endpoint = self.get_object()
        endpoint.status = 'compliant'
        endpoint.antivirus_ok = True
        endpoint.disk_encrypted = True
        endpoint.last_seen_at = timezone.now()
        endpoint.save(update_fields=['status', 'antivirus_ok', 'disk_encrypted', 'last_seen_at', 'updated_at'])
        return Response(EndpointDeviceSerializer(endpoint).data)


class IdentityLifecycleTaskViewSet(viewsets.ModelViewSet):
    queryset = IdentityLifecycleTask.objects.select_related('directory_user', 'requested_by', 'assigned_to').order_by('status', 'due_date')
    serializer_class = IdentityLifecycleTaskSerializer
    permission_classes = [IsAuthenticated, IsSupportStaff]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['process_type', 'status', 'assigned_to', 'department']
    search_fields = ['title', 'employee_name', 'department', 'notes']
    ordering_fields = ['due_date', 'created_at', 'status']

    def perform_create(self, serializer):
        serializer.save(requested_by=self.request.user)

    @action(detail=True, methods=['post'], url_path='mark-done')
    def mark_done(self, request, pk=None):
        task = self.get_object()
        task.status = 'done'
        task.ad_account_done = True
        task.mailbox_done = True
        task.groups_done = True
        task.endpoint_done = True
        task.vpn_done = True
        task.save(update_fields=[
            'status', 'ad_account_done', 'mailbox_done', 'groups_done',
            'endpoint_done', 'vpn_done', 'updated_at',
        ])
        return Response(IdentityLifecycleTaskSerializer(task).data)


class FactorySiteViewSet(viewsets.ModelViewSet):
    serializer_class = FactorySiteSerializer
    permission_classes = [IsAuthenticated, IsSupportStaff]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['industry_type', 'is_active', 'customer_name', 'portfolio_code']
    search_fields = ['title', 'short_name', 'code', 'customer_name', 'city', 'custom_industry_label']
    ordering_fields = ['title', 'customer_name', 'industry_type', 'updated_at']

    def get_queryset(self):
        qs = FactorySite.objects.annotate(
            department_count=Count('departments', filter=Q(departments__is_active=True), distinct=True),
            inventory_count=Count('inventory_items', filter=Q(inventory_items__is_active=True), distinct=True),
        ).order_by('customer_name', 'title')
        site_ids = get_accessible_sites(self.request.user).values_list('pk', flat=True)
        return qs.filter(pk__in=site_ids)


class FactoryDepartmentViewSet(viewsets.ModelViewSet):
    serializer_class = FactoryDepartmentSerializer
    permission_classes = [IsAuthenticated, IsSupportStaff]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['factory_site', 'department_type', 'criticality', 'is_active']
    search_fields = ['name', 'code', 'manager_name', 'floor_label']
    ordering_fields = ['name', 'department_type', 'criticality', 'updated_at']

    def get_queryset(self):
        qs = FactoryDepartment.objects.annotate(zone_count=Count('zones')).order_by('factory_site__title', 'department_type', 'name')
        return filter_queryset_by_site(qs, self.request.user)


class DepartmentInventoryItemViewSet(viewsets.ModelViewSet):
    serializer_class = DepartmentInventoryItemSerializer
    permission_classes = [IsAuthenticated, IsSupportStaff]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['factory_site', 'department', 'zone', 'item_type', 'status', 'is_active']
    search_fields = ['title', 'reference_code', 'serial_number', 'asset_tag', 'barcode', 'category_label', 'owner_name']
    ordering_fields = ['sort_order', 'title', 'updated_at', 'quantity']

    def get_queryset(self):
        qs = DepartmentInventoryItem.objects.select_related(
            'factory_site', 'department', 'zone',
        ).order_by('factory_site__title', 'department__name', 'sort_order', 'title')
        return filter_queryset_by_site(qs, self.request.user)


class FactoryZoneViewSet(viewsets.ModelViewSet):
    queryset = FactoryZone.objects.select_related('department', 'factory_area').order_by('department__name', 'name')
    serializer_class = FactoryZoneSerializer
    permission_classes = [IsAuthenticated, IsSupportStaff]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['department', 'zone_type', 'criticality', 'is_active', 'factory_area']
    search_fields = ['name', 'code', 'building', 'floor', 'description']
    ordering_fields = ['name', 'zone_type', 'criticality', 'updated_at']


class ManagedDocumentViewSet(viewsets.ModelViewSet):
    queryset = ManagedDocument.objects.select_related('department', 'zone', 'owner').order_by('-updated_at')
    serializer_class = ManagedDocumentSerializer
    permission_classes = [IsAuthenticated, IsSupportStaff]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['category', 'file_type', 'status', 'department', 'zone', 'preview_enabled']
    search_fields = ['title', 'reference_code', 'description', 'tags']
    ordering_fields = ['title', 'updated_at', 'valid_until', 'status']

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

    @action(detail=True, methods=['post'], url_path='approve')
    def approve(self, request, pk=None):
        document = self.get_object()
        document.status = 'approved'
        document.save(update_fields=['status', 'updated_at'])
        return Response(ManagedDocumentSerializer(document, context={'request': request}).data)


class FactoryITAssetRelationViewSet(viewsets.ModelViewSet):
    queryset = FactoryITAssetRelation.objects.select_related(
        'department', 'zone', 'device', 'camera', 'endpoint', 'printer',
        'application', 'ticket', 'document', 'maintenance_task', 'consumable', 'it_asset',
    ).order_by('asset_type', '-updated_at')
    serializer_class = FactoryITAssetRelationSerializer
    permission_classes = [IsAuthenticated, IsSupportStaff]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['department', 'zone', 'asset_type', 'role']
    search_fields = ['label', 'notes', 'department__name', 'zone__name']
    ordering_fields = ['asset_type', 'role', 'updated_at']


class AssetQRTagViewSet(viewsets.ModelViewSet):
    queryset = AssetQRTag.objects.select_related(
        'device', 'endpoint', 'it_asset', 'camera', 'printer', 'factory_zone', 'consumable',
    ).order_by('code')
    serializer_class = AssetQRTagSerializer
    permission_classes = [IsAuthenticated, IsSupportStaff]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['tag_type', 'is_active']
    search_fields = ['code', 'label', 'location']
    ordering_fields = ['code', 'tag_type', 'updated_at']


class ERPConnectionViewSet(viewsets.ModelViewSet):
    queryset = ERPConnection.objects.select_related('owner').order_by('erp_type', 'name')
    serializer_class = ERPConnectionSerializer
    permission_classes = [IsAuthenticated, IsSupportStaff]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['erp_type', 'sync_enabled', 'last_sync_status']
    search_fields = ['name', 'base_url', 'database_name', 'username']
    ordering_fields = ['name', 'last_sync_at', 'last_sync_status']

    @action(detail=True, methods=['post'], url_path='test')
    def test_connection(self, request, pk=None):
        connection = self.get_object()
        from .integrations.erp_connector import ERPClientError, test_erp_connection
        try:
            result = test_erp_connection(connection)
            connection.last_sync_status = 'healthy'
            connection.last_sync_message = f"Test OK · {result.get('server_version', '')}"
            connection.save(update_fields=['last_sync_status', 'last_sync_message', 'updated_at'])
            return Response({'status': 'ok', 'result': result})
        except ERPClientError as exc:
            connection.last_sync_status = 'error'
            connection.last_sync_message = str(exc)
            connection.save(update_fields=['last_sync_status', 'last_sync_message', 'updated_at'])
            return Response({'status': 'error', 'detail': str(exc)}, status=400)

    @action(detail=True, methods=['post'], url_path='sync')
    def sync(self, request, pk=None):
        connection = self.get_object()
        from .integrations.erp_connector import ERPClientError, sync_erp_connection
        try:
            count, message = sync_erp_connection(connection)
            connection.last_sync_at = timezone.now()
            connection.last_sync_status = 'healthy'
            connection.last_sync_message = message
            connection.records_synced = count
            connection.save(update_fields=[
                'last_sync_at', 'last_sync_status', 'last_sync_message', 'records_synced', 'updated_at',
            ])
            return Response(ERPConnectionSerializer(connection).data)
        except ERPClientError as exc:
            connection.last_sync_status = 'error'
            connection.last_sync_message = str(exc)
            connection.save(update_fields=['last_sync_status', 'last_sync_message', 'updated_at'])
            return Response({'detail': str(exc)}, status=400)


class ProblemRecordViewSet(viewsets.ModelViewSet):
    serializer_class = ProblemRecordSerializer
    permission_classes = [IsAuthenticated, IsSupportStaff]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['status', 'priority', 'factory_site', 'owner']
    search_fields = ['title', 'description', 'root_cause']
    ordering_fields = ['updated_at', 'priority', 'created_at']

    def get_queryset(self):
        qs = ProblemRecord.objects.select_related('factory_site', 'owner', 'major_incident').order_by('-updated_at')
        return filter_queryset_by_site(qs, self.request.user)

    def perform_create(self, serializer):
        serializer.save(owner=serializer.validated_data.get('owner') or self.request.user)


class ReleaseRecordViewSet(viewsets.ModelViewSet):
    serializer_class = ReleaseRecordSerializer
    permission_classes = [IsAuthenticated, IsSupportStaff]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['status', 'factory_site', 'cab_approved', 'owner']
    search_fields = ['title', 'version', 'description']
    ordering_fields = ['planned_start', 'updated_at']

    def get_queryset(self):
        qs = ReleaseRecord.objects.select_related('factory_site', 'owner', 'change_request').order_by('-planned_start', '-updated_at')
        return filter_queryset_by_site(qs, self.request.user)

    def perform_create(self, serializer):
        serializer.save(owner=serializer.validated_data.get('owner') or self.request.user)


class MonitoringConnectionViewSet(viewsets.ModelViewSet):
    serializer_class = MonitoringConnectionSerializer
    permission_classes = [IsAuthenticated, IsSupportStaff]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['monitor_type', 'sync_enabled', 'last_sync_status', 'factory_site']
    search_fields = ['name', 'base_url']
    ordering_fields = ['name', 'last_sync_at']

    def get_queryset(self):
        qs = MonitoringConnection.objects.select_related('factory_site').order_by('name')
        return filter_queryset_by_site(qs, self.request.user)

    @action(detail=True, methods=['post'], url_path='sync')
    def sync(self, request, pk=None):
        from inventory.tasks import sync_monitoring_connection_task
        sync_monitoring_connection_task.delay(self.get_object().pk)
        return Response({'status': 'queued'})


class NotificationChannelViewSet(viewsets.ModelViewSet):
    serializer_class = NotificationChannelSerializer
    permission_classes = [IsAuthenticated, IsSupportStaff]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['channel_type', 'is_active', 'factory_site']
    search_fields = ['name', 'endpoint_url', 'email_recipients']
    ordering_fields = ['name', 'last_sent_at']

    def get_queryset(self):
        qs = NotificationChannel.objects.select_related('factory_site', 'owner').order_by('name')
        return filter_queryset_by_site(qs, self.request.user)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


class ModulePermissionGrantViewSet(viewsets.ModelViewSet):
    serializer_class = ModulePermissionGrantSerializer
    permission_classes = [IsAuthenticated, IsSupportStaff]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['module_code', 'permission_level', 'is_active', 'factory_site', 'user']
    search_fields = ['user__username']
    ordering_fields = ['created_at', 'module_code']

    def get_queryset(self):
        return ModulePermissionGrant.objects.select_related('user', 'factory_site', 'granted_by').order_by('-created_at')

    def perform_create(self, serializer):
        serializer.save(granted_by=self.request.user)


# ==================================================
# --- KABİN ÇİZİMİ İÇİN API ---
# ==================================================
@extend_schema(responses={200: OpenApiTypes.OBJECT})
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_rack_devices(request):
    """
    Sadece 'rack_name' (kabin adı) olan cihazları JSON olarak döndürür.
    Rack çizim sayfasındaki (JavaScript) fetch API bu endpoint'i kullanır.
    """
    # Kabin adı boş olmayan cihazları getir
    if request.user.is_superuser:
        devices = Device.objects.all()
    else:
        devices = get_objects_for_user(request.user, 'inventory.view_device')
    devices = devices.exclude(rack_name__isnull=True).exclude(rack_name__exact='')
    data = []
    for d in devices:
        data.append({
            'id': d.id,
            'name': d.name,
            'type': d.device_type,
            'rack_name': d.rack_name,
            'rack_u_position': d.position_u,  
            'rack_u_height': d.height_u,      
        })
    return Response(data)