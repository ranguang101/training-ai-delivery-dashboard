/**
 * Fusion Dashboard v2.0 - Plane + MeterSphere Fusion Architecture Controller
 * Context-aware Feishu links & Toast Interception Patch
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

  function showToast(msg, duration) {
    duration = duration || 2500;
    let container = document.getElementById('toast-container');
    if (!container) {
      container = document.createElement('div');
      container.id = 'toast-container';
      container.className = 'toast-container';
      document.body.appendChild(container);
    }
    const toast = document.createElement('div');
    toast.className = 'toast-message';
    toast.textContent = msg;
    container.appendChild(toast);

    requestAnimationFrame(function () {
      toast.classList.add('is-visible');
    });

    setTimeout(function () {
      toast.classList.remove('is-visible');
      setTimeout(function () {
        if (toast.parentNode) {
          toast.parentNode.removeChild(toast);
        }
      }, 300);
    }, duration);
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

    // 表头飞书用例表按钮拦截
    const subCasesBtn = document.getElementById('sub-link-feishu-cases');
    if (subCasesBtn) {
      subCasesBtn.addEventListener('click', function (e) {
        if (subCasesBtn.classList.contains('is-disabled')) {
          e.preventDefault();
          let msg = '💡 该模块尚未录入飞书测试用例矩阵';
          if (currentModuleFilter.startsWith('mvp-b-ai')) {
            msg = '💡 MVP-B AI 处于规划准备期，用例矩阵尚未建立';
          } else if (currentModuleFilter.startsWith('mvp-b') || currentModuleFilter.startsWith('P3')) {
            msg = '💡 MVP-B 当前处于需求契约准备阶段，测试用例矩阵待研发提测后生成';
          }
          showToast(msg);
        }
      });
    }

    // 抽屉底部飞书按钮拦截
    const drawerFeishuBtn = document.getElementById('drawer-feishu-btn');
    if (drawerFeishuBtn) {
      drawerFeishuBtn.addEventListener('click', function (e) {
        if (drawerFeishuBtn.classList.contains('is-disabled')) {
          e.preventDefault();
          showToast('💡 当前用例所属模块尚未录入飞书测试用例矩阵');
        }
      });
    }
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
        updateCasesActionButton();
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
  }

  function getModuleCasesUrl(modId) {
    if (!rawData) return null;
    if (modId === 'all') {
      return (rawData.feishu_links && rawData.feishu_links.cases_url) || null;
    }
    if (modId === 'mvp-a' || modId === 'P1' || modId === 'P2') {
      const mvpA = (rawData.modules || []).find(m => m.id === 'mvp-a');
      if (mvpA && mvpA.feishu_links && mvpA.feishu_links.cases_url) {
        return mvpA.feishu_links.cases_url;
      }
      return (rawData.feishu_links && rawData.feishu_links.cases_url) || null;
    }
    const targetMod = (rawData.modules || []).find(m => m.id === modId);
    if (targetMod && targetMod.feishu_links && targetMod.feishu_links.cases_url) {
      return targetMod.feishu_links.cases_url;
    }
    return null;
  }

  function updateCasesActionButton() {
    const btn = document.getElementById('sub-link-feishu-cases');
    if (!btn) return;

    if (currentModuleFilter === 'all') {
      const url = getModuleCasesUrl('all');
      btn.textContent = '查看全量基线用例表 (MVP-A) ↗';
      btn.href = url || 'javascript:void(0)';
      btn.classList.remove('is-disabled');
      btn.removeAttribute('data-disabled');
    } else if (currentModuleFilter === 'mvp-a' || currentModuleFilter === 'P1' || currentModuleFilter === 'P2') {
      const url = getModuleCasesUrl('mvp-a');
      btn.textContent = '在飞书查看完整矩阵 ↗';
      btn.href = url || 'javascript:void(0)';
      btn.classList.remove('is-disabled');
      btn.removeAttribute('data-disabled');
    } else {
      // mvp-b, mvp-b-ai, P3, etc.
      btn.textContent = '飞书用例表 (待生成) ⊘';
      btn.href = 'javascript:void(0)';
      btn.classList.add('is-disabled');
      btn.setAttribute('data-disabled', 'true');
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

      // In-Card Asset Bar (Scheme B: Decoupled from Header)
      const feishu = mod.feishu_links || {};
      let assetsHtml = '';

      if (mod.id === 'mvp-a') {
        const prdLink = feishu.prd_url
          ? `<a class="card-asset-pill" href="${escapeHtml(feishu.prd_url)}" target="_blank" rel="noopener noreferrer">📄 PRD v2.2 ↗</a>`
          : '';
        const casesLink = feishu.cases_url
          ? `<a class="card-asset-pill" href="${escapeHtml(feishu.cases_url)}" target="_blank" rel="noopener noreferrer">📊 47条用例全表 ↗</a>`
          : '';
        const reportLink = feishu.report_url
          ? `<a class="card-asset-pill" href="${escapeHtml(feishu.report_url)}" target="_blank" rel="noopener noreferrer">📑 RUN-008报告 ↗</a>`
          : '';
        assetsHtml = prdLink + casesLink + reportLink;
      } else if (mod.id === 'mvp-b') {
        const prdLink = feishu.prd_url
          ? `<a class="card-asset-pill" href="${escapeHtml(feishu.prd_url)}" target="_blank" rel="noopener noreferrer">📄 PRD初稿 ↗</a>`
          : `<span class="card-asset-pill is-disabled">📄 PRD初稿 (内部草稿)</span>`;
        const casesPlaceholder = `<span class="card-asset-pill is-disabled" data-toast="💡 MVP-B 当前处于需求契约准备阶段，测试用例矩阵待研发提测后生成">📊 用例矩阵 (待提测) ⊘</span>`;
        assetsHtml = prdLink + casesPlaceholder;
      } else if (mod.id === 'mvp-b-ai') {
        assetsHtml = `<span class="card-asset-pill is-disabled" data-toast="💡 MVP-B AI 处于规划准备期，用例矩阵尚未建立">💡 规划预研中</span>`;
      }

      if (assetsHtml) {
        const assetBar = document.createElement('div');
        assetBar.className = 'card-asset-bar';
        assetBar.innerHTML = `<span class="card-asset-label">🔗 核心资产:</span>` + assetsHtml;

        // 阻止向上冒泡触发卡片切换
        assetBar.querySelectorAll('.card-asset-pill').forEach(function (pill) {
          pill.addEventListener('click', function (e) {
            e.stopPropagation();
            const toastMsg = pill.getAttribute('data-toast');
            if (toastMsg) {
              e.preventDefault();
              showToast(toastMsg);
            }
          });
        });

        card.appendChild(assetBar);
      }

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
      updateCasesActionButton();
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
    updateCasesActionButton();
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

    // 抽屉内飞书按钮同步状态
    const drawerFeishuBtn = document.getElementById('drawer-feishu-btn');
    if (drawerFeishuBtn) {
      const modId = (item.branch || item.module || '').toLowerCase();
      let itemCasesUrl = (rawData && rawData.feishu_links && rawData.feishu_links.cases_url) || null;
      if (modId.startsWith('mvp-b') || modId.startsWith('p3')) {
        itemCasesUrl = null;
      }
      if (itemCasesUrl) {
        drawerFeishuBtn.href = itemCasesUrl;
        drawerFeishuBtn.classList.remove('is-disabled');
        drawerFeishuBtn.textContent = '飞书用例表直达 ↗';
      } else {
        drawerFeishuBtn.href = 'javascript:void(0)';
        drawerFeishuBtn.classList.add('is-disabled');
        drawerFeishuBtn.textContent = '飞书用例表 (待生成) ⊘';
      }
    }

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
