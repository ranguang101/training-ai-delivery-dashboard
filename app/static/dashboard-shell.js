// Shared R3 page shell: safe sync status and a text-only DOM builder.
// No delivery, document, test-run, or business payload is read here.
(function () {
  'use strict';

  const syncPanel = document.querySelector('.sync-panel, .lightweight-sync');
  const syncStatus = document.querySelector('#sync-status');
  const initialRevision = document.body.dataset.dashboardRevision || null;

  window.dashboardElement = function dashboardElement(tag, className, text) {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text !== undefined && text !== null) element.textContent = text;
    return element;
  };

  async function checkForUpdates() {
    if (!syncPanel || !syncStatus) return;
    try {
      const response = await fetch('/api/v1/project-status', { cache: 'no-store' });
      if (!response.ok) throw new Error('status request failed');
      const payload = await response.json();
      const revision = payload?.data?.revision;
      if (revision !== null && typeof revision !== 'string') {
        throw new Error('sync projection invalid');
      }
      syncPanel.classList.remove('is-error');
      syncStatus.textContent = '已连接';
      if (initialRevision && revision && revision !== initialRevision) {
        syncStatus.textContent = '发现更新，正在刷新';
        window.location.reload();
      }
    } catch {
      syncPanel.classList.add('is-error');
      syncStatus.textContent = '暂时无法同步';
    }
  }

  checkForUpdates();
  window.setInterval(checkForUpdates, 10000);
})();
