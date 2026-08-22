const syncPanel = document.querySelector(".sync-panel");
const syncStatus = document.querySelector("#sync-status");
const initialLastUpdated = document.body.dataset.lastUpdated || null;
const isPanelMode = document.body.dataset.dashboardMode === "read_only_local";

// Only the standalone panel may poll the sync clock.  Its /api/v1/project-status
// response is a server-approved lightweight projection ({project_name,
// last_updated}); the business app still returns full data there and must not
// be polled periodically.
async function checkForUpdates() {
  if (!syncPanel || !syncStatus) return;
  try {
    const response = await fetch("/api/v1/project-status", { cache: "no-store" });
    if (!response.ok) throw new Error("status request failed");
    const payload = await response.json();
    const lastUpdated = payload && payload.data && typeof payload.data.last_updated === "string"
      ? payload.data.last_updated
      : null;
    if (lastUpdated === null) throw new Error("sync projection invalid");

    syncPanel.classList.remove("is-error");
    syncStatus.textContent = "已连接";

    if (initialLastUpdated && lastUpdated !== initialLastUpdated) {
      syncStatus.textContent = "发现更新，正在刷新";
      window.location.reload();
    }
  } catch (error) {
    syncPanel.classList.add("is-error");
    syncStatus.textContent = "暂时无法同步";
  }
}

if (isPanelMode && syncPanel && syncStatus) {
  checkForUpdates();
  window.setInterval(checkForUpdates, 10000);
}

function dashboardElement(tag, className, text) {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (text !== undefined && text !== null) element.textContent = text;
  return element;
}

const sourceRoleLabels = {
  product: '产品负责人',
  development: '服务端技术负责人',
  frontend: '前端开发负责人',
  testing: '测试负责人',
};

const deliveryStateLabels = {
  planning: '规划中',
  contract_freeze: '契约待冻结',
  implementation: '实施中',
  integration: '联调中',
  independent_test: '独立测试中',
  product_acceptance: '产品验收中',
  ready_for_trial: '可试用',
  not_frozen: '待冻结',
  frozen: '已冻结',
  retest_required: '待复验',
  not_applicable: '不适用',
  not_fixed: '待固定',
  fixed: '已固定',
  superseded: '已替换',
  not_assessed: '待评估',
  evidence_ready: '证据已齐',
  open: '未解除',
  passed: '已通过',
  blocked: '有阻塞',
};

function sourceRoleLabel(sourceRole, displayLabel) {
  return displayLabel || sourceRoleLabels[sourceRole] || sourceRole || '待核对';
}

function deliveryStateLabel(status) {
  return deliveryStateLabels[status] || status || '待核对';
}

function addDeliveryState(parent, title, state) {
  const card = dashboardElement('article', 'delivery-state-card');
  card.append(dashboardElement('h4', '', title));
  card.append(dashboardElement('p', 'delivery-state-value', deliveryStateLabel(state?.status)));
  card.append(dashboardElement('p', 'delivery-state-summary', state?.safe_summary || '未提供'));
  parent.append(card);
}

function appendDeliveryScope(parent, title, items) {
  const section = dashboardElement('section', 'delivery-scope');
  const list = dashboardElement('ul');
  section.append(dashboardElement('h4', '', title));
  (Array.isArray(items) ? items : []).forEach((item) => {
    list.append(dashboardElement('li', '', item.label || '未提供'));
  });
  if (!list.children.length) list.append(dashboardElement('li', '', '未提供'));
  section.append(list);
  parent.append(section);
}

function safeEvidenceHref(lineId, evidenceId) {
  return `/api/v1/project-status/dashboard/delivery-lines/${encodeURIComponent(lineId)}/evidence/${encodeURIComponent(evidenceId)}`;
}

