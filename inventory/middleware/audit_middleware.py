"""Staff işlemlerinde denetim izi oluşturur."""
from inventory.audit import record_audit


class AuditMiddleware:
    SENSITIVE_PREFIXES = (
        '/admin/', '/api/', '/kimlik-operasyonlari/', '/entegrasyon-merkezi/',
        '/itsm-olgunluk/', '/kullanici-yonetimi/', '/fabrika-portfoy-envanter/',
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.method in ('POST', 'PUT', 'PATCH', 'DELETE') and request.user.is_authenticated:
            if any(request.path.startswith(prefix) for prefix in self.SENSITIVE_PREFIXES):
                record_audit(
                    action='update' if request.method != 'DELETE' else 'delete',
                    resource_type='http_request',
                    resource_id=request.path,
                    actor=request.user,
                    request=request,
                    payload={'method': request.method, 'status': response.status_code},
                )
        return response
