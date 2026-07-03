"""OmniOps modül kaydı ve sektör bazlı çalışma alanı profilleri."""

WORKSPACE_MODULE_KEYS = (
    'command',
    'factory',
    'network',
    'identity',
    'service',
    'security',
    'reports',
    'admin',
)

DEFAULT_MODULE_LABELS = {
    'command': 'Genel Bakış',
    'factory': 'Fabrika & Envanter',
    'network': 'Altyapı',
    'identity': 'Kimlik & Erişim',
    'service': 'Servis Masası',
    'security': 'Güvenlik & Uyum',
    'reports': 'Rapor & Doküman',
    'admin': 'Yönetim',
}

DEFAULT_DASHBOARD_WIDGETS = [
    'metrics',
    'heatmap',
    'device_chart',
    'ticket_chart',
    'events',
    'backbone',
]

INDUSTRY_PRESETS = {
    'textile': {
        'label': 'Tekstil & Dokuma',
        'modules': ['command', 'factory', 'network', 'identity', 'service', 'security', 'reports', 'admin'],
        'features': {'sales_kanban': False, 'ot_bridge': True, 'factory_portfolio': True},
        'terminology': {
            'department_label': 'Atölye',
            'zone_label': 'Hat / Bölüm',
            'site_label': 'Tesis',
            'inventory_panel_title': 'Hat Envanteri',
        },
        'nav_labels': {
            'factory_command': 'Departman Panosu',
            'monitor': 'Üretim Hattı İzleme',
        },
    },
    'food': {
        'label': 'Gıda & İçecek',
        'modules': ['command', 'factory', 'network', 'identity', 'service', 'security', 'reports', 'admin'],
        'features': {'sales_kanban': False, 'ot_bridge': True, 'factory_portfolio': True},
        'terminology': {
            'department_label': 'Birim',
            'zone_label': 'Hat / Oda',
            'site_label': 'Tesis',
            'inventory_panel_title': 'Hijyen & Hat Envanteri',
        },
        'nav_labels': {'monitor': 'Proses İzleme'},
    },
    'automotive': {
        'label': 'Otomotiv Yan Sanayi',
        'modules': ['command', 'factory', 'network', 'identity', 'service', 'security', 'reports', 'admin'],
        'features': {'sales_kanban': True, 'ot_bridge': True, 'factory_portfolio': True},
        'terminology': {
            'department_label': 'Departman',
            'zone_label': 'Hücre / Hat',
            'inventory_panel_title': 'Pres & Montaj Envanteri',
        },
    },
    'solar': {
        'label': 'Güneş Enerjisi & PV',
        'modules': ['command', 'factory', 'network', 'security', 'reports', 'admin'],
        'features': {'sales_kanban': True, 'ot_bridge': True, 'factory_portfolio': True, 'identity': False},
        'terminology': {
            'department_label': 'Saha',
            'zone_label': 'İnverter Grubu',
            'site_label': 'Santral / Saha',
            'inventory_panel_title': 'PV Ekipman Envanteri',
        },
        'nav_labels': {
            'factory_group': 'Saha & Santral',
            'factory_command': 'Santral Panosu',
            'monitor': 'SCADA Performansı',
            'network': 'Ağ & Telemetri',
            'ot_integrations': 'Inverter / SCADA Köprüsü',
        },
    },
    'energy': {
        'label': 'Enerji & Utilities',
        'modules': ['command', 'factory', 'network', 'identity', 'security', 'reports', 'admin'],
        'features': {'ot_bridge': True, 'factory_portfolio': True},
        'terminology': {
            'department_label': 'Tesis',
            'zone_label': 'Ünite',
            'inventory_panel_title': 'Enerji Varlık Envanteri',
        },
        'nav_labels': {'monitor': 'SCADA & Performans'},
    },
    'logistics': {
        'label': 'Lojistik & Depo',
        'modules': ['command', 'factory', 'network', 'identity', 'service', 'security', 'reports', 'admin'],
        'features': {'sales_kanban': False, 'factory_portfolio': True},
        'terminology': {
            'department_label': 'Operasyon',
            'zone_label': 'Depo / Hat',
            'inventory_panel_title': 'Depo & Araç Envanteri',
        },
    },
    'generic': {
        'label': 'Genel Endüstri',
        'modules': list(WORKSPACE_MODULE_KEYS),
        'features': {'sales_kanban': True, 'ot_bridge': True, 'factory_portfolio': True, 'identity': True},
        'terminology': {
            'department_label': 'Bölüm',
            'zone_label': 'Alt Alan',
            'site_label': 'Tesis',
            'inventory_panel_title': 'Bölüm Envanteri',
        },
    },
}

INDUSTRY_ALIASES = {
    'custom': 'generic',
    'chemical': 'generic',
    'electronics': 'generic',
    'pharma': 'food',
    'metal': 'automotive',
    'paper': 'textile',
}


def normalize_industry(industry_key):
    key = (industry_key or 'generic').strip().lower()
    return INDUSTRY_ALIASES.get(key, key if key in INDUSTRY_PRESETS else 'generic')


def get_industry_preset(industry_key):
    return INDUSTRY_PRESETS.get(normalize_industry(industry_key), INDUSTRY_PRESETS['generic'])


def merge_module_labels(org_labels=None, preset=None):
    labels = dict(DEFAULT_MODULE_LABELS)
    if preset:
        nav = preset.get('nav_labels') or {}
        if nav.get('factory_group'):
            labels['factory'] = nav['factory_group']
        if nav.get('network'):
            labels['network'] = nav['network']
    if org_labels:
        labels.update(org_labels)
    return labels