function appendDeliveryDetails(article, line) {
  const details = dashboardElement('details', 'delivery-details');
  const summary = dashboardElement('summary', '', '查看门槛、证据与后置范围');
  const content = dashboardElement('div', 'delivery-detail-content');
  const states = dashboardElement('div', 'delivery-state-grid');
  addDeliveryState(states, '字段级契约', line.contract_state);
  addDeliveryState(states, '组合候选', line.candidate_version);
  addDeliveryState(states, '运行门槛', line.runtime_gate);
  content.append(states);

  const scopes = dashboardElement('div', 'delivery-scope-grid');
  appendDeliveryScope(scopes, '明确后置', line.scope_out);
  content.append(scopes);

  const evidence = dashboardElement('section', 'delivery-evidence');
  const evidenceList = dashboardElement('ul');
  evidence.append(dashboardElement('h4', '', '已核对证据'));
  (Array.isArray(line.evidence_links) ? line.evidence_links : []).forEach((item) => {
    const node = dashboardElement('li');
    const allowedHref = safeEvidenceHref(line.id, item.id);
    if (typeof item.href === 'string' && item.href === allowedHref) {
      const link = dashboardElement('a', '', item.label || '安全证据');
      link.href = allowedHref;
      link.dataset.deliveryEvidence = item.id || '';
      node.append(link);
    } else {
      node.append(dashboardElement('strong', 'evidence-label-blocked', item.label || '安全证据'));
      node.append(dashboardElement('p', 'evidence-link-degraded', '证据链接不可用：未通过安全白名单校验。'));
    }
    node.append(dashboardElement('span', 'evidence-level', item.display_label || '待核对'));
    node.append(dashboardElement('p', '', item.safe_summary || '未提供'));
    node.append(dashboardElement('small', '', `来源角色：${sourceRoleLabel(item.source_role, item.source_role_label)} · 核对：${item.checked_at || '未提供'}`));
    evidenceList.append(node);
  });
  if (!evidenceList.children.length) evidenceList.append(dashboardElement('li', '', '证据缺失／待核对'));
  evidence.append(evidenceList); content.append(evidence);

  const blockers = dashboardElement('section', 'delivery-blockers');
  const blockerList = dashboardElement('ol');
  blockers.append(dashboardElement('h4', '', '全部开放门禁'));
  (Array.isArray(line.open_blockers) ? line.open_blockers : []).forEach((item) => {
    const node = dashboardElement('li');
    node.append(dashboardElement('strong', '', item.title || item.id || '待核对门禁'));
    node.append(dashboardElement('p', '', item.next_action || '最小解除条件未提供'));
    node.append(dashboardElement('small', '', `状态：${deliveryStateLabel(item.status)} · 更新：${item.updated_at || '未提供'}`));
    blockerList.append(node);
  });
  if (!blockerList.children.length) blockerList.append(dashboardElement('li', '', '当前未登记开放门禁；需继续核对。'));
  blockers.append(blockerList); content.append(blockers);
  details.append(summary, content);
  article.append(details);
}

