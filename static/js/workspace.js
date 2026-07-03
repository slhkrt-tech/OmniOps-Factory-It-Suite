/** OmniOps global workspace UX: sürükle-bırak, layout kaydetme, kısayollar */

function getCsrfToken() {
    const match = document.cookie.match(/csrftoken=([^;]+)/);
    return match ? decodeURIComponent(match[1]) : '';
}

function persistWorkspaceLayout(page, order) {
    return fetch('/api/workspace/layout/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCsrfToken(),
            'X-Requested-With': 'XMLHttpRequest',
        },
        body: JSON.stringify({ page, order }),
    }).then(r => (r.ok ? r.json() : Promise.reject(r)));
}

function initSortableZones() {
    if (document.body.dataset.dragDrop !== '1') return;
    if (typeof Sortable === 'undefined') return;

    document.querySelectorAll('[data-sortable-zone]').forEach(zone => {
        if (zone.dataset.sortableReady === '1') return;
        const page = zone.dataset.sortableZone || 'dashboard';
        const handle = zone.dataset.sortableHandle || '.ops-drag-handle';

        Sortable.create(zone, {
            animation: 180,
            handle,
            draggable: '[data-widget-id]',
            ghostClass: 'ops-sortable-ghost',
            chosenClass: 'ops-sortable-chosen',
            dragClass: 'ops-sortable-drag',
            onEnd() {
                const order = [...zone.querySelectorAll('[data-widget-id]')]
                    .map(el => el.dataset.widgetId)
                    .filter(Boolean);
                if (!order.length) return;
                persistWorkspaceLayout(page, order).catch(console.error);
            },
        });
        zone.dataset.sortableReady = '1';
    });
}

function applyDashboardLayoutOrder(layout) {
    const zone = document.querySelector('[data-sortable-zone="dashboard"]');
    if (!zone || !Array.isArray(layout)) return;
    const map = {};
    zone.querySelectorAll('[data-widget-id]').forEach(el => {
        map[el.dataset.widgetId] = el;
    });
    layout.forEach(id => {
        if (map[id]) zone.appendChild(map[id]);
    });
}

function initWorkspaceStudio() {
    initSortableZones();

    const layout = window.__OMNIOPS_DASHBOARD_LAYOUT__;
    if (layout) applyDashboardLayoutOrder(layout);

    document.querySelectorAll('[data-collapsible-panel]').forEach(panel => {
        const key = panel.dataset.collapsiblePanel;
        const storageKey = `omniops_panel_${key}`;
        const saved = localStorage.getItem(storageKey);
        if (saved === 'collapsed') {
            panel.classList.add('is-collapsed');
        }
        const toggle = panel.querySelector('[data-collapse-toggle]');
        if (toggle) {
            toggle.addEventListener('click', () => {
                panel.classList.toggle('is-collapsed');
                localStorage.setItem(storageKey, panel.classList.contains('is-collapsed') ? 'collapsed' : 'open');
            });
        }
    });
}

document.addEventListener('DOMContentLoaded', initWorkspaceStudio);
