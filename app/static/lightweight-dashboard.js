// 五个一级页面的原型化渲染层：数据改 project-status.json，页面结构保持一致。
(function () {
  'use strict';

  const root = document.querySelector('[data-lightweight-dashboard]');
  if (!root) return;

  const page = document.body.dataset.dashboardPage || 'overview';
  const currentLine = document.body.dataset.dashboardLine || '';
  const pageCopy = {
    overview: ['PROJECT CONTROL ROOM', '项目总览', '只回答三件事：项目走到哪里、下一道关键门禁是什么、现在需要谁做决定。'],
    product: ['PRODUCT BASELINE', '产品 / PRD', '产品基线、范围、版本和决策在这里统一观察，不代替技术、前端或测试结论。'],
    frontend: ['FRONTEND DELIVERY', '前端交付', '只展示页面实现范围、候选版本和当前阻断；浏览器验证不在这里代替独立结论。'],
    development: ['BACKEND DELIVERY', '服务端交付', '只展示技术评审、实施范围和技术风险；完整评审资料进入受控详情。'],
    testing: ['QUALITY WORKSPACE', '质量 / 测试', '正式测试摘要、独立结论、缺陷生命周期和覆盖范围统一在这里观察。'],
  };

  function el(tag, className, value) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (value !== undefined && value !== null) node.textContent = String(value);
    return node;
  }

  function safe(value, fallback = '待关联') {
    return typeof value === 'string' && value.trim() ? value : fallback;
  }

  function display(value, fallback = '待关联') {
    return value === null || value === undefined || value === '' ? fallback : String(value);
  }

  function status(value) {
    const item = value && typeof value === 'object' ? value : {};
    const pill = el('span', 'lightweight-status', safe(item.label, '待核对'));
    const code = typeof item.code === 'string' ? item.code.replace(/[^A-Za-z0-9_-]/g, '') : '';
    if (code) {
      pill.classList.add(`lightweight-status-${code}`);
      pill.dataset.statusCode = code;
    }
    return pill;
  }

  function link(label, href, className = 'lightweight-link') {
    const node = el('a', className, label);
    node.href = href;
    return node;
  }

  function panel(title, body, action, className = '') {
    const article = el('article', `lightweight-panel ${className}`.trim());
    const head = el('div', 'lightweight-panel-head');
    const heading = el('h2', '', title);
    head.append(heading);
    if (action) head.append(action);
    article.append(head, body);
    return article;
  }

  function empty(message = '暂无已登记信息') {
    return el('p', 'lightweight-empty', message);
  }

  function meta(label, value) {
    const row = el('div', 'lightweight-meta-row');
    row.append(el('dt', '', label), el('dd', '', display(value)));
    return row;
  }

  function pagePath(path) {
    const url = new URL(path, window.location.origin);
    if (currentLine) url.searchParams.set('line', currentLine);
    return url.pathname + url.search;
  }

  function lineSelector(data) {
    const wrap = el('div', 'lightweight-filterbar');
    wrap.append(el('span', '', '当前交付线'));
    const select = document.createElement('select');
    select.id = 'lightweight-line-select';
    select.setAttribute('aria-label', '当前交付线');
    const all = el('option', '', '全部交付线');
    all.value = '';
    select.append(all);
    (Array.isArray(data.line_options) ? data.line_options : []).forEach((item) => {
      if (!item || typeof item.id !== 'string') return;
      const option = el('option', '', safe(item.label));
      option.value = item.id;
      select.append(option);
    });
    select.value = currentLine;
    select.addEventListener('change', () => {
      const url = new URL(window.location.href);
      if (select.value) url.searchParams.set('line', select.value);
      else url.searchParams.delete('line');
      window.location.assign(url.pathname + url.search);
    });
    wrap.append(select);
    const selected = data.selected_line;
    wrap.append(
      el('span', 'lightweight-filter-state', selected ? `当前状态：${safe(selected.status && selected.status.label)}` : '未筛选交付线'),
    );
    return wrap;
  }

  function pageHead(data) {
    const copy = pageCopy[page] || pageCopy.overview;
    const head = el('div', 'lightweight-page-head');
    const textBlock = el('div');
    const title = el('h1', '', copy[1]);
    title.id = 'dashboard-page-title';
    textBlock.append(el('p', 'lightweight-eyebrow', copy[0]), title, el('p', 'lightweight-page-description', copy[2]));
    const actions = el('div', 'lightweight-head-actions');
    const details = {
      overview: ['查看口径', '总览承载方向、进度、交付线和决策队列；没有数据时保持待关联。'],
      product: ['查看变更边界', '版本与变更只作为项目状态摘要展示，完整产品文档不在看板内展开。'],
      frontend: ['查看交付边界', '候选版本是交付身份，不等于独立测试通过、产品验收通过或可试用。'],
      development: ['查看风险边界', '技术评审和实施摘要只用于观察，审批仍在看板外完成。'],
      testing: ['查看测试口径', '正式测试、辅助自动化、产品验收和发布结论保持独立。'],
    };
    const [label, body] = details[page] || details.overview;
    const info = el('button', 'lightweight-button', label);
    info.type = 'button';
    info.dataset.lightweightDrawerTitle = label;
    info.dataset.lightweightDrawerBody = body;
    actions.append(info);
    if (page !== 'testing') actions.append(link(page === 'overview' ? '进入产品 / PRD' : '回到项目总览', pagePath(page === 'overview' ? '/project-status/product' : '/project-status'), 'lightweight-button lightweight-button-primary'));
    else actions.append(link('进入质量详情', pagePath('/project-status/tests/requirements'), 'lightweight-button lightweight-button-primary'));
    head.append(textBlock, actions);
    return head;
  }

  function metric(label, value, note, className = '') {
    const card = el('article', `lightweight-metric ${className}`.trim());
    const valueNode = el('strong', 'lightweight-metric-value', value);
    card.append(el('span', 'lightweight-label', label), valueNode, el('small', '', note));
    return card;
  }

  function progressBar(value) {
    const track = el('div', 'lightweight-progress-track');
    const fill = el('i');
    const percent = typeof value === 'number' && Number.isFinite(value) ? Math.max(0, Math.min(100, value)) : 0;
    fill.style.width = `${percent}%`;
    track.append(fill);
    return track;
  }

  function hero(data, title, summary, sideTitle, sideBody, sideAction) {
    const wrap = el('div', 'lightweight-hero');
    const main = el('article', 'lightweight-hero-main');
    main.append(el('p', 'lightweight-eyebrow', 'CURRENT STATUS'), el('h2', '', title), el('p', 'lightweight-hero-copy', summary));
    const side = el('article', 'lightweight-hero-side');
    side.append(el('p', 'lightweight-eyebrow', 'NEXT DECISION'), el('h3', '', sideTitle), el('p', '', sideBody));
    if (sideAction) side.append(sideAction);
    wrap.append(main, side);
    return wrap;
  }

  function lineRows(lines, compact = false) {
    const list = el('div', compact ? 'lightweight-line-list lightweight-line-list-compact' : 'lightweight-line-list');
    if (!Array.isArray(lines) || !lines.length) return empty('尚未建立产品交付线');
    lines.forEach((lineItem) => {
      const row = el('article', compact ? 'lightweight-line-row' : 'lightweight-line-row lightweight-line-row-large');
      const identity = el('div');
      identity.append(el('h3', '', safe(lineItem.name)), el('p', '', safe(lineItem.summary || lineItem.scope_summary)));
      const current = el('div', 'lightweight-line-meta');
      current.append(el('span', '', '当前状态'), status(lineItem.status), status(lineItem.evidence_level));
      const next = el('div', 'lightweight-line-meta');
      next.append(el('span', '', '下一步'), el('strong', '', safe(lineItem.next_action)));
      const count = el('div', 'lightweight-line-meta');
      count.append(el('span', '', '开放阻断'), el('strong', '', display(lineItem.blocker_count, '0')));
      row.append(identity, current, next, count, link('查看详情 →', pagePath(`/project-status/delivery-lines/${encodeURIComponent(lineItem.delivery_line_id)}`)));
      list.append(row);
    });
    return list;
  }

  function decisions(items) {
    const list = el('ul', 'lightweight-list');
    if (!Array.isArray(items) || !items.length) return empty('决策队列待关联');
    items.forEach((item) => {
      const row = el('li', 'lightweight-list-item');
      const heading = el('div', 'lightweight-list-heading');
      heading.append(el('strong', '', safe(item.title)), status(item.status));
      row.append(heading, el('p', '', safe(item.impact_summary)), el('p', 'lightweight-muted', `责任角色：${safe(item.owner_role)} · 下一步：${safe(item.next_action)}`));
      list.append(row);
    });
    return list;
  }

  function overview(data) {
    const item = data.data || {};
    const firstDecision = Array.isArray(item.decisions) && item.decisions[0];
    const title = safe(item.direction, '项目方向待关联');
    const summary = safe(item.summary);
    const sideTitle = firstDecision ? safe(firstDecision.title) : '当前暂无已登记决策';
    const sideBody = firstDecision ? safe(firstDecision.impact_summary) : '项目状态文件未登记下一项负责人决策。';
    const content = el('div', 'lightweight-content-block');
    content.append(pageHead(data), lineSelector(data));
    content.append(hero(data, title, summary, sideTitle, sideBody, firstDecision ? el('button', 'lightweight-hero-action', '查看决定项') : null));
    const metrics = el('div', 'lightweight-metric-grid lightweight-metric-grid-four');
    const progress = item.progress_percent;
    const selected = data.selected_line;
    metrics.append(metric('总体进度', progress === null || progress === undefined ? '待核对' : `${progress}%`, '轻量观察，不替代产品验收'));
    const currentCard = metric('当前交付线', selected ? safe(selected.name) : '全部交付线', selected ? safe(selected.status && selected.status.label) : '选择一条线查看上下文');
    currentCard.classList.add('lightweight-metric-wide-value');
    metrics.append(currentCard, metric('开放门禁', selected ? display(selected.blocker_count, '0') : '待关联', '来自交付线登记'), metric('最近变更', display(Array.isArray(item.recent_updates) ? item.recent_updates.length : 0), '状态文件中的更新条目'));
    const progressCard = metrics.firstElementChild;
    if (progressCard && progress !== null && progress !== undefined) progressCard.append(progressBar(progress));
    content.append(metrics);
    const gates = el('section', 'lightweight-section');
    const gateHead = el('div', 'lightweight-section-head');
    gateHead.append(el('div', '', null));
    gateHead.firstChild.append(el('p', 'lightweight-eyebrow', 'DELIVERY RHYTHM'), el('h2', '', '交付节奏'));
    gateHead.append(el('p', '', '未登记的阶段保持待关联，不由看板自行计算。'));
    const track = el('div', 'lightweight-track');
    ['产品基线', '字段契约', '组合候选', '开发联调', '独立测试', '产品验收'].forEach((label, index) => {
      const node = el('div', 'lightweight-track-node');
      node.append(el('span', '', `D${index + 1}`), el('strong', '', label), el('small', '', '待关联'));
      track.append(node);
    });
    gates.append(gateHead, track);
    content.append(gates);
    const lineSection = el('section', 'lightweight-section');
    const lineHead = el('div', 'lightweight-section-head');
    lineHead.append(el('h2', '', '产品交付线'), el('p', '', '状态、下一步和开放阻断保持同一行，便于横向比较。'));
    lineSection.append(lineHead, lineRows(item.lines));
    content.append(lineSection);
    const lower = el('div', 'lightweight-two-column');
    const roadmap = el('div', 'lightweight-list');
    roadmap.append(el('p', 'lightweight-eyebrow', 'PRODUCT BASELINE'), el('h3', '', safe(item.progress_summary, '产品基线待关联')), el('p', '', safe(item.summary)), link('进入产品页 →', pagePath('/project-status/product')));
    lower.append(panel('PRD / 产品基线', roadmap));
    lower.append(panel('需要关注', decisions(item.decisions), null, 'lightweight-panel-alert'));
    content.append(lower);
    return content;
  }

  function product(data) {
    const item = data.data || {};
    const versions = Array.isArray(item.versions) ? item.versions : [];
    const content = el('div', 'lightweight-content-block');
    content.append(pageHead(data), lineSelector(data));
    content.append(hero(data, safe(item.baseline, '产品基线待关联'), safe(item.current_position), safe(item.release && item.release.status && item.release.status.label, '发布状态待关联'), safe(item.release && item.release.summary, '发布摘要待关联')));
    const metrics = el('div', 'lightweight-metric-grid lightweight-metric-grid-four');
    metrics.append(metric('当前基线', safe(item.baseline), '产品基线编号'), metric('版本数量', display(versions.length), '当前状态文件登记'), metric('发布状态', safe(item.release && item.release.status && item.release.status.label), '不等于可试用或发布'), metric('交付线', display(Array.isArray(item.lines) ? item.lines.length : 0), '当前登记数量'));
    content.append(metrics);
    const scope = el('div', 'lightweight-list');
    if (!versions.length) scope.append(empty('版本与范围待关联'));
    versions.forEach((version) => {
      const row = el('article', 'lightweight-list-item');
      row.append(el('div', 'lightweight-list-heading', null));
      row.firstChild.append(el('strong', '', `${safe(version.code)} · ${safe(version.title)}`), status(version.status));
      row.append(el('p', '', safe(version.scope)), el('p', 'lightweight-muted', `下一道门：${safe(version.next_gate)}`));
      scope.append(row);
    });
    const baseline = el('div', 'lightweight-list');
    baseline.append(el('p', '', '产品范围由状态文件中的基线与版本摘要驱动。完整 PRD、原始变更记录和敏感文档不在看板内展开。'), el('p', 'lightweight-muted', '来源文档：产品基线来源已登记'));
    const acceptance = el('div', 'lightweight-list');
    acceptance.append(el('p', '', '产品验收、独立测试、试用和发布保持独立判断。缺少负责人确认时，页面显示待确认。'), el('p', 'lightweight-muted', '当前交付线可从总览进入受控详情。'));
    const columns = el('div', 'lightweight-three-column');
    const versionsPanel = panel('版本与范围', scope);
    versionsPanel.id = 'product-versions';
    columns.append(versionsPanel, panel('基线与验收边界', baseline), panel('产品决策提示', acceptance));
    content.append(columns);
    return content;
  }

  function rolePanel(role, title) {
    const body = el('div', 'lightweight-role-body');
    body.append(el('h3', '', safe(role && role.name)), status(role && role.status));
    const metaList = el('dl', 'lightweight-meta');
    metaList.append(meta('当前工作', role && role.current), meta('下一步', role && role.next), meta('等待事项', role && role.waiting_for));
    body.append(metaList);
    return panel(title, body);
  }

  function frontend(data) {
    const item = data.data || {};
    const content = el('div', 'lightweight-content-block');
    content.append(pageHead(data), lineSelector(data));
    content.append(hero(data, safe(item.role && item.role.current, '前端当前工作待关联'), safe(item.role && item.role.next), '前端交付边界', '候选版本和浏览器验证摘要待关联时，不替代独立测试结论。'));
    const metrics = el('div', 'lightweight-metric-grid lightweight-metric-grid-four');
    metrics.append(metric('角色状态', safe(item.role && item.role.status && item.role.status.label), '前端责任摘要'), metric('交付线', display(Array.isArray(item.lines) ? item.lines.length : 0), '当前登记数量'), metric('浏览器验证', '待关联', '不自动形成验收结论'), metric('前端阻断', '待关联', '等待状态文件登记'));
    content.append(metrics, panel('页面实现范围', lineRows(item.lines), null, 'lightweight-panel-full'));
    const candidate = el('div', 'lightweight-list');
    candidate.append(el('p', '', '候选版本只作为交付证据身份。前端、服务端和测试来源不一致时，保持待核对。'), el('p', 'lightweight-muted', '候选历史、关联交接单和浏览器证据进入后续受控详情。'));
    const blockers = el('div', 'lightweight-list');
    blockers.append(el('p', '', safe(item.browser_verification)), el('p', '', safe(item.blockers)));
    const columns = el('div', 'lightweight-two-column');
    columns.append(panel('前端候选版本', candidate), panel('验证与阻断', blockers));
    content.append(columns);
    return content;
  }

  function development(data) {
    const item = data.data || {};
    const reviews = Array.isArray(item.reviews) ? item.reviews : [];
    const content = el('div', 'lightweight-content-block');
    content.append(pageHead(data), lineSelector(data));
    content.append(hero(data, safe(item.role && item.role.current, '服务端当前工作待关联'), safe(item.role && item.role.next), '技术评审状态', reviews.length ? safe(reviews[0].status && reviews[0].status.label) : '待关联'));
    const metrics = el('div', 'lightweight-metric-grid lightweight-metric-grid-four');
    metrics.append(metric('角色状态', safe(item.role && item.role.status && item.role.status.label), '服务端责任摘要'), metric('技术评审', display(reviews.length), '当前登记数量'), metric('实施范围', '待关联', '不展开实施操作'), metric('技术风险', '待关联', '需要状态文件登记'));
    content.append(metrics);
    const reviewList = el('div', 'lightweight-list');
    if (!reviews.length) reviewList.append(empty('技术评审待关联'));
    reviews.forEach((review) => {
      const row = el('article', 'lightweight-list-item');
      row.append(el('div', 'lightweight-list-heading', null));
      row.firstChild.append(el('strong', '', `${safe(review.review_id)} · ${safe(review.title)}`), status(review.status));
      row.append(el('p', '', safe(review.scope)), el('p', 'lightweight-muted', `下一步：${safe(review.next)}`));
      reviewList.append(row);
    });
    const scope = el('div', 'lightweight-list');
    scope.append(el('p', '', safe(item.implementation_scope)), el('p', 'lightweight-muted', '实施包、迁移和完整技术方案不在看板内展开。'));
    const risks = el('div', 'lightweight-list');
    risks.append(el('p', '', safe(item.risks)), el('p', 'lightweight-muted', '风险应有影响、责任角色和解除条件。'));
    const columns = el('div', 'lightweight-two-column');
    columns.append(panel('技术评审状态', reviewList), panel('实施范围', scope), panel('技术风险', risks, null, 'lightweight-panel-alert'));
    content.append(columns);
    return content;
  }

  function quality(data) {
    const item = data.data || {};
    const ready = item.state === 'ready';
    const content = el('div', 'lightweight-content-block');
    content.append(pageHead(data), lineSelector(data));
    content.append(hero(data, ready ? '质量摘要已建立' : '质量统计待关联', ready ? '当前已登记质量对象，可从质量详情继续查看生命周期。' : '正式项目状态文件尚未关联质量工作区，页面不猜测 Case、缺陷或测试结论。', '质量边界', '辅助自动化、独立测试、产品验收、试用和发布仍分别判断.', link('进入质量详情 →', pagePath('/project-status/tests/requirements'), 'lightweight-hero-action')));
    const metrics = el('div', 'lightweight-metric-grid lightweight-metric-grid-six');
    metrics.append(metric('正式 Case', display(item.formal_cases), '不含候选 Case'), metric('已执行', display(item.executed), '正式执行结果'), metric('通过', display(item.passed), '不推导产品结论'), metric('失败 / 阻塞', `${display(item.failed)} / ${display(item.blocked)}`, '待后续核对'), metric('未执行', display(item.not_executed), '待后续执行'), metric('未关闭缺陷', item.defects ? display(item.defects.open) : '待关联', '来自缺陷登记'));
    content.append(metrics);
    const execution = el('div', 'lightweight-list');
    if (!ready) execution.append(empty('正式测试执行分布待关联'));
    else ['passed', 'failed', 'blocked', 'not_executed'].forEach((key) => {
      const labels = { passed: '通过', failed: '失败', blocked: '阻塞', not_executed: '未执行' };
      const row = el('div', 'lightweight-bar-row');
      row.append(el('span', '', labels[key]), progressBar(item[key] || 0), el('strong', '', display(item[key], '0')));
      execution.append(row);
    });
    const boundary = el('div', 'lightweight-list');
    boundary.append(el('p', '', '辅助自动化、开发自测和候选 Case 不自动计入正式测试通过。'), el('p', 'lightweight-muted', safe(item.coverage, '覆盖关系待关联')));
    const columns = el('div', 'lightweight-two-column');
    columns.append(panel('正式 Case 执行分布', execution), panel('缺陷与覆盖边界', boundary));
    content.append(columns);
    return content;
  }

  function syncNavLine() {
    document.querySelectorAll('[data-lightweight-nav]').forEach((nav) => {
      const url = new URL(nav.getAttribute('href') || '/project-status', window.location.origin);
      if (currentLine) url.searchParams.set('line', currentLine);
      else url.searchParams.delete('line');
      nav.href = url.pathname + url.search;
    });
  }

  function openDrawer(title, body) {
    const backdrop = document.querySelector('[data-lightweight-drawer-backdrop]');
    const drawerBody = document.querySelector('#lightweight-drawer-body');
    if (!backdrop || !drawerBody) return;
    document.querySelector('#lightweight-drawer-title').textContent = title;
    document.querySelector('#lightweight-drawer-sub').textContent = '受控摘要 · 本地只读';
    drawerBody.replaceChildren();
    const section = el('section', 'lightweight-drawer-section');
    section.append(el('h3', '', title), el('p', '', body), el('p', 'lightweight-muted', '完整原始文档、日志、代码路径和业务数据不在此面板展开。'));
    drawerBody.append(section);
    backdrop.hidden = false;
    backdrop.classList.add('is-open');
    document.querySelector('[data-lightweight-drawer-close]').focus();
  }

  function closeDrawer() {
    const backdrop = document.querySelector('[data-lightweight-drawer-backdrop]');
    if (!backdrop) return;
    backdrop.classList.remove('is-open');
    backdrop.hidden = true;
  }

  function render(data) {
    syncNavLine();
    const project = data.project || {};
    const crumb = document.querySelector('#lightweight-project-crumb');
    if (crumb) crumb.textContent = safe(project.name, '项目名称待关联');
    root.replaceChildren();
    const warnings = Array.isArray(data.warnings) ? data.warnings : [];
    if (warnings.length) {
      const alert = el('div', 'lightweight-alert');
      alert.setAttribute('role', 'alert');
      alert.append(el('strong', '', '请注意'));
      const list = el('ul');
      warnings.forEach((warning) => list.append(el('li', '', safe(warning && warning.safe_message, '部分数据待核对'))));
      alert.append(list);
      root.append(alert);
    }
    const views = { overview, product, frontend, development, testing: quality };
    root.append((views[page] || overview)(data));
    root.setAttribute('aria-busy', 'false');
  }

  document.addEventListener('click', (event) => {
    const trigger = event.target.closest('[data-lightweight-drawer-title]');
    if (trigger) {
      event.preventDefault();
      openDrawer(trigger.dataset.lightweightDrawerTitle, trigger.dataset.lightweightDrawerBody);
    }
    if (event.target.closest('[data-lightweight-drawer-close]') || event.target.matches('[data-lightweight-drawer-backdrop]')) closeDrawer();
  });
  document.addEventListener('keydown', (event) => { if (event.key === 'Escape') closeDrawer(); });

  const url = new URL('/api/v1/project-status/lightweight', window.location.origin);
  url.searchParams.set('page', page);
  if (currentLine) url.searchParams.set('line', currentLine);
  fetch(url.pathname + url.search, { headers: { Accept: 'application/json' }, cache: 'no-store' })
    .then((response) => { if (!response.ok) throw new Error('dashboard unavailable'); return response.json(); })
    .then((body) => { if (!body || body.success !== true || !body.data) throw new Error('invalid dashboard projection'); render(body.data); })
    .catch(() => {
      root.replaceChildren(el('p', 'lightweight-load-failure', '项目状态暂时无法加载，请稍后重试。'));
      root.setAttribute('role', 'alert');
      root.setAttribute('aria-busy', 'false');
    });
}());