function renderDeliveryDashboard(view) {
  const target = document.querySelector('[data-delivery-lines-content]');
  const lines = Array.isArray(view?.delivery_lines) ? view.delivery_lines : [];
  if (!target) return;
  target.replaceChildren();
  target.setAttribute('aria-busy', 'false');
  if (!lines.length) {
    target.append(dashboardElement('p', 'delivery-empty', '暂无经过核对的产品交付线。'));
    return;
  }
  const grid = dashboardElement('div', 'delivery-module-grid');
  lines.forEach((line) => {
    const article = dashboardElement('article', 'delivery-line-card delivery-module-card');
    article.id = `delivery-line-${line.id}`;
    const heading = dashboardElement('header', 'delivery-line-heading');
    const title = dashboardElement('div');
    title.append(dashboardElement('span', 'delivery-level', line.display_label || '等级待核对'));
    title.append(dashboardElement('h3', '', line.name || '未命名交付线'));
    const timeLabel = line.verified_at
      ? `最近核对：${line.verified_at}`
      : `更新时间：${line.updated_at || '待核对'}`;
    const deliveryStatus = dashboardElement('span', 'delivery-status-pill', deliveryStateLabel(line.delivery_status));
    heading.append(title, deliveryStatus);
    article.append(heading, dashboardElement('p', 'delivery-summary', line.summary || '未提供'));

    const firstBlocker = Array.isArray(line.open_blockers) ? line.open_blockers[0] : null;
    const overview = dashboardElement('dl', 'delivery-overview');
    [
      ['当前门禁', firstBlocker?.title || '待核对'],
      ['下一步', firstBlocker?.next_action || '暂无待办'],
      ['最近核对', `${timeLabel.replace(/^(最近核对|更新时间)：/, '')} · ${sourceRoleLabel(line.source_role, line.source_role_label)}`],
    ].forEach(([label, value]) => {
      const item = dashboardElement('div');
      item.append(dashboardElement('dt', '', label), dashboardElement('dd', '', value));
      overview.append(item);
    });
    article.append(overview);

    const scopeChips = dashboardElement('div', 'delivery-scope-chips');
    scopeChips.setAttribute('aria-label', '本次包含范围');
    scopeChips.append(dashboardElement('span', '', '本次包含'));
    (Array.isArray(line.scope_in) ? line.scope_in : []).forEach((item) => scopeChips.append(dashboardElement('em', '', item.id || '待核对')));
    if (scopeChips.children.length === 1) scopeChips.append(dashboardElement('em', '', '待核对'));
    article.append(scopeChips);
    appendDeliveryDetails(article, line);
    grid.append(article);
  });
  target.append(grid);
}

function renderDeliveryDashboardError(target) {
  const errorMessage = dashboardElement(
    'p',
    'delivery-load-error-message',
    '交付线证据未加载：当前未显示任何交付状态。请确认安全看板服务可用后重试。',
  );
  // role=alert belongs on the non-interactive message so the retry button
  // stays focusable and is announced separately.
  errorMessage.setAttribute('role', 'alert');
  const retryButton = dashboardElement('button', 'delivery-retry', '重新加载交付线');
  retryButton.type = 'button';
  retryButton.addEventListener('click', () => loadDeliveryDashboard());

  const errorPanel = dashboardElement('div', 'delivery-load-error');
  errorPanel.setAttribute('aria-live', 'assertive');
  errorPanel.append(errorMessage, retryButton);
  target.replaceChildren(errorPanel);
}

async function loadDeliveryDashboard() {
  if (!document.querySelector('[data-delivery-lines-content]')) return;
  const target = document.querySelector('[data-delivery-lines-content]');
  if (target) target.setAttribute('aria-busy', 'true');
  try {
    const response = await fetch('/api/v1/project-status/dashboard', { cache: 'no-store' });
    if (!response.ok) throw new Error('delivery dashboard request failed');
    renderDeliveryDashboard((await response.json()).data);
  } catch (error) {
    if (!target) return;
    renderDeliveryDashboardError(target);
    target.setAttribute('aria-busy', 'false');
  }
}

loadDeliveryDashboard();

const safeWorkspaceRoutes = {
  collaboration: '/project-status/workspaces',
  development: '/project-status/workspaces/development',
  frontend: '/project-status/workspaces/frontend',
  testing: '/project-status/workspaces/testing',
};

function safeWorkspaceEvidenceHref(href) {
  return typeof href === 'string'
    && /^\/api\/v1\/project-status\/dashboard\/delivery-lines\/[A-Za-z0-9_.-]+\/evidence\/[A-Za-z0-9_.-]+$/.test(href)
    ? href
    : '';
}

function workspaceValue(value, fallback = '待核对') {
  return typeof value === 'string' && value.trim() ? value : fallback;
}

function workspaceWarningList(warnings) {
  if (!Array.isArray(warnings) || !warnings.length) return null;
  const alert = dashboardElement('section', 'safe-workspace-alert');
  alert.setAttribute('role', 'alert');
  alert.append(dashboardElement('strong', '', '工作区数据待核对'));
  const list = dashboardElement('ul');
  warnings.forEach((warning) => list.append(dashboardElement('li', '', workspaceValue(warning, '安全数据源返回了未说明的提示。'))));
  alert.append(list);
  return alert;
}

