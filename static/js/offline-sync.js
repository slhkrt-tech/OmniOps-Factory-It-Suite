(function () {
    const DB_NAME = 'omniops-offline';
    const STORE = 'ticketQueue';

    function t(key, fallback) {
        if (window.OmniOpsI18n && window.OmniOpsI18n[key]) {
            return window.OmniOpsI18n[key];
        }
        return fallback;
    }

    function openDb() {
        return new Promise((resolve, reject) => {
            const request = indexedDB.open(DB_NAME, 1);
            request.onupgradeneeded = () => {
                request.result.createObjectStore(STORE, {keyPath: 'id', autoIncrement: true});
            };
            request.onsuccess = () => resolve(request.result);
            request.onerror = () => reject(request.error);
        });
    }

    async function addQueuedTicket(payload) {
        const db = await openDb();
        return new Promise((resolve, reject) => {
            const tx = db.transaction(STORE, 'readwrite');
            tx.objectStore(STORE).add({...payload, queued_at: new Date().toISOString()});
            tx.oncomplete = resolve;
            tx.onerror = () => reject(tx.error);
        });
    }

    async function listQueuedTickets() {
        const db = await openDb();
        return new Promise((resolve, reject) => {
            const tx = db.transaction(STORE, 'readonly');
            const request = tx.objectStore(STORE).getAll();
            request.onsuccess = () => resolve(request.result || []);
            request.onerror = () => reject(request.error);
        });
    }

    async function deleteQueuedTicket(id) {
        const db = await openDb();
        return new Promise((resolve, reject) => {
            const tx = db.transaction(STORE, 'readwrite');
            tx.objectStore(STORE).delete(id);
            tx.oncomplete = resolve;
            tx.onerror = () => reject(tx.error);
        });
    }

    async function syncQueuedTickets(config) {
        const items = await listQueuedTickets();
        const errors = [];
        for (const item of items) {
            const response = await fetch(config.endpoint, {
                method: 'POST',
                headers: {'Content-Type': 'application/json', 'X-CSRFToken': config.csrfToken},
                body: JSON.stringify({
                    title: item.title,
                    description: item.description,
                    priority: item.priority,
                    category: item.category
                })
            });
            if (response.ok) {
                await deleteQueuedTicket(item.id);
            } else {
                let message = t('syncFailed', `#${item.id} senkronize edilemedi`).replace('%(id)s', item.id);
                try {
                    const payload = await response.json();
                    message = payload.detail || payload.error || JSON.stringify(payload);
                } catch (error) {
                    message = await response.text();
                }
                errors.push(message);
            }
        }
        return errors;
    }

    function renderQueue(items, queueList) {
        if (!items.length) {
            queueList.innerHTML = `<span class="text-muted">${t('queueEmpty', 'Bekleyen kayıt yok.')}</span>`;
            return;
        }
        queueList.innerHTML = items.map(item => `
            <div class="border rounded-3 p-3 mb-2">
                <div class="fw-bold">${item.title}</div>
                <div class="text-muted small">${item.priority} · ${new Date(item.queued_at).toLocaleString()}</div>
            </div>
        `).join('');
    }

    window.OmniOpsOffline = {
        async init(config) {
            const form = document.getElementById(config.formId);
            const queueList = document.getElementById(config.queueListId);
            const status = document.getElementById(config.statusId);
            const syncButton = document.getElementById(config.syncButtonId);

            const refresh = async () => {
                const items = await listQueuedTickets();
                renderQueue(items, queueList);
                status.textContent = navigator.onLine ? t('online', 'Online') : t('offline', 'Offline');
                status.className = `badge ${navigator.onLine ? 'bg-success' : 'bg-danger'}`;
            };

            form.addEventListener('submit', async (event) => {
                event.preventDefault();
                const data = Object.fromEntries(new FormData(form).entries());
                if (navigator.onLine) {
                    try {
                        const response = await fetch(config.endpoint, {
                            method: 'POST',
                            headers: {'Content-Type': 'application/json', 'X-CSRFToken': config.csrfToken},
                            body: JSON.stringify(data)
                        });
                        if (!response.ok) throw new Error(t('apiResponseFailed', 'API yanıtı başarısız'));
                        form.reset();
                        const errors = await syncQueuedTickets(config);
                        if (errors.length) {
                            alert(`${t('syncWarning', 'Senkronizasyon uyarısı:')}\n${errors.join('\n')}`);
                        }
                    } catch (error) {
                        await addQueuedTicket(data);
                    }
                } else {
                    await addQueuedTicket(data);
                }
                await refresh();
            });

            syncButton.addEventListener('click', async () => {
                const errors = await syncQueuedTickets(config);
                if (errors.length) {
                    alert(`${t('syncWarning', 'Senkronizasyon uyarısı:')}\n${errors.join('\n')}`);
                }
                await refresh();
            });
            window.addEventListener('online', async () => {
                await syncQueuedTickets(config);
                await refresh();
            });
            window.addEventListener('offline', refresh);

            await syncQueuedTickets(config).catch(() => {});
            await refresh();
        }
    };
})();
