"""Kullanıcı ve kurum için efektif çalışma alanı bağlamını üretir."""

import os

from django.conf import settings

from .models import FactorySite, OrganizationWorkspace, UserWorkspacePreference
from .workspace_registry import (
    DEFAULT_DASHBOARD_WIDGETS,
    DEFAULT_MODULE_LABELS,
    get_industry_preset,
    merge_module_labels,
    normalize_industry,
)


def _resolve_industry(org, prefs, request):
    if prefs and prefs.active_factory_site_id:
        site = prefs.active_factory_site
        if site:
            return normalize_industry(site.industry_type)
    if org and org.primary_industry:
        return normalize_industry(org.primary_industry)
    if request and request.session.get('workspace_industry'):
        return normalize_industry(request.session['workspace_industry'])
    env_industry = os.environ.get('WORKSPACE_PRIMARY_INDUSTRY', '')
    if env_industry:
        return normalize_industry(env_industry)
    return 'generic'


def get_active_organization():
    org = OrganizationWorkspace.objects.filter(is_active=True).order_by('id').first()
    if org:
        return org
    default_industry = normalize_industry(os.environ.get('WORKSPACE_PRIMARY_INDUSTRY', 'generic'))
    return OrganizationWorkspace.objects.create(
        name=getattr(settings, 'APP_NAME', 'OmniOps'),
        primary_industry=default_industry,
        is_active=True,
    )


def get_user_preferences(user):
    if not user.is_authenticated:
        return None
    pref, _ = UserWorkspacePreference.objects.get_or_create(user=user)
    return pref


def get_enabled_modules(org, preset):
    if org.enabled_modules:
        return set(org.enabled_modules)
    return set(preset.get('modules') or [])


def get_workspace_context(user, request=None):
    org = get_active_organization()
    prefs = get_user_preferences(user)
    industry = _resolve_industry(org, prefs, request)
    preset = get_industry_preset(industry)
    enabled = get_enabled_modules(org, preset)
    labels = merge_module_labels(org.module_labels or {}, preset)
    terminology = dict(preset.get('terminology') or {})
    terminology.update(org.terminology or {})
    features = dict(preset.get('features') or {})
    features.update(org.feature_overrides or {})
    if not getattr(settings, 'FEATURE_SALES_KANBAN', True):
        features['sales_kanban'] = False

    active_site = None
    if prefs and prefs.active_factory_site_id:
        active_site = prefs.active_factory_site
    elif user and user.is_authenticated:
        site_qs = FactorySite.objects.filter(is_active=True).order_by('customer_name', 'title')
        active_site = site_qs.filter(industry_type=industry).first() or site_qs.first()

    dashboard_layout = (prefs.dashboard_layout if prefs and prefs.dashboard_layout else None) or DEFAULT_DASHBOARD_WIDGETS
    sidebar_layout = (prefs.sidebar_layout if prefs and prefs.sidebar_layout else None) or list(enabled)

    return {
        'organization': org,
        'industry': industry,
        'industry_label': org.custom_industry_label or preset.get('label') or industry.title(),
        'tagline': org.tagline or 'Bilgi işlem için tek çalışma alanı',
        'modules': {key: key in enabled for key in DEFAULT_MODULE_LABELS},
        'module_labels': labels,
        'terminology': terminology,
        'features': features,
        'active_site': active_site,
        'drag_drop_enabled': prefs.drag_drop_enabled if prefs else True,
        'dashboard_layout': dashboard_layout,
        'sidebar_layout': sidebar_layout,
        'nav_labels': preset.get('nav_labels') or {},
    }


def is_module_enabled(context, module_key):
    return bool(context.get('modules', {}).get(module_key, True))


def save_user_layout(user, page, order, hidden=None):
    prefs = get_user_preferences(user)
    fields = ['updated_at']
    if page == 'dashboard':
        prefs.dashboard_layout = order
        fields.insert(0, 'dashboard_layout')
        if hidden is not None:
            prefs.hidden_widgets = hidden
            fields.insert(-1, 'hidden_widgets')
    elif page == 'sidebar':
        prefs.sidebar_layout = order
        fields.insert(0, 'sidebar_layout')
    prefs.save(update_fields=fields)
    return prefs