function workspaceMeta(label, value) {
  const row = dashboardElement('div');
  row.append(dashboardElement('dt', '', label), dashboardElement('dd', '', value));
  return row;
}

function workspaceCompletedItems(workspace) {
  return Array.isArray(workspace?.completed_items) && workspace.completed_items.length
    ? workspace.completed_items
    : null;
}

function workspaceCompletedSummary(workspace) {
  const items = workspaceCompletedItems(workspace);
  return items ? `${items.length} 项` : '待核对';
}

function workspaceOverviewCard(workspace) {
  const route = safeWorkspaceRoutes[workspace?.id];
  if (!route) return null;
  const card = dashboardElement('article', 'safe-workspace-card');
  const heading = dashboardElement('div', 'safe-workspace-card-heading');
  const title = dashboardElement('h3', '', workspaceValue(workspace.display_label, '工作区待核对'));
  const status = dashboardElement('span', 'safe-workspace-status', workspaceValue(workspace.status_label));
  heading.append(title, status);
  card.append(heading);
  card.append(dashboardElement('p', 'safe-workspace-owner', `负责人：${workspaceValue(workspace.owner_role_label)}`));
  card.append(dashboardElement('p', 'safe-workspace-current', workspaceValue(workspace.current, '当前工作待核对。')));
  const meta = dashboardElement('dl', 'safe-workspace-meta');
  meta.append(
    workspaceMeta('已完成', workspaceCompletedSummary(workspace)),
    workspaceMeta('下一步', workspaceValue(workspace.next, '待核对')),
    workspaceMeta('核对时间', workspaceValue(workspace.checked_at || workspace.updated_at)),
  );
  card.append(meta);
  const link = dashboardElement('a', 'safe-workspace-link', `查看${workspaceValue(workspace.display_label, '工作区')} →`);
  link.href = route;
  card.append(link);
  return card;
}

function renderSafeWorkspaceOverview(view) {
  const target = document.querySelector('[data-safe-workspace-overview]');
  if (!target) return;
  const workspaces = Array.isArray(view?.workspaces) ? view.workspaces : [];
  target.replaceChildren();
  target.setAttribute('aria-busy', 'false');
  const warnings = workspaceWarningList(view?.warnings);
  if (warnings) target.append(warnings);
  if (!workspaces.length) {
    target.append(dashboardElement('p', 'safe-workspace-empty', '当前未显示任何工作区状态。请确认安全数据源可用后刷新页面。'));
    return;
  }
  const grid = dashboardElement('div', 'safe-workspace-grid');
  workspaces.forEach((workspace) => {
    const card = workspaceOverviewCard(workspace);
    if (card) grid.append(card);
  });
  if (!grid.children.length) {
    target.append(dashboardElement('p', 'safe-workspace-empty', '当前未显示任何可识别的工作区状态。'));
    return;
  }
  target.append(grid);
}

function appendWorkspaceEvidence(parent, evidenceLinks) {
  const section = dashboardElement('section', 'safe-workspace-evidence');
  section.append(dashboardElement('h3', '', '已核对证据'));
  const list = dashboardElement('ul');
  (Array.isArray(evidenceLinks) ? evidenceLinks : []).forEach((item) => {
    const row = dashboardElement('li');
    const href = safeWorkspaceEvidenceHref(item?.href);
    if (href) {
      const link = dashboardElement('a', '', workspaceValue(item?.label, '安全证据'));
      link.href = href;
      row.append(link);
    } else {
      row.append(dashboardElement('strong', '', workspaceValue(item?.label, '安全证据待核对')));
      row.append(dashboardElement('p', 'safe-workspace-link-warning', '证据链接未通过安全白名单校验，已停用。'));
    }
    row.append(dashboardElement('p', '', workspaceValue(item?.safe_summary, '未提供安全摘要。')));
    row.append(dashboardElement('small', '', `来源角色：${workspaceValue(item?.source_role_label)} · 核对：${workspaceValue(item?.checked_at || item?.verified_at)}`));
    list.append(row);
  });
  if (!list.children.length) list.append(dashboardElement('li', '', '暂无已核对证据；待继续核对。'));
  section.append(list);
  parent.append(section);
}

