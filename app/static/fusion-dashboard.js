/**
 * Fusion Dashboard v2.0 - Plane + MeterSphere Fusion Architecture Controller
 */

(function () {
  'use strict';

  let rawData = null;
  let allCases = [];
  let currentModuleFilter = 'all';
  let currentStatusFilter = 'all';
  let currentSearchText = '';

  function escapeHtml(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function init() {
    loadDashboardData();
    setupEvents();
  }

  function setupEvents() {
    window.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') {
        closeDrawer();
      }
    });

    const backdrop = document.getElementById('drawer-backdrop');
    if (backdrop) {
      backdrop.addEventListener('click', closeDrawer);
    }

    const closeBtn = document.getElementById('drawer-close-btn');
    if (closeBtn) {
      closeBtn.addEventListener('click', closeDrawer);
    }

    const searchInput = document.getElementById('tree-search-input');
    if (searchInput) {
      searchInput.addEventListener('input', function (e) {
        currentSearchText = e.target.value.trim();
        renderTable();
      });
    }

    const statusTabs = document.querySelectorAll('.filter-tab');
    statusTabs.forEach(function (tab) {
      tab.addEventListener('click', function () {
        statusTabs.forEach(t => t.classList.remove('active'));
        tab.classList.add('active');
        currentStatusFilter = tab.getAttribute('data-status') || 'all';
        renderTable();
      });
    });
  }

  function loadDashboardData() {
    fetch('/api/v1/project-status/lightweight?page=dashboard_v2')
      .then(function (res) {
        if (!res.ok) throw new Error('Failed to load dashboard data');
        return res.json();
      })
      .then(function (json) {
        if (!json.success || !json.data) return;
        rawData = json.data;
        allCases = rawData.cases || [];
        renderTopModules(rawData.modules || []);
        renderFeishuLinks(rawData.feishu_links || {});
        renderTree(rawData.tree || []);
        renderTable();
      })
      .catch(function (err) {
        console.error('Dashboard load error:', err);
      });
  }

  function renderFeishuLinks(links) {
    const prdBtn = document.getElementById('link-feishu-prd');
    if (prdBtn && links.prd_url) {
      prdBtn.href = links.prd_url;
      prdBtn.style.display = 'inline-flex';
    }
    const casesBtn = document.getElementById('link-feishu-cases');
    if (casesBtn && links.cases_url) {
      casesBtn.href = links.cases_url;
      casesBtn.style.display = 'inline-flex';
    }
    const reportBtn = document.getElementById('link-feishu-report');
    if (reportBtn && links.report_url) {
      reportBtn.href = links.report_url;
      reportBtn.style.display = 'inline-flex';
    }
    const subCasesBtn = document.getElementById('sub-link-feishu-cases');
    if (subCasesBtn && links.cases_url) {
      subCasesBtn.href = links.cases_url;
    }
    const drawerFeishuBtn = document.getElementById('drawer-feishu-btn');
    if (drawerFeishuBtn && links.cases_url) {
      drawerFeishuBtn.href = links.cases_url;
    }
  }

  function renderTopModules(modules) {
    const grid = document.getElementById('modules-grid');
    if (!grid) return;
    grid.innerHTML = '';

    modules.forEach(function (mod) {
      const card = document.createElement('div');
      card.className = 'module-card' + (mod.id === 'mvp-a' ? ' active-module' : '');
      card.setAttribute('data-module-id', mod.id);

      const circleClass = (mod.pass_rate > 0) ? '' : ' zero';
      const circleStyle = (mod.pass_rate > 0)
        ? 'background: conic-gradient(var(--green) ' + mod.pass_rate + '%, #e2e8f0 0);'
        : '';

      let stepperHtml = '';
      if (Array.isArray(mod.stepper)) {
        stepperHtml = mod.stepper.map((step, sIdx) => {
          const isDone = step.state === 'done';
          const isCurr = step.state === 'current';
          const cls = isDone ? 'step-dot done' : (isCurr ? 'step-dot current' : 'step-dot');
          const arrow = (sIdx < mod.stepper.length - 1) ? '<span class="step-dot-arrow">→</span>' : '';
          return '<span class="' + cls + '">' + escapeHtml(step.name) + '</span>' + arrow;
        }).join('');
      }

      card.innerHTML = `
        <div class="module-header">
          <div>
            <div class="module-name">${escapeHtml(mod.name)}</div>
            <div class="module-sub">${escapeHtml(mod.sub_title)}</div>
          </div>
          <span class="pill ${escapeHtml(mod.status_pill_class || 'pill-gray')}">${escapeHtml(mod.status_label)}</span>
        </div>
        <div class="module-body">
          <div class="progress-circle ${circleClass}" style="${circleStyle}">
            <span class="progress-val">${mod.pass_rate}%</span>
          </div>
          <div class="module-info">
            <div class="stepper-mini">${stepperHtml}</div>
            <div class="module-note">
              ${escapeHtml(mod.blocker_summary)}
            </div>
          </div>
        </div>
      `;

      card.addEventListener('click', function () {
        document.querySelectorAll('.module-card').forEach(c => c.classList.remove('active-module'));
        card.classList.add('active-module');
        selectModuleById(mod.id);
      });

      grid.appendChild(card);
    });
  }

  function renderTree(tree) {
    const container = document.getElementById('tree-list-container');
    if (!container) return;
    container.innerHTML = '';

    tree.forEach(function (item) {
      appendTreeNode(container, item, 0);
    });
  }

  function appendTreeNode(parentEl, node, level) {
    const nodeEl = document.createElement('div');
    const indentClass = level > 0 ? ' tree-indent' : '';
    const activeClass = (node.id === currentModuleFilter) ? ' active-node' : '';
    const isMvpB = node.id && (node.id.startsWith('mvp-b') || node.id.startsWith('P3'));
    const opacityStyle = isMvpB ? 'opacity: 0.7;' : '';

    nodeEl.className = 'tree-node' + indentClass + activeClass;
    nodeEl.setAttribute('data-node-id', node.id);
    if (opacityStyle) nodeEl.style.cssText = opacityStyle;

    const icon = level === 0 ? '📁' : (node.children ? '📂' : '📄');

    nodeEl.innerHTML = `
      <div class="tree-node-left">
        <span>${icon}</span>
        <span>${escapeHtml(node.label)}</span>
      </div>
      <span class="tree-count">${node.count !== undefined ? node.count : 0}</span>
    `;

    nodeEl.addEventListener('click', function () {
      document.querySelectorAll('.tree-node').forEach(n => n.classList.remove('active-node'));
      nodeEl.classList.add('active-node');
      currentModuleFilter = node.id;
      document.getElementById('pane-title').textContent = node.label;
      renderTable();
    });

    parentEl.appendChild(nodeEl);

    if (Array.isArray(node.children)) {
      node.children.forEach(function (child) {
        appendTreeNode(parentEl, child, level + 1);
      });
    }
  }

  function selectModuleById(moduleId) {
    let targetNodeId = moduleId;
    let targetLabel = '全部需求';
    if (moduleId === 'mvp-a') {
      targetNodeId = 'mvp-a';
      targetLabel = 'MVP-A 管理运营底座';
    } else if (moduleId === 'mvp-b') {
      targetNodeId = 'mvp-b';
      targetLabel = 'MVP-B 教师学情工作台';
    } else if (moduleId === 'mvp-b-ai') {
      targetNodeId = 'mvp-b-ai';
      targetLabel = 'MVP-B AI 文字整理';
    }

    currentModuleFilter = targetNodeId;
    document.querySelectorAll('.tree-node').forEach(function (n) {
      if (n.getAttribute('data-node-id') === targetNodeId) {
        n.classList.add('active-node');
        const labelSpan = n.querySelector('.tree-node-left span:last-child');
        if (labelSpan) targetLabel = labelSpan.textContent;
      } else {
        n.classList.remove('active-node');
      }
    });

    document.getElementById('pane-title').textContent = targetLabel;
    renderTable();
  }

  function renderTable() {
    const tbody = document.getElementById('case-tbody');
    if (!tbody) return;
    tbody.innerHTML = '';

    const filtered = allCases.filter(function (c) {
      let matchModule = false;
      if (currentModuleFilter === 'all') {
        matchModule = true;
      } else if (currentModuleFilter === 'mvp-a') {
        matchModule = (c.module === 'P1' || c.module === 'P2');
      } else if (currentModuleFilter === 'mvp-b' || currentModuleFilter.startsWith('P3') || currentModuleFilter === 'mvp-b-ai') {
        matchModule = false;
      } else {
        matchModule = (c.module === currentModuleFilter);
      }

      const matchStatus = (currentStatusFilter === 'all') || (c.status === currentStatusFilter);
      const matchSearch = !currentSearchText ||
        c.id.toLowerCase().includes(currentSearchText.toLowerCase()) ||
        c.title.toLowerCase().includes(currentSearchText.toLowerCase());

      return matchModule && matchStatus && matchSearch;
    });

    const isMvpBEmpty = currentModuleFilter.startsWith('mvp-b') || currentModuleFilter.startsWith('P3');

    // Update Stats Bar
    const totalCount = filtered.length;
    const passedCount = filtered.filter(c => c.status === 'passed').length;
    const blockedCount = filtered.filter(c => c.status === 'blocked').length;
    const rate = totalCount > 0 ? Math.round((passedCount / totalCount) * 1000) / 10 : 0;

    const statTotalEl = document.getElementById('stat-total');
    const statPassedEl = document.getElementById('stat-passed');
    const statBlockedEl = document.getElementById('stat-blocked');
    const statRateEl = document.getElementById('stat-rate');

    if (statTotalEl) statTotalEl.textContent = totalCount;
    if (statPassedEl) statPassedEl.textContent = passedCount;
    if (statBlockedEl) statBlockedEl.textContent = blockedCount;
    if (statRateEl) statRateEl.textContent = '(' + rate + '%)';

    // Update Tab count badges
    const passedTab = document.querySelector('.filter-tab[data-status="passed"]');
    if (passedTab) passedTab.textContent = '通过 (' + passedCount + ')';
    const blockedTab = document.querySelector('.filter-tab[data-status="blocked"]');
    if (blockedTab) blockedTab.textContent = '阻塞 (' + blockedCount + ')';

    if (filtered.length === 0) {
      const emptyMsg = isMvpBEmpty
        ? '当前需求处于前期准备中，暂未录入正式用例'
        : '当前筛选条件下暂无测试用例';
      tbody.innerHTML = '<tr><td colspan="6" style="text-align:center; padding: 48px; color: var(--text-muted); font-size: 13px;">' + escapeHtml(emptyMsg) + '</td></tr>';
      return;
    }

    filtered.forEach(function (item) {
      const tr = document.createElement('tr');
      tr.addEventListener('click', function () {
        openDrawer(item);
      });

      const pillClass = (item.status === 'passed') ? 'pill-green' : 'pill-amber';
      const statusText = item.status_label || (item.status === 'passed' ? '通过' : '阻塞 (收口中)');

      tr.innerHTML = `
        <td class="case-id-cell">${escapeHtml(item.id)}</td>
        <td><span class="pill pill-gray">${escapeHtml(item.module_name)}</span></td>
        <td class="case-title-cell" title="${escapeHtml(item.title)}">${escapeHtml(item.title)}</td>
        <td>${escapeHtml(item.automation_kind)}</td>
        <td><span class="pill ${pillClass}">${escapeHtml(statusText)}</span></td>
        <td><button class="btn-step">查看步骤 →</button></td>
      `;

      const btn = tr.querySelector('.btn-step');
      if (btn) {
        btn.addEventListener('click', function (e) {
          e.stopPropagation();
          openDrawer(item);
        });
      }

      tbody.appendChild(tr);
    });
  }

  function openDrawer(item) {
    const idEl = document.getElementById('drawer-case-id');
    const titleEl = document.getElementById('drawer-title');
    const statusEl = document.getElementById('drawer-status');
    const precondEl = document.getElementById('drawer-precond');
    const stepsEl = document.getElementById('drawer-steps');
    const expectedEl = document.getElementById('drawer-expected');
    const actualEl = document.getElementById('drawer-actual');

    if (idEl) idEl.textContent = item.id + ' · ' + (item.module_name || item.module);
    if (titleEl) titleEl.textContent = item.title;

    const isPassed = item.status === 'passed';
    const statusPill = isPassed
      ? '<span class="pill pill-green">执行通过</span> · 自动化与回归均已就绪'
      : '<span class="pill pill-amber">阻塞 (收口中)</span> · 待本轮独立测试收口';

    if (statusEl) statusEl.innerHTML = statusPill;
    if (precondEl) precondEl.textContent = item.preconditions || '测试基础环境与租户账号已就绪';
    if (stepsEl) stepsEl.textContent = item.steps || '';
    if (expectedEl) expectedEl.textContent = item.expected_result || '系统交互与数据流转正常';
    if (actualEl) actualEl.textContent = item.actual_result || '';

    const backdrop = document.getElementById('drawer-backdrop');
    const panel = document.getElementById('drawer-panel');
    if (backdrop) backdrop.classList.add('open');
    if (panel) panel.classList.add('open');
  }

  function closeDrawer() {
    const backdrop = document.getElementById('drawer-backdrop');
    const panel = document.getElementById('drawer-panel');
    if (backdrop) backdrop.classList.remove('open');
    if (panel) panel.classList.remove('open');
  }

  window.openDrawer = openDrawer;
  window.closeDrawer = closeDrawer;

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
