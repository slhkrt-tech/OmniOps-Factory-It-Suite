/* OmniOps global UI scripts */
document.addEventListener('DOMContentLoaded', () => {
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });

    initCommandPalette();
    initSidebarGroups();
});

function initSidebarGroups() {
    const groups = document.querySelectorAll('.sidebar-group');
    if (!groups.length || typeof bootstrap === 'undefined') return;

    const activeLink = document.querySelector('.sidebar .nav-link.active');
    if (activeLink) {
        const parentCollapse = activeLink.closest('.collapse');
        if (parentCollapse) {
            bootstrap.Collapse.getOrCreateInstance(parentCollapse, { toggle: false }).show();
            const toggle = document.querySelector(`[data-bs-target="#${parentCollapse.id}"]`);
            if (toggle) toggle.setAttribute('aria-expanded', 'true');
        }
    }

    groups.forEach(group => {
        const collapseEl = group.querySelector('.collapse');
        const toggle = group.querySelector('.sidebar-group-toggle');
        if (!collapseEl || !toggle) return;

        const storageKey = `omniops_sidebar_${group.dataset.sidebarGroup || collapseEl.id}`;
        const saved = localStorage.getItem(storageKey);
        if (saved === 'open') {
            bootstrap.Collapse.getOrCreateInstance(collapseEl, { toggle: false }).show();
            toggle.setAttribute('aria-expanded', 'true');
        } else if (saved === 'closed') {
            bootstrap.Collapse.getOrCreateInstance(collapseEl, { toggle: false }).hide();
            toggle.setAttribute('aria-expanded', 'false');
        }

        collapseEl.addEventListener('shown.bs.collapse', () => localStorage.setItem(storageKey, 'open'));
        collapseEl.addEventListener('hidden.bs.collapse', () => localStorage.setItem(storageKey, 'closed'));
    });
}

function initCommandPalette() {
    const modalEl = document.getElementById('commandPaletteModal');
    const input = document.getElementById('global-search-input');
    const results = document.getElementById('global-search-results');
    if (!modalEl || !input || !results || typeof bootstrap === 'undefined') return;

    const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
    let timer = null;

    function render(items) {
        if (!items.length) {
            results.innerHTML = '<div class="command-empty">Sonuç bulunamadı. Farklı bir kelime deneyin.</div>';
            return;
        }
        results.innerHTML = items.map(item => `
            <a class="command-result-item" href="${item.url || '#'}">
                <span class="command-result-icon"><span class="iconify" data-icon="${item.icon || 'mdi:flash-outline'}"></span></span>
                <span class="command-result-copy">
                    <span class="command-result-title">${escapeHtml(item.title || '')}</span>
                    <span class="command-result-subtitle">${escapeHtml(item.type || '')} · ${escapeHtml(item.subtitle || '')}</span>
                </span>
                <span class="iconify command-result-arrow" data-icon="mdi:arrow-right"></span>
            </a>
        `).join('');
    }

    function search(q = '') {
        fetch(`/api/global-search/?q=${encodeURIComponent(q)}`, { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
            .then(response => response.ok ? response.json() : Promise.reject(response))
            .then(data => render(data.results || []))
            .catch(() => {
                results.innerHTML = '<div class="command-empty text-danger">Arama servisi şu an yanıt vermiyor.</div>';
            });
    }

    modalEl.addEventListener('shown.bs.modal', () => {
        input.focus();
        input.select();
        search(input.value.trim());
    });

    input.addEventListener('input', () => {
        clearTimeout(timer);
        timer = setTimeout(() => search(input.value.trim()), 180);
    });

    document.addEventListener('keydown', event => {
        if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
            event.preventDefault();
            modal.show();
        }
    });
}

function escapeHtml(value) {
    return String(value)
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;')
        .replaceAll("'", '&#039;');
}

// ==========================================
// ORTAK FONKSİYONLAR
// Herhangi bir HTML sayfasından çağrılabilir.
// ==========================================

// --- 3. ŞİFRE GİZLE / GÖSTER (Iconify Destekli) ---
// Örnek kullanım: onclick="togglePasswordVisibility('loginPassword', 'eyeIcon')"
function togglePasswordVisibility(inputId, iconId) {
    const passInput = document.getElementById(inputId);
    const eyeIcon = document.getElementById(iconId);
    
    if (passInput && eyeIcon) {
        if (passInput.type === 'password') {
            passInput.type = 'text';
            eyeIcon.setAttribute('data-icon', 'mdi:eye-off-outline'); // Çizgili göz ikonu
        } else {
            passInput.type = 'password';
            eyeIcon.setAttribute('data-icon', 'mdi:eye-outline'); // Normal göz ikonu
        }
    }
}

// --- 4. BUTON YÜKLENİYOR ---
// Örnek kullanım: onclick="showGlobalLoading('submitBtn', 'Kaydediliyor...')"
function showGlobalLoading(btnId, loadingText = "İşleniyor...") {
    const btn = document.getElementById(btnId);
    
    if (btn) {
        btn.innerHTML = `<span class="iconify me-2 animate-spin" data-icon="mdi:loading"></span> ${loadingText}`;
    }
}