function appendWorkspaceBlockers(parent, blockers) {
  const section = dashboardElement('section', 'safe-workspace-blockers');
  section.append(dashboardElement('h3', '', '开放门禁'));
  const list = dashboardElement('ol');
  (Array.isArray(blockers) ? blockers : []).forEach((item) => {
    const row = dashboardElement('li');
    row.append(dashboardElement('strong', '', workspaceValue(item?.title, '门禁待核对')));
    row.append(dashboardElement('p', '', workspaceValue(item?.next_action, '最小解除条件待核对。')));
    row.append(dashboardElement('small', '', `状态：${deliveryStateLabel(item?.status)} · 更新：${workspaceValue(item?.updated_at)}`));
    list.append(row);
  });
  if (!list.children.length) list.append(dashboardElement('li', '', '当前未登记开放门禁；仍需继续核对。'));
  section.append(list);
  parent.append(section);
}

function appendWorkspaceCompleted(parent, workspace) {
  const section = dashboardElement('section', 'safe-workspace-phase safe-workspace-completed');
  section.append(dashboardElement('h3', '', '已完成'));
  const items = workspaceCompletedItems(workspace);
  if (!items) {
    section.append(dashboardElement('p', 'safe-workspace-phase-empty', '暂无经核对的已完成项，待核对。'));
    parent.append(section);
    return;
  }
  const list = dashboardElement('ul', 'safe-workspace-completed-list');
  items.forEach((item) => {
    const row = dashboardElement('li');
    row.append(dashboardElement('strong', '', workspaceValue(item?.label, '已完成项待核对')));
    row.append(dashboardElement('small', '', `核对：${workspaceValue(item?.checked_at)} · 来源角色：${workspaceValue(item?.source_role_label)}`));
    list.append(row);
  });
  section.append(list);
  parent.append(section);
}

function appendWorkspaceCurrentAndNext(parent, workspace) {
  [
    ['进行中', workspaceValue(workspace.current, '当前工作待核对。')],
    ['后续计划', workspaceValue(workspace.next, '后续计划待核对。')],
  ].forEach(([title, content]) => {
    const section = dashboardElement('section', 'safe-workspace-phase');
    section.append(dashboardElement('h3', '', title), dashboardElement('p', '', content));
    parent.append(section);
  });
}

function renderSafeWorkspaceDetail(view, workspaceId) {
  const target = document.querySelector('[data-safe-workspace-detail]');
  if (!target) return;
  const workspaces = Array.isArray(view?.workspaces) ? view.workspaces : [];
  const workspace = workspaces.find((item) => item?.id === workspaceId);
  target.replaceChildren();
  target.setAttribute('aria-busy', 'false');
  const warnings = workspaceWarningList(view?.warnings);
  if (warnings) target.append(warnings);
  if (!workspace) {
    const message = dashboardElement('p', 'safe-workspace-empty', '当前未显示该工作区状态。请确认安全数据源可用后刷新页面。');
    message.setAttribute('role', 'alert');
    target.append(message);
    return;
  }
  const header = dashboardElement('header', 'safe-workspace-detail-heading');
  header.append(
    dashboardElement('h3', '', workspaceValue(workspace.display_label, '工作区待核对')),
    dashboardElement('span', 'safe-workspace-status', workspaceValue(workspace.status_label)),
  );
  target.append(header, dashboardElement('p', 'safe-workspace-owner', `负责人：${workspaceValue(workspace.owner_role_label)}`));

  const phases = dashboardElement('div', 'safe-workspace-phase-grid');
  appendWorkspaceCompleted(phases, workspace);
  appendWorkspaceCurrentAndNext(phases, workspace);
  target.append(phases);

  const metadata = dashboardElement('dl', 'safe-workspace-activity');
  metadata.append(
    workspaceMeta('关联交付线', Array.isArray(workspace.delivery_line_refs) && workspace.delivery_line_refs.length ? workspace.delivery_line_refs.join(' · ') : '待核对'),
    workspaceMeta('最近核对', workspaceValue(workspace.checked_at || workspace.updated_at)),
  );
  target.append(metadata);

  const detailGrid = dashboardElement('div', 'safe-workspace-detail-grid');
  appendWorkspaceBlockers(detailGrid, workspace.open_blockers);
  appendWorkspaceEvidence(detailGrid, workspace.evidence_links);
  target.append(detailGrid);
}

