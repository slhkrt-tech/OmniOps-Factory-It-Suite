from django.contrib import messages
from django.shortcuts import redirect
from django.utils.translation import gettext as _
from functools import wraps


def role_required(allowed_roles):
    """Sadece belirtilen rollere (Gruplara) sahip kullanıcıların View'a erişmesine izin verir."""
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('login')

            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)

            user_groups = request.user.groups.values_list('name', flat=True)
            if any(role in user_groups for role in allowed_roles):
                return view_func(request, *args, **kwargs)

            messages.error(request, _('Bu sayfaya erişim yetkiniz bulunmamaktadır.'))
            if request.user.is_staff:
                return redirect('dashboard')
            return redirect('user_panel')
        return _wrapped_view
    return decorator
