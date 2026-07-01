"""Fabrika tesis bazlı erişim kontrolü (RBAC)."""
from django.conf import settings
from django.db import models

from .helpdesk import is_support_staff
from .models import FactorySite, ModulePermissionGrant, UserFactorySiteAccess

GLOBAL_SITE_ROLES = ['Admin', 'Yönetim']
PERMISSION_RANK = {'view': 1, 'edit': 2, 'admin': 3}


def user_has_global_site_access(user):
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    if not getattr(settings, 'SITE_ACCESS_ENFORCEMENT', True) and is_support_staff(user):
        return True
    return user.groups.filter(name__in=GLOBAL_SITE_ROLES).exists()


def get_accessible_site_ids(user):
    """None = tüm tesisler; boş liste = erişim yok."""
    if not user.is_authenticated:
        return []
    if user_has_global_site_access(user):
        return None
    return list(
        UserFactorySiteAccess.objects.filter(user=user, is_active=True)
        .values_list('factory_site_id', flat=True)
    )


def get_accessible_sites(user):
    qs = FactorySite.objects.filter(is_active=True)
    site_ids = get_accessible_site_ids(user)
    if site_ids is None:
        return qs.order_by('customer_name', 'title')
    if not site_ids:
        return qs.none()
    return qs.filter(pk__in=site_ids).order_by('customer_name', 'title')


def user_can_access_site(user, site):
    if not user.is_authenticated or site is None:
        return False
    if user_has_global_site_access(user):
        return True
    site_id = site.pk if hasattr(site, 'pk') else int(site)
    return UserFactorySiteAccess.objects.filter(
        user=user, factory_site_id=site_id, is_active=True,
    ).exists()


def filter_queryset_by_site(queryset, user, site_field='factory_site'):
    site_ids = get_accessible_site_ids(user)
    if site_ids is None:
        return queryset
    if not site_ids:
        return queryset.none()
    return queryset.filter(**{f'{site_field}__in': site_ids})


def resolve_site_for_user(user, site=None, site_id=None):
    """Kullanıcının erişebildiği seçili tesis; erişim yoksa None."""
    if site and user_can_access_site(user, site):
        return site
    if site_id:
        candidate = FactorySite.objects.filter(pk=site_id, is_active=True).first()
        if candidate and user_can_access_site(user, candidate):
            return candidate
    return get_accessible_sites(user).first()


def user_has_module_permission(user, module_code, required='view', factory_site=None):
    """Modül bazlı ince taneli yetki kontrolü."""
    if not user.is_authenticated:
        return False
    if user.is_superuser or user_has_global_site_access(user):
        return True
    if factory_site and not user_can_access_site(user, factory_site):
        return False
    grants = ModulePermissionGrant.objects.filter(
        user=user, module_code=module_code, is_active=True,
    )
    if factory_site:
        grants = grants.filter(models.Q(factory_site=factory_site) | models.Q(factory_site__isnull=True))
    required_rank = PERMISSION_RANK.get(required, 1)
    for grant in grants:
        if PERMISSION_RANK.get(grant.permission_level, 0) >= required_rank:
            return True
    return False