function renderSafeWorkspaceError(target) {
  const message = dashboardElement('p', 'safe-workspace-empty', '工作区安全摘要未加载：当前未显示任何工作区状态。请确认安全看板服务可用后重试。');
  message.setAttribute('role', 'alert');
  const retry = dashboardElement('button', 'safe-workspace-retry', '重新加载工作区');
  retry.type = 'button';
  retry.addEventListener('click', () => loadSafeWorkspaces());
  const panel = dashboardElement('div', 'safe-workspace-error');
  panel.append(message, retry);
  target.replaceChildren(panel);
  target.setAttribute('aria-busy', 'false');
}

async function loadSafeWorkspaces() {
  const overview = document.querySelector('[data-safe-workspace-overview]');
  const detail = document.querySelector('[data-safe-workspace-detail]');
  if (!overview && !detail) return;
  const target = overview || detail;
  target.setAttribute('aria-busy', 'true');
  try {
    const response = await fetch('/api/v1/project-status/dashboard/workspaces', { cache: 'no-store' });
    if (!response.ok) throw new Error('workspace dashboard request failed');
    const payload = await response.json();
    if (!payload?.success || !payload?.data || !Array.isArray(payload.data.workspaces)) {
      throw new Error('workspace dashboard projection invalid');
    }
    if (overview) renderSafeWorkspaceOverview(payload.data);
    if (detail) renderSafeWorkspaceDetail(payload.data, detail.dataset.safeWorkspaceDetail);
  } catch (error) {
    renderSafeWorkspaceError(target);
  }
}

loadSafeWorkspaces();

document.querySelectorAll('[data-release-expand]').forEach((button) => {
  button.addEventListener('click', () => {
    const details = button.closest('.release-identity');
    const shortCommit = details?.querySelector('[data-release-commit-short]');
    const fullCommit = details?.querySelector('[data-release-commit-full]');
    const isExpanded = button.getAttribute('aria-expanded') === 'true';
    button.setAttribute('aria-expanded', String(!isExpanded));
    button.textContent = isExpanded ? '展开' : '收起';
    if (shortCommit) shortCommit.hidden = !isExpanded;
    if (fullCommit) fullCommit.hidden = isExpanded;
  });
});

document.querySelectorAll('[data-release-copy]').forEach((button) => {
  button.addEventListener('click', async () => {
    const text = button.dataset.copyText;
    if (!text) return;
    try {
      await navigator.clipboard.writeText(text);
      button.textContent = '已复制';
    } catch (error) {
      button.textContent = '复制失败';
    }
    window.setTimeout(() => { button.textContent = '复制'; }, 1600);
  });
});

function automationElement(tag, className, text) {
  return dashboardElement(tag, className, text);
}

function automationError(target, message) {
  const panel = automationElement('div', 'automation-load-error');
  panel.setAttribute('role', 'alert');
  panel.append(automationElement('strong', '', '辅助自动化摘要未加载'), automationElement('p', '', message));
  target.replaceChildren(panel);
  target.setAttribute('aria-busy', 'false');
}

function automationSafeHref(href) {
  return typeof href === 'string' && href.startsWith('/api/v1/project-status/test-automation/runs/')
    ? href
    : '';
}

function automationTimestamp(value) {
  return value || '待测试负责人补录';
}

function automationStatus(run) {
  return run?.automation_status_label || '状态待核对';
}

