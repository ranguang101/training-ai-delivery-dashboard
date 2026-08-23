// R4 质量生命周期页面：只消费受控结构化投影，不读取原始测试资产。
(function () {
  'use strict';

  const root = document.querySelector('[data-quality-requirements]');
  if (!root) return;

  const copy = {
    loadingFailure: '暂时无法加载质量追踪信息，请稍后重试',
    noCases: '尚未登记正式 Case',
    noAutomation: '尚未配置辅助自动化',
    noDefects: '当前无关联缺陷',
    noReport: '尚未形成最终测试报告，当前不可进入产品验收',
    missing: '待补录',
  };
  const executionLabels = {
    not_executed: '未执行', passed: '通过', failed: '失败', blocked: '阻塞', not_applicable: '不适用',
  };
  const detailRequirement = root.dataset.qualityRequirementId || null;

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function safeText(value, fallback = copy.missing) {
    return typeof value === 'string' && value.trim() ? value : fallback;
  }

  function readQuery() {
    const search = new URLSearchParams(window.location.search);
    return {
      requirement: detailRequirement || search.get('requirement'),
      line: search.get('line'),
      from: search.get('from'),
      anchor: window.location.hash,
    };
  }

  function overviewHref(requirement, line) {
    const url = new URL('/project-status/tests/requirements', window.location.origin);
    if (requirement) url.searchParams.set('requirement', requirement);
    if (line) url.searchParams.set('line', line);
    return url.pathname + url.search;
  }

  function detailHref(requirement, line, section) {
    const url = new URL(`/project-status/tests/requirements/${encodeURIComponent(requirement)}`, window.location.origin);
    if (line) url.searchParams.set('line', line);
    url.searchParams.set('from', 'requirement-overview');
    url.hash = section;
    return url.pathname + url.search + url.hash;
  }

  function warning(messages) {
    const block = el('div', 'safe-workspace-alert qw-alert');
    block.setAttribute('role', 'alert');
    block.append(el('strong', '', '请注意'));
    const list = el('ul');
    messages.forEach((message) => list.append(el('li', '', message)));
    block.append(list);
    return block;
  }

  function pill(text, tone) {
    return el('span', `r3-status-pill qw-status-${tone || 'neutral'}`, text);
  }

  function metric(label, value) {
    const item = el('div', 'qw-metric');
    item.append(el('strong', '', String(value)), el('span', '', label));
    return item;
  }

  function card(title, detail, body, href, disabled = false) {
    const section = el('section', 'qw-card');
    section.append(el('h3', '', title), body);
    if (detail) {
      const link = el(disabled ? 'span' : 'a', 'qw-card-link', detail);
      if (disabled) link.setAttribute('aria-disabled', 'true');
      else link.href = href;
      section.append(link);
    }
    return section;
  }

  function requirementTabs(data, selected) {
    const nav = el('nav', 'qw-tabs');
    nav.setAttribute('aria-label', '质量需求');
    (Array.isArray(data.requirements) ? data.requirements : []).forEach((item) => {
      const link = el('a', item.quality_requirement_id === selected ? 'is-active' : '', safeText(item.name));
      link.href = overviewHref(item.quality_requirement_id, item.delivery_line_id);
      link.dataset.testid = `quality-requirement-${item.quality_requirement_id}`;
      nav.append(link);
    });
    return nav;
  }

  function readinessSummary(selected) {
    const panel = el('section', 'qw-readiness');
    panel.append(el('h3', '', safeText(selected.name)));
    const row = el('div', 'qw-readiness-row');
    row.append(
      pill(safeText(selected.status_label), selected.status),
      el('span', '', selected.can_enter_product_acceptance ? '具备进入产品验收前提' : '当前不可进入产品验收'),
    );
    panel.append(row, el('p', '', safeText(selected.readiness_summary)));
    return panel;
  }

  function overviewCards(data, selected) {
    const line = selected.delivery_line_id;
    const requirement = selected.quality_requirement_id;
    const cases = data.cards.formal_cases || {};
    const caseBody = el('div', 'qw-card-content');
    const caseMetrics = el('div', 'qw-metrics');
    caseMetrics.append(
      metric('正式 Case', cases.total || 0), metric('已执行', cases.executed || 0),
      metric('通过', cases.passed || 0), metric('失败/阻塞', `${cases.failed || 0}/${cases.blocked || 0}`),
    );
    caseBody.append(caseMetrics, el('p', 'qw-card-note', `自动化 ${cases.automated || 0} · 人工 ${cases.manual || 0} · 最近：${executionLabels[cases.latest_execution_status] || copy.missing}`));

    const automation = data.cards.assisted_automation || {};
    const automationBody = el('div', 'qw-card-content');
    const automationMetrics = el('div', 'qw-metrics');
    automationMetrics.append(
      metric('可自动化', automation.automatable_count || 0), metric('待人工确认', automation.passed_pending_human || 0),
      metric('失败', automation.failed || 0), metric('已确认', automation.reviewed || 0),
    );
    automationBody.append(automationMetrics, el('p', 'qw-card-boundary', '辅助自动化，不等于正式准出'));

    const defects = data.cards.defects || {};
    const defectBody = el('div', 'qw-card-content');
    const defectMetrics = el('div', 'qw-metrics');
    defectMetrics.append(
      metric('关联缺陷', defects.total || 0), metric('Open', defects.open || 0),
      metric('待复测', defects.ready_for_retest || 0), metric('已关闭', defects.closed || 0),
    );
    defectBody.append(defectMetrics, el('p', 'qw-card-note', defects.has_open_high_priority ? `当前最高未关闭级别：${safeText(defects.highest_open_severity)}` : '当前无未关闭高优先级缺陷'));

    const report = data.cards.final_report || {};
    const reportBody = el('div', 'qw-card-content');
    reportBody.append(
      el('p', 'qw-report-id', safeText(report.report_id, copy.noReport)),
      el('p', 'qw-card-note', safeText(report.scope_summary, copy.noReport)),
      pill(safeText(report.report_status_label), report.report_status),
      el('p', 'qw-card-note', safeText(report.safe_summary, copy.noReport)),
    );

    const grid = el('div', 'qw-card-grid');
    grid.append(
      card('正式测试 Case', '查看 Case 列表', caseBody, detailHref(requirement, line, 'cases')),
      card('辅助自动化', '查看辅助运行', automationBody, detailHref(requirement, line, 'automation')),
      card('Jira / 缺陷', '查看关联缺陷', defectBody, detailHref(requirement, line, 'defects')),
      card('最终测试报告', report.report_id ? '查看测试报告' : '尚无最终报告', reportBody, detailHref(requirement, line, 'reports'), !report.report_id),
    );
    return grid;
  }

  function filterControls(label, options, onChange) {
    const wrap = el('label', 'qw-filter');
    wrap.append(el('span', '', label));
    const select = el('select');
    options.forEach(([value, text]) => {
      const option = el('option', '', text);
      option.value = value;
      select.append(option);
    });
    select.addEventListener('change', () => onChange(select.value));
    wrap.append(select);
    return wrap;
  }

  function detailList(title, section, items, render, emptyText, filters) {
    const block = el('section', 'qw-detail-section');
    block.id = section;
    block.append(el('h3', '', title));
    const list = el('div', 'qw-detail-list');
    const renderItems = (predicate) => {
      list.replaceChildren();
      const current = items.filter(predicate || (() => true));
      if (!current.length) list.append(el('p', 'r3-empty', emptyText));
      else current.forEach((item) => list.append(render(item)));
    };
    if (filters) block.append(filters(renderItems));
    renderItems();
    block.append(list);
    return block;
  }

  function caseItem(item) {
    const node = el('article', 'qw-detail-item');
    node.append(
      el('h4', '', `${safeText(item.case_id)} · ${safeText(item.title)}`),
      pill(safeText(item.latest_execution && item.latest_execution.execution_status_label, '未执行'), item.latest_execution && item.latest_execution.execution_status),
      el('p', '', `前置：${safeText(item.preconditions)}`),
      el('p', '', `步骤：${safeText(item.steps)}`),
      el('p', '', `预期：${safeText(item.expected_result)}`),
    );
    return node;
  }

  function automationItem(item) {
    const node = el('article', 'qw-detail-item');
    node.append(
      el('h4', '', safeText(item.automation_run_id)),
      pill(safeText(item.automation_status_label), item.automation_status),
      el('p', '', `断言：${item.assertion_total || 0} 项，失败 ${item.assertion_failed || 0} 项。`),
      el('p', '', safeText(item.safe_summary)),
      el('p', 'qw-card-boundary', '辅助自动化，不等于正式准出'),
    );
    return node;
  }

  function defectItem(item) {
    const node = el('article', 'qw-detail-item');
    node.append(
      el('h4', '', `${safeText(item.defect_id)}${item.jira_issue_key ? ` · ${item.jira_issue_key}` : ''}`),
      pill(safeText(item.status_label), item.is_open ? 'blocked' : 'verified'),
      el('p', '', `严重程度：${safeText(item.severity)} · 复测：${safeText(item.retest_status)}`),
      el('p', '', safeText(item.safe_summary)),
    );
    return node;
  }

  function reportItem(item) {
    const node = el('article', 'qw-detail-item');
    node.append(
      el('h4', '', safeText(item.report_id)),
      pill(safeText(item.report_status_label), item.report_status),
      el('p', '', `候选：${safeText(item.candidate_ref)} · 核对：${safeText(item.verified_at)}`),
      el('p', '', safeText(item.scope_summary)),
      el('p', '', safeText(item.conclusion)),
    );
    return node;
  }

  function detailSections(data) {
    const sections = data.sections || {};
    const shell = el('div', 'qw-detail-sections');
    const overview = el('section', 'qw-detail-section');
    overview.id = 'overview';
    overview.append(el('h3', '', '需求概况与功能点映射'));
    const trace = sections.traceability || {};
    const facts = el('dl', 'qw-trace');
    [['PRD', trace.prd_refs], ['功能点', trace.feature_refs], ['Case', trace.case_ids], ['执行', trace.execution_case_ids], ['缺陷', trace.defect_ids], ['报告', trace.report_ids]].forEach(([label, values]) => {
      const row = el('div');
      row.append(el('dt', '', label), el('dd', '', Array.isArray(values) && values.length ? values.join('、') : copy.missing));
      facts.append(row);
    });
    overview.append(facts);
    shell.append(overview);
    shell.append(detailList('Case 列表', 'cases', sections.cases || [], caseItem, copy.noCases, (render) => filterControls('执行状态', [['', '全部状态'], ['passed', '通过'], ['failed', '失败'], ['blocked', '阻塞'], ['not_executed', '未执行']], (value) => render((item) => !value || (item.latest_execution ? item.latest_execution.execution_status === value : value === 'not_executed')))));
    shell.append(detailList('辅助自动化运行', 'automation', sections.automation || [], automationItem, copy.noAutomation, (render) => filterControls('运行状态', [['', '全部状态'], ['passed_pending_human', '待人工确认'], ['reviewed', '已确认'], ['failed', '失败']], (value) => render((item) => !value || item.automation_status === value))));
    shell.append(detailList('Jira / 缺陷与复测', 'defects', sections.defects || [], defectItem, copy.noDefects, (render) => filterControls('缺陷状态', [['', '全部状态'], ['open', 'Open'], ['in_progress', '修复中'], ['closed', '已关闭']], (value) => render((item) => !value || item.status === value))));
    shell.append(detailList('最终测试报告', 'reports', sections.reports || [], reportItem, copy.noReport));
    return shell;
  }

  function failure() {
    root.replaceChildren();
    const alert = warning([copy.loadingFailure]);
    const retry = el('button', 'safe-workspace-retry', '刷新重试');
    retry.type = 'button';
    retry.addEventListener('click', load);
    alert.append(retry);
    root.append(alert);
    root.setAttribute('aria-busy', 'false');
  }

  function render(data) {
    root.replaceChildren();
    root.setAttribute('aria-busy', 'false');
    const warnings = (Array.isArray(data.warnings) ? data.warnings : [])
      .map((item) => item && item.safe_message)
      .filter((item) => typeof item === 'string');
    if (warnings.length) root.append(warning(warnings));
    const selected = data.selected_requirement;
    const query = readQuery();
    if (Array.isArray(data.requirements) && data.requirements.length) {
      root.append(requirementTabs(data, selected ? selected.quality_requirement_id : query.requirement));
    }
    if (!selected) {
      if (!warnings.length) root.append(warning(['测试资产待关联，当前不展示质量结论']));
      return;
    }
    root.append(readinessSummary(selected));
    if (detailRequirement) root.append(detailSections(data));
    else root.append(overviewCards(data, selected));
  }

  async function load() {
    root.setAttribute('aria-busy', 'true');
    const query = readQuery();
    const endpoint = detailRequirement
      ? `/api/v1/project-status/quality-requirements/${encodeURIComponent(detailRequirement)}`
      : '/api/v1/project-status/quality-requirements';
    const url = new URL(endpoint, window.location.origin);
    if (!detailRequirement && query.requirement) url.searchParams.set('requirement', query.requirement);
    if (query.line) url.searchParams.set('line', query.line);
    try {
      const response = await fetch(url, {cache: 'no-store'});
      if (!response.ok) throw new Error('quality lifecycle request failed');
      const payload = await response.json();
      if (!payload || payload.success !== true || !payload.data) throw new Error('invalid quality lifecycle projection');
      render(payload.data);
      if (query.anchor) document.getElementById(query.anchor.slice(1))?.scrollIntoView({block: 'start'});
    } catch (_) {
      failure();
    }
  }

  load();
}());