function renderAutomationEntry(view) {
  const target = document.querySelector('[data-test-automation-entry]');
  if (!target) return;
  const runs = Array.isArray(view?.runs) ? view.runs : [];
  const latest = runs[0];
  const values = [
    ['已评估正式 Case', runs.length],
    ['待审核计划', runs.filter((run) => run.review_status === 'pending_testing_review').length],
    ['最近辅助运行', latest?.run_id || '未提供'],
    ['最近断言', latest ? `${latest.assertion_total} 项 · ${latest.assertion_failed} 项失败` : '未提供'],
    ['人工项待验收', latest?.manual_items_count ?? '待核对'],
  ];
  const list = automationElement('dl', 'automation-entry-metrics');
  values.forEach(([label, value]) => {
    const item = automationElement('div');
    item.append(automationElement('dt', '', label), automationElement('dd', '', value));
    list.append(item);
  });
  target.replaceChildren(list);
  target.setAttribute('aria-busy', 'false');
}

function appendAutomationWarnings(target, warnings) {
  if (!Array.isArray(warnings) || !warnings.length) return;
  const alert = automationElement('section', 'automation-load-error');
  alert.setAttribute('role', 'alert');
  alert.append(automationElement('strong', '', '辅助自动化数据待核对'));
  warnings.forEach((warning) => alert.append(automationElement('p', '', warning)));
  target.append(alert);
}

function renderAutomationRuns(view) {
  const target = document.querySelector('[data-test-automation-content]');
  if (!target) return;
  const runs = Array.isArray(view?.runs) ? view.runs : [];
  target.replaceChildren();
  target.setAttribute('aria-busy', 'false');
  appendAutomationWarnings(target, view?.warnings);
  if (!runs.length) {
    target.append(automationElement('p', 'delivery-empty', '暂无可安全展示的辅助自动化摘要。'));
    return;
  }
  const list = automationElement('div', 'automation-case-list');
  runs.forEach((run) => {
    const article = automationElement('article', 'automation-case-row');
    const caseInfo = automationElement('div', 'automation-case-info');
    caseInfo.append(automationElement('strong', '', run.source_case_id || '正式 Case 待核对'));
    caseInfo.append(automationElement('span', '', `Case 版本：${run.case_version || '未提供'}`));
    const state = automationElement('div', 'automation-case-state');
    state.append(automationElement('span', 'automation-status', automationStatus(run)));
    state.append(automationElement('small', '', `最近运行：${automationTimestamp(run.executed_at)}`));
    const manual = automationElement('div', 'automation-case-manual');
    manual.append(automationElement('strong', '', '人工保留项'), automationElement('span', '', `${run.manual_items_count ?? '待核对'} 项待验收`));
    const action = automationElement('div', 'automation-case-actions');
    const link = automationElement('a', 'detail-link', '查看辅助运行 →');
    link.href = `/project-status/tests/automation/runs/${encodeURIComponent(run.run_id || '')}`;
    link.dataset.testid = 'test-automation-run-link';
    action.append(link);
    article.append(caseInfo, state, manual, action);
    list.append(article);
  });
  target.append(list);
}

function renderAutomationRun(run) {
  const target = document.querySelector('[data-test-automation-run-id]');
  if (!target) return;
  target.replaceChildren();
  target.setAttribute('aria-busy', 'false');
  const overview = automationElement('section', 'automation-run-overview');
  const meta = automationElement('dl', 'automation-run-meta');
  [
    ['正式 Case', `${run?.source_case_id || '未提供'} · v${run?.case_version || '未提供'}`],
    ['工具提交', run?.tool_commit || '未提供'],
    ['被测提交', run?.tested_project_commit || '未提供'],
    ['执行时间', automationTimestamp(run?.executed_at)],
  ].forEach(([label, value]) => {
    const row = automationElement('div');
    row.append(automationElement('dt', '', label), automationElement('dd', '', value));
    meta.append(row);
  });
  overview.append(meta, automationElement('p', 'automation-run-summary', run?.governance_statement || '状态待核对'));
  overview.append(automationElement('span', 'automation-status', automationStatus(run)));
  target.append(overview);

  const assertion = automationElement('section', 'section-block automation-assertions');
  assertion.append(automationElement('h2', '', '辅助断言与人工项'));
  const result = automationElement('div', 'automation-assertion-summary');
  result.append(
    automationElement('strong', '', `${run?.assertion_total ?? '待核对'} 项断言`),
    automationElement('span', '', `${run?.assertion_failed ?? '待核对'} 项失败`),
    automationElement('span', '', `${run?.manual_items_count ?? '待核对'} 项人工确认`),
  );
  assertion.append(result, automationElement('p', 'muted-copy', '逐项原始断言、报告和截图不在质量面板展示；测试负责人仍需独立复核。'));
  target.append(assertion);

  const closure = automationElement('section', 'automation-closure-grid');
  [
    ['隔离清理', run?.cleanup_status_label || '待核对'],
    ['测试负责人复核', run?.review_status_label || '待核对'],
  ].forEach(([title, status]) => {
    const item = automationElement('article', 'automation-closure-item');
    item.append(automationElement('h2', '', title), automationElement('strong', '', status));
    closure.append(item);
  });
  target.append(closure);

  const evidence = Array.isArray(run?.evidence_links) ? run.evidence_links : [];
  const links = evidence.map((item) => ({ label: item?.label || '受控辅助自动化摘要', href: automationSafeHref(item?.href), summary: item?.safe_summary || '' })).filter((item) => item.href);
  if (links.length) {
    const section = automationElement('section', 'section-block automation-safe-evidence');
    section.append(automationElement('h2', '', '安全证据入口'));
    const list = automationElement('ul', 'case-design-links');
    links.forEach((item) => {
      const row = automationElement('li');
      const link = automationElement('a', '', item.label);
      link.href = item.href;
      row.append(link, automationElement('small', '', item.summary));
      list.append(row);
    });
    section.append(list);
    target.append(section);
  }
}

async function loadTestAutomation() {
  const entry = document.querySelector('[data-test-automation-entry]');
  const content = document.querySelector('[data-test-automation-content]');
  const runTarget = document.querySelector('[data-test-automation-run-id]');
  if (!entry && !content && !runTarget) return;
  const runId = runTarget?.dataset.testAutomationRunId;
  const endpoint = runId
    ? `/api/v1/project-status/test-automation/runs/${encodeURIComponent(runId)}`
    : '/api/v1/project-status/test-automation';
  try {
    const response = await fetch(endpoint, { cache: 'no-store' });
    if (!response.ok) throw new Error('test automation request failed');
    const view = (await response.json()).data;
    if (runTarget) renderAutomationRun(view);
    else {
      renderAutomationEntry(view);
      renderAutomationRuns(view);
    }
  } catch (error) {
    [entry, content, runTarget].filter(Boolean).forEach((target) => automationError(target, '当前未显示任何辅助自动化状态。请确认受控接口可用后刷新页面。'));
  }
}

loadTestAutomation();

// Document reading pages render server-side canonical links; this guard enforces
// the same policy for anything the server missed (raw relative paths, file: or
// other schemes).  Unapproved links degrade to plain text, never to a clickable
// filesystem-relative target.
function guardDocumentLinks() {
  const body = document.querySelector('.markdown-body[data-document-link-guard]');
  if (!body) return;
  body.querySelectorAll('a[href]').forEach((link) => {
    const href = link.getAttribute('href') || '';
    const isAllowed = /^\/project-status\/documents\/[A-Za-z0-9]+(?:#.*)?$/.test(href)
      || href.startsWith('#')
      || /^(https?:|mailto:)/i.test(href);
    if (isAllowed) return;
    const replacement = document.createElement('span');
    replacement.className = 'doc-link-missing';
    replacement.title = '目标链接未通过站内文档安全校验，已停用';
    replacement.textContent = link.textContent;
    link.replaceWith(replacement);
  });
}

guardDocumentLinks();